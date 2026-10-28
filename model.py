"""
model.py
Owner: Rob

PURPOSE
    Gurobi formulation of the Milestone 3/4 multi-period LP for the
    Mid-Atlantic gas merchant. Takes the dict returned by src/load_data.py,
    builds and solves the model, and returns a plain-Python solution dict that
    validate.py and visualizations.py read. No file I/O and no data cleaning here.

NOTATION (matches the Milestone 3 report)
    Sets        T months, J markets, L routes, F fields, L_j, F_j, F0
    Variables   x[t] hub purchases; s[l,t] shipments (measured at the hub);
                qin[f,t], qout[f,t] injections/withdrawals; I[f,t] inventory;
                u[j,t] citygate spot purchases; k[l] firm capacity (Dth/day)
    Constraints HB hub balance, DM market balance, IB inventory balance,
                PC pipeline capacity, KC capacity access limit, SL storage limits,
                CI cyclic inventory

USAGE
    from model import solve
    sol = solve(data)                   # data = load_data()
    sol["objective"], sol["x"][1], sol["duals"]["DM"][("NY", 10)]
"""

import gurobipy as gp
from gurobipy import GRB


def build_model(data: dict, verbose: bool = False):
    """Build (but do not solve) the LP. Returns (model, vars) where vars maps
    variable names to the gurobipy tupledicts, and constraints are reachable
    through model.getConstrByName or the 'cons' entry of vars."""
    T, J, L, F = data["T"], data["J"], data["L"], data["F"]
    L_j, F_j, F0 = data["L_j"], data["F_j"], data["F0"]
    d, P, D, pi = data["days"], data["P"], data["D"], data["pi"]
    c, R, kbar, phi = data["c"], data["R"], data["kbar"], data["phi"]
    Ibar, I0 = data["Ibar"], data["I0"]
    r_in, r_out, c_in, c_out = data["r_in"], data["r_out"], data["c_in"], data["c_out"]

    m = gp.Model("gas_merchant")
    m.Params.OutputFlag = 1 if verbose else 0

    # ---------------- Decision variables (all continuous, >= 0) ----------------
    x    = m.addVars(T,    name="x")      # hub purchases, Dth
    s    = m.addVars(L, T, name="s")      # shipments on route l, Dth (at hub)
    qin  = m.addVars(F, T, name="qin")    # injections, Dth
    qout = m.addVars(F, T, name="qout")   # withdrawals, Dth
    I    = m.addVars(F, T, name="I")      # end-of-month inventory, Dth
    u    = m.addVars(J, T, name="u")      # citygate spot purchases, Dth
    k    = m.addVars(L,    name="k")      # firm capacity contracted, Dth/day

    # Inventory at the end of month t-1 (I0 for t = first month)
    def I_prev(f, t):
        return I0[f] if t == T[0] else I[f, t - 1]

    # ---------------- Objective ----------------
    purchase = gp.quicksum(P[t] * x[t] for t in T)
    usage    = gp.quicksum(c[l] * s[l, t] for l in L for t in T)
    storage  = gp.quicksum(c_in[f] * qin[f, t] + c_out[f] * qout[f, t] for f in F for t in T)
    spot     = gp.quicksum(pi[j, t] * u[j, t] for j in J for t in T)
    reserve  = gp.quicksum(len(T) * R[l] * k[l] for l in L)   # paid every month
    m.setObjective(purchase + usage + storage + spot + reserve, GRB.MINIMIZE)

    # ---------------- Constraints ----------------
    cons = {}
    # (HB) hub purchases + net hub-storage withdrawals = total shipped
    cons["HB"] = m.addConstrs(
        (x[t] + gp.quicksum(qout[f, t] - qin[f, t] for f in F0)
         == gp.quicksum(s[l, t] for l in L) for t in T), name="HB")

    # (DM) deliveries net of fuel + net market-storage withdrawals + spot = demand
    cons["DM"] = m.addConstrs(
        (gp.quicksum((1 - phi[l]) * s[l, t] for l in L_j[j])
         + gp.quicksum(qout[f, t] - qin[f, t] for f in F_j[j])
         + u[j, t] == D[j, t] for j in J for t in T), name="DM")

    # (IB) inventory carries over
    cons["IB"] = m.addConstrs(
        (I[f, t] == I_prev(f, t) + qin[f, t] - qout[f, t] for f in F for t in T), name="IB")

    # (PC) monthly shipments within contracted daily capacity
    cons["PC"] = m.addConstrs(
        (s[l, t] <= d[t] * k[l] for l in L for t in T), name="PC")

    # (KC) contracted capacity within what the merchant can access.
    # Written as a constraint (not a variable bound) so its dual is reported:
    # the annual value of one more Dth/day of accessible capacity on route l.
    cons["KC"] = m.addConstrs((k[l] <= kbar[l] for l in L), name="KC")

    # (SL) storage rate and capacity limits
    cons["SL_in"]  = m.addConstrs((qin[f, t]  <= d[t] * r_in[f]  for f in F for t in T), name="SL_in")
    cons["SL_out"] = m.addConstrs((qout[f, t] <= d[t] * r_out[f] for f in F for t in T), name="SL_out")
    cons["SL_cap"] = m.addConstrs((I[f, t] <= Ibar[f] for f in F for t in T), name="SL_cap")

    # (CI) end the year where we started
    cons["CI"] = m.addConstrs((I[f, T[-1]] == I0[f] for f in F), name="CI")

    m.update()
    vars_ = dict(x=x, s=s, qin=qin, qout=qout, I=I, u=u, k=k, cons=cons,
                 cost_terms=dict(purchase=purchase, pipeline_usage=usage,
                                 storage_fees=storage, spot=spot, reservation=reserve))
    return m, vars_


