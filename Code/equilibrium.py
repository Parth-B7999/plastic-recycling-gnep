"""
equilibrium.py -- Shared result container and the exact analytic reference solver.

The analytic solver here is the ground truth the whole verification suite is
built on.  Because each agent's best response

    q_i(lambda) = clip( (m_i - lambda) / b_i , 0 , Cap_i )

is continuous and NON-INCREASING in lambda, the aggregate demand
sum_i q_i(lambda) is non-increasing, so the market-clearing condition

    sum_i q_i(lambda) = Q_tot

has a solution that 1-D bisection finds to machine precision.  This is an
exact, independent check of the entire model and owes nothing to Pyomo, IPOPT,
PATH or scipy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import data as D

__all__ = ["Equilibrium", "best_response", "aggregate_demand", "solve_analytic",
           "STATE_AT_CAPACITY", "STATE_PRICE_SETTER", "STATE_PRICED_OUT",
           "AGENT_STATES"]

# -----------------------------------------------------------------------------
# Equilibrium states of an agent
# -----------------------------------------------------------------------------
# These describe where an agent actually SITS at the solved equilibrium.  They
# are NOT the same thing as data.AgentData.wants_more_than_nameplate, which is a
# static structural property of the agent's own cost curve and knows nothing
# about lambda.  Incineration is the standing counterexample: at the base case
# it is a PRICE_SETTER (2,000 of 4,000 t/yr, mu_W = 0) while
# wants_more_than_nameplate is True.
STATE_AT_CAPACITY = "AT CAPACITY"      # q_i = Cap_i, mu_i > 0: wants more, cannot have it
STATE_PRICE_SETTER = "PRICE-SETTER"    # 0 < q_i < Cap_i, mu_i = 0: THIS agent pins lambda
STATE_PRICED_OUT = "PRICED OUT"        # q_i = 0, m_i < lambda: cannot outbid the others
AGENT_STATES = (STATE_AT_CAPACITY, STATE_PRICE_SETTER, STATE_PRICED_OUT)


@dataclass
class Equilibrium:
    """Solution of one variational equilibrium problem.

    Attributes:
        q:            Equilibrium throughput per agent, ton/yr.
        mu:           Multiplier on the private capacity bound, USD/ton.
        multipliers:  Multiplier per shared constraint, keyed by constraint key
                      (v1 has exactly one, "lambda", in USD/ton).
        q_tot:        Feedstock availability the problem was solved at, ton/yr.
        method:       Which engine produced this ("analytic", "planner",
                      "mcp-fb", "mcp-path", "best-response").
        iterations:   Iteration count where meaningful, else None.
        trace:        Convergence trace where meaningful.
        info:         Free-form diagnostics.
    """

    q: dict[str, float]
    mu: dict[str, float]
    multipliers: dict[str, float]
    q_tot: float
    method: str
    iterations: int | None = None
    trace: list[float] = field(default_factory=list)
    info: dict[str, object] = field(default_factory=dict)

    @property
    def lam(self) -> float:
        """The headline quantity: shadow price of shared feedstock, USD/ton."""
        return self.multipliers["lambda"]

    @property
    def total_q(self) -> float:
        """Total feedstock actually taken up by the agents, ton/yr."""
        return sum(self.q.values())

    def operating_profit(self, key: str) -> float:
        """Operating profit of agent `key`, USD/yr."""
        ag = D.AGENTS[key]
        return ag.margin * self.q[key] - 0.5 * ag.b * self.q[key] ** 2

    def net_profit(self, key: str) -> float:
        """Profit net of annualized CAPEX for agent `key`, USD/yr."""
        return self.operating_profit(key) - D.AGENTS[key].acc

    def emissions(self, key: str) -> float:
        """Emissions of agent `key`, t CO2e/yr."""
        return D.AGENTS[key].e_total * self.q[key]

    def unbought_feedstock(self) -> float:
        """Feedstock no agent buys, which goes to landfill, ton/yr."""
        return max(0.0, self.q_tot - self.total_q)

    def system_emissions(self) -> float:
        """System-wide emissions including landfilling of unbought feed.

        The unbought stream affects system accounting only -- never any agent's
        profit, per the v1 scope.

        Returns:
            Total emissions, t CO2e/yr.
        """
        agent_part = sum(self.emissions(k) for k in self.q)
        landfill_part = (
            D.EMIS_UNIT_SCALE * D.GWP_LANDFILL * self.unbought_feedstock()
        )
        return agent_part + landfill_part

    def agent_state(self, key: str,
                    agents: dict[str, D.AgentData] | None = None) -> str:
        """Equilibrium state of agent `key`: where it actually sits at lambda*.

        Classifies from the SOLVED shared price, not from any static property of
        the agent.  The three states are mutually exclusive and exhaustive:

            STATE_AT_CAPACITY   q_i = Cap_i, mu_i > 0
                                -- wants more feedstock, cannot have it
            STATE_PRICE_SETTER  0 < q_i < Cap_i, mu_i = 0
                                -- interior; THIS agent's first-order condition
                                   pins lambda
            STATE_PRICED_OUT    q_i = 0, m_i < lambda
                                -- cannot outbid the others for a single tonne

        Args:
            key:    Agent identifier.
            agents: Agent set; defaults to data.AGENTS.

        Returns:
            One of AGENT_STATES.
        """
        ags = D.AGENTS if agents is None else agents
        interior, at_cap, _ = _classify(self.multipliers["lambda"], ags)
        if key in at_cap:
            return STATE_AT_CAPACITY
        if key in interior:
            return STATE_PRICE_SETTER
        return STATE_PRICED_OUT

    def agent_states(self, agents: dict[str, D.AgentData] | None = None
                     ) -> dict[str, str]:
        """Equilibrium state of every agent, keyed by agent identifier."""
        ags = D.AGENTS if agents is None else agents
        return {k: self.agent_state(k, ags) for k in ags}

    def price_setters(self, agents: dict[str, D.AgentData] | None = None
                      ) -> list[str]:
        """Agents whose first-order condition pins lambda at this equilibrium.

        Normally exactly one.  It is empty in two cases:

        * At the degenerate Q_tot where aggregate demand is flat and lambda is
          set-valued (Q_tot = 0, Cap_S, Cap_S + Cap_W) -- there no agent is
          strictly interior, so none pins the price, and we report the lower end
          of the valid interval by convention.
        * When the shared constraint is SLACK (abundant feedstock, lambda = 0).
          An agent can then be positionally interior -- gasification is, above
          Q_tot = 11,374 -- but it is sitting at its own unconstrained optimum,
          not pinning a scarcity price, because there is no scarcity to price.

        Args:
            agents: Agent set; defaults to data.AGENTS.

        Returns:
            Agent keys in STATE_PRICE_SETTER, or [] if feedstock is not scarce.
        """
        ags = D.AGENTS if agents is None else agents
        if self.total_q < self.q_tot - 1e-6:
            return []
        return [k for k in ags if self.agent_state(k, ags) == STATE_PRICE_SETTER]

    def complementarity_residuals(
        self, agents: dict[str, D.AgentData] | None = None
    ) -> dict[str, float]:
        """Every KKT / complementarity residual of the stacked system.

        Args:
            agents: The agent set THIS equilibrium was actually solved against.
                Defaults to data.AGENTS -- correct for every base-case call in
                this project, but MUST be passed explicitly whenever `self` was
                solved with a custom agent set (e.g. a capacity swept away from
                its data.py value in capacity_sensitivity.py). Checking residuals
                against the wrong (base-case) agent parameters is exactly the
                static/dynamic conflation flagged in
                data.AgentData.wants_more_than_nameplate -- one level up here.

        Returns:
            Mapping from residual name to absolute violation.  All entries must
            be below 1e-8 at a valid variational equilibrium.
        """
        ags = D.AGENTS if agents is None else agents
        res: dict[str, float] = {}
        lam = self.lam
        for k, ag in ags.items():
            q, mu = self.q[k], self.mu[k]
            stat = ag.b * q - ag.margin + lam + mu      # dual feasibility
            res[f"q_{k}>=0"] = max(0.0, -q)
            res[f"stat_{k}>=0"] = max(0.0, -stat)
            res[f"comp_q_{k}"] = abs(q * stat)
            res[f"mu_{k}>=0"] = max(0.0, -mu)
            res[f"cap_slack_{k}>=0"] = max(0.0, q - ag.cap)
            res[f"comp_mu_{k}"] = abs(mu * (ag.cap - q))
        res["lambda>=0"] = max(0.0, -lam)
        slack = self.q_tot - self.total_q
        res["shared_slack>=0"] = max(0.0, -slack)
        res["comp_lambda"] = abs(lam * slack)
        return res

    def max_residual(self, agents: dict[str, D.AgentData] | None = None) -> float:
        """Largest complementarity residual, for assertions and reporting.

        Args:
            agents: See `complementarity_residuals` -- pass the agent set this
                equilibrium was actually solved against if it differs from
                data.AGENTS.
        """
        return max(self.complementarity_residuals(agents).values())


def best_response(agent: D.AgentData, lam: float) -> float:
    """Agent's profit-maximizing throughput given the shared price `lam`.

    Solves  max_q  (m_i - lambda)*q - 0.5*b_i*q^2  s.t. 0 <= q <= Cap_i,
    whose solution is the clipped interior optimum.  `lam` acts exactly like a
    uniform surcharge on feedstock that every agent faces identically.

    Args:
        agent: Agent parameters.
        lam:   Shared feedstock scarcity price, USD/ton.

    Returns:
        Best-response throughput, ton/yr.
    """
    return min(agent.cap, max(0.0, (agent.margin - lam) / agent.b))


def aggregate_demand(lam: float, agents: dict[str, D.AgentData] | None = None) -> float:
    """Total feedstock demanded by all agents at price `lam`, ton/yr."""
    ags = D.AGENTS if agents is None else agents
    return sum(best_response(a, lam) for a in ags.values())


def _classify(lam: float, ags: dict[str, D.AgentData]
              ) -> tuple[list[str], list[str], list[str]]:
    """Partition agents by their best response at price `lam`.

    Args:
        lam:  Shared feedstock price, USD/ton.
        ags:  Agent set.

    Returns:
        (interior, at_cap, priced_out) lists of agent keys, where
        interior   = 0 < q_i(lam) < Cap_i   (these agents SET the price)
        at_cap     = q_i(lam) = Cap_i
        priced_out = q_i(lam) = 0
    """
    interior: list[str] = []
    at_cap: list[str] = []
    priced_out: list[str] = []
    for k, a in ags.items():
        x = (a.margin - lam) / a.b
        if x <= 0.0:
            priced_out.append(k)
        elif x >= a.cap:
            at_cap.append(k)
        else:
            interior.append(k)
    return interior, at_cap, priced_out


def _breakpoints(ags: dict[str, D.AgentData]) -> list[float]:
    """Kinks of the aggregate demand curve, sorted descending.

    Aggregate demand sum_i clip((m_i - lambda)/b_i, 0, Cap_i) is piecewise
    linear in lambda, changing slope only where some agent's demand hits 0
    (lambda = m_i) or hits its cap (lambda = m_i - b_i*Cap_i).  Between two
    consecutive breakpoints the active set is FIXED, so the market-clearing
    lambda can be written down in closed form -- no tolerance tuning, and no
    chance of mis-identifying the active set near the jump at Q_tot = Cap_S.

    Args:
        ags: Agent set.

    Returns:
        Distinct non-negative breakpoints, largest first.
    """
    pts = {0.0}
    for a in ags.values():
        if a.margin > 0.0:
            pts.add(a.margin)
        edge = a.margin - a.b * a.cap
        if edge > 0.0:
            pts.add(edge)
    return sorted(pts, reverse=True)


def _assemble(lam: float, q_tot: float, ags: dict[str, D.AgentData],
              method: str, binding: bool, **info: object) -> Equilibrium:
    """Build an Equilibrium from a clearing price, exactly.

    Args:
        lam:     Market-clearing shared price, USD/ton.
        q_tot:   Feedstock availability, ton/yr.
        ags:     Agent set.
        method:  Label for the producing engine.
        binding: True if the shared constraint is active (sum_i q_i = Q_tot).
                 When it binds and exactly one agent is interior, that agent is
                 handed the residual feed directly -- the best-conditioned form,
                 which drives the stationarity residual to ~1e-16.  When the
                 constraint is slack every agent simply takes its unconstrained
                 best response.
        info:    Extra diagnostics.

    Returns:
        Equilibrium with machine-precision complementarity residuals.
    """
    interior, at_cap, _ = _classify(lam, ags)
    q = {k: best_response(a, lam) for k, a in ags.items()}
    if binding and len(interior) == 1:
        k0 = interior[0]
        q[k0] = max(0.0, min(ags[k0].cap,
                             q_tot - sum(ags[k].cap for k in at_cap)))
    mu = {k: max(0.0, ags[k].margin - ags[k].b * q[k] - lam) if k in at_cap
          else 0.0 for k in ags}
    return Equilibrium(q=q, mu=mu, multipliers={"lambda": lam}, q_tot=q_tot,
                       method=method, info=dict(info))


def solve_analytic(
    q_tot: float = D.Q_TOT_BASE,
    agents: dict[str, D.AgentData] | None = None,
) -> Equilibrium:
    """Solve the variational equilibrium EXACTLY by walking demand breakpoints.

    No iteration and no tolerance.  Aggregate demand is piecewise linear and
    non-increasing in lambda, so the equilibrium price is

        lambda* = min { lambda >= 0 : aggregate_demand(lambda) <= Q_tot }

    We locate the lowest demand segment that brackets Q_tot and invert that
    segment in closed form.  Taking the MINIMUM such lambda fixes the
    convention wherever lambda is set-valued (demand flat at Q_tot -- e.g.
    Q_tot exactly equal to Cap_S, or to Cap_S + Cap_W): we report the smallest
    price that clears the market, which is also the right-hand limit of
    lambda(Q_tot) and exactly what plain bisection converges to.  Every engine
    in this project uses that same convention, so they agree everywhere.

    Args:
        q_tot:  Feedstock availability, ton/yr.
        agents: Agent set; defaults to data.AGENTS.

    Returns:
        Equilibrium with method="analytic".
    """
    ags = D.AGENTS if agents is None else agents
    q_tot = max(0.0, float(q_tot))

    if aggregate_demand(0.0, ags) <= q_tot:
        return _assemble(0.0, q_tot, ags, "analytic", binding=False,
                         regime="abundant")

    brk = _breakpoints(ags)              # descending
    ascending = list(reversed(brk))      # 0.0 first
    for lo, hi in zip(ascending[:-1], ascending[1:]):
        if not (aggregate_demand(lo, ags) > q_tot >= aggregate_demand(hi, ags)):
            continue
        interior, at_cap, _ = _classify(0.5 * (lo + hi), ags)
        if not interior:
            # Flat segment cannot satisfy the strict inequality above, so this
            # branch is unreachable; guard it rather than divide by zero.
            return _assemble(hi, q_tot, ags, "analytic", binding=True,
                             regime="flat-segment")
        residual_feed = q_tot - sum(ags[k].cap for k in at_cap)
        if len(interior) == 1:
            k0 = interior[0]
            lam = ags[k0].margin - ags[k0].b * residual_feed
        else:
            num = sum(ags[k].margin / ags[k].b for k in interior) - residual_feed
            den = sum(1.0 / ags[k].b for k in interior)
            lam = num / den
        lam = min(hi, max(lo, lam))
        return _assemble(lam, q_tot, ags, "analytic", binding=True,
                         regime="scarce")

    # Price at or above every agent's margin: nobody operates.  Reached only
    # when Q_tot is (near) zero.
    lam = max(0.0, max(a.margin for a in ags.values()))
    return _assemble(lam, q_tot, ags, "analytic", binding=True,
                     regime="no-uptake")


def solve_bisection(
    q_tot: float = D.Q_TOT_BASE,
    agents: dict[str, D.AgentData] | None = None,
    tol: float = 1e-12,
    max_iter: int = 400,
) -> Equilibrium:
    """Solve the VE by plain 1-D bisection on lambda -- the brief's test #1.

    Deliberately the dumbest possible method: it uses only the monotonicity of
    q_i(lambda) and knows nothing about active sets, Pyomo, or the MCP.  That
    independence is the whole point.

    Args:
        q_tot:    Feedstock availability, ton/yr.
        agents:   Agent set; defaults to data.AGENTS.
        tol:      Absolute width of the final lambda bracket, USD/ton.
        max_iter: Iteration cap.

    Returns:
        Equilibrium with method="bisection".
    """
    ags = D.AGENTS if agents is None else agents
    q_tot = max(0.0, float(q_tot))

    if aggregate_demand(0.0, ags) <= q_tot:
        return _assemble(0.0, q_tot, ags, "bisection", binding=False,
                         iterations=0)

    lo, hi = 0.0, max(a.margin for a in ags.values())
    if hi <= 0.0:
        return _assemble(0.0, q_tot, ags, "bisection", binding=False,
                         iterations=0)

    it = 0
    for it in range(1, max_iter + 1):
        mid = 0.5 * (lo + hi)
        if aggregate_demand(mid, ags) > q_tot:
            lo = mid
        else:
            hi = mid
        if hi - lo <= tol:
            break
    eq = _assemble(0.5 * (lo + hi), q_tot, ags, "bisection", binding=True)
    eq.iterations = it
    return eq


# =============================================================================
# Multiplier non-uniqueness at degenerate Q_tot
# =============================================================================

def lambda_from_primal(
    q: dict[str, float],
    q_tot: float,
    agents: dict[str, D.AgentData] | None = None,
    tol: float = 1e-6,
) -> float:
    """Smallest lambda >= 0 consistent with a given primal allocation `q`.

    WHY THIS EXISTS.  The equilibrium ALLOCATION q* is unique everywhere
    (each agent's program is strictly concave), but the shared MULTIPLIER
    lambda is unique only where some agent is strictly interior.  At the
    finitely many Q_tot where aggregate demand is flat -- Q_tot = Cap_S,
    Q_tot = Cap_S + Cap_W, Q_tot = 0 -- every agent sits at 0 or at its cap, and
    an entire INTERVAL of lambda supports the same q*.  A QP solver (Method A)
    or a complementarity solver (Method B) will each return some arbitrary
    point of that interval, so the three methods would appear to disagree on
    lambda while agreeing perfectly on q.

    CONVENTION.  This project always reports the LOWER end of the valid
    interval: the smallest price that clears the market, which is also the
    right-hand limit of lambda(Q_tot) and exactly what plain bisection
    converges to.  Applying this projection to each engine's primal solution
    makes the methods comparable without touching the primal answer.

    The valid interval is read straight off the stacked KKT conditions:
        q_i = 0        =>  lambda >= m_i
        0 < q_i < Cap  =>  lambda  = m_i - b_i*q_i          (pins lambda)
        q_i = Cap_i    =>  lambda <= m_i - b_i*Cap_i
        sum_i q_i < Q_tot  =>  lambda = 0

    Args:
        q:      Primal allocation per agent, ton/yr.
        q_tot:  Feedstock availability, ton/yr.
        agents: Agent set; defaults to data.AGENTS.
        tol:    Absolute tolerance, ton/yr, for deciding "at a bound".

    Returns:
        The lower end of the valid lambda interval, USD/ton.
    """
    ags = D.AGENTS if agents is None else agents
    if sum(q.values()) < q_tot - tol:
        return 0.0                       # shared constraint slack
    for k, a in ags.items():             # an interior agent pins lambda
        if tol < q[k] < a.cap - tol:
            return max(0.0, a.margin - a.b * q[k])
    lower = 0.0
    for k, a in ags.items():
        if q[k] <= tol:
            lower = max(lower, a.margin)
    return max(0.0, lower)


def mu_from_primal(
    q: dict[str, float],
    lam: float,
    agents: dict[str, D.AgentData] | None = None,
    tol: float = 1e-6,
) -> dict[str, float]:
    """Private capacity multipliers implied by a primal allocation and lambda.

    mu_i = max(0, m_i - b_i*q_i - lambda) for agents at their cap, else 0.

    Args:
        q:      Primal allocation per agent, ton/yr.
        lam:    Shared feedstock price, USD/ton.
        agents: Agent set; defaults to data.AGENTS.
        tol:    Absolute tolerance, ton/yr, for deciding "at the cap".

    Returns:
        Multiplier per agent, USD/ton.
    """
    ags = D.AGENTS if agents is None else agents
    return {
        k: max(0.0, a.margin - a.b * q[k] - lam) if q[k] >= a.cap - tol else 0.0
        for k, a in ags.items()
    }