def solve(data: dict, verbose: bool = False) -> dict:
    """Build and solve the LP. Returns the solution dict:

        status        str     "OPTIMAL", "INFEASIBLE", ...
        objective     float   total annual cost, $
        costs         dict    objective broken into its five terms, $
        x, k          dict    {t: Dth}, {l: Dth/day}
        s, qin, qout, I, u    dict keyed (l,t), (f,t), (f,t), (f,t), (j,t)
        duals         dict of dicts, keyed like the constraint indices:
            DM      $/Dth   marginal cost of serving one more Dth in market j, month t
            KC      $/(Dth/day)/yr  value of one more Dth/day of accessible capacity
                            (reported as a positive saving)
            SL_cap  $/Dth   value of one more Dth of storage space in field f, month t
            SL_in, SL_out, PC, HB, IB, CI as returned by Gurobi
    Sign convention: Gurobi duals for a minimisation; for <= constraints a
    binding limit gives Pi <= 0, so KC and SL_cap are negated to read as savings.
    """
    m, v = build_model(data, verbose)
    m.optimize()

    status = {GRB.OPTIMAL: "OPTIMAL", GRB.INFEASIBLE: "INFEASIBLE",
              GRB.UNBOUNDED: "UNBOUNDED", GRB.INF_OR_UNBD: "INF_OR_UNBD"}.get(m.Status, str(m.Status))
    sol = {"status": status}
    if m.Status != GRB.OPTIMAL:
        if m.Status == GRB.INFEASIBLE:
            m.computeIIS()
            sol["iis"] = [c.ConstrName for c in m.getConstrs() if c.IISConstr]
        return sol

    val = lambda td: {key: var.X for key, var in td.items()}
    sol["objective"] = m.ObjVal
    sol["costs"] = {name: expr.getValue() for name, expr in v["cost_terms"].items()}
    for name in ["x", "s", "qin", "qout", "I", "u", "k"]:
        sol[name] = val(v[name])

    flip = {"KC", "SL_cap"}
    sol["duals"] = {
        name: {key: (-con.Pi if name in flip else con.Pi) for key, con in cd.items()}
        for name, cd in v["cons"].items()
    }
    sol["model"] = m   # kept for sensitivity work (SAObjLow/Up, RHSLow/Up, etc.)
    return sol


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
    from load_data import load_data

    sol = solve(load_data(), verbose=True)
    print(sol["status"], f"${sol.get('objective', float('nan')):,.0f}")
    for name, value in sol.get("costs", {}).items():
        print(f"  {name:15s} ${value:,.0f}")
