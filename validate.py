import calendar
import math
import warnings


PARAMETER_KEYS = {
    "T", "J", "L", "F", "L_j", "F_j", "F0", "days", "P", "D", "pi",
    "c", "R", "kbar", "phi", "Ibar", "I0", "r_in", "r_out", "c_in", "c_out"
}


def finish(problems):
    for problem in problems:
        print(problem)
    return problems


def check_values(name, values, expected, problems, nonnegative=True):
    if not isinstance(values, dict):
        problems.append(f"{name}: expected a dictionary")
        return False
    if set(values) != expected:
        problems.append(f"{name}: missing keys {expected - set(values)}; unexpected keys {set(values) - expected}")
    valid = set(values) == expected
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            problems.append(f"{name}[{key}]: expected finite number, got {value!r}")
            valid = False
        elif nonnegative and value < 0:
            problems.append(f"{name}[{key}]: negative value {value}")
            valid = False
    return valid


def validate_inputs(data):
    problems = []
    if not isinstance(data, dict):
        return finish(["Inputs must be a dictionary"])
    missing = PARAMETER_KEYS - set(data)
    if missing:
        return finish([f"Missing input keys: {sorted(missing)}"])
    expected_sets = {"T": list(range(1, 13)), "J": ["NY", "NJ", "PA"], "L": [1, 2, 3, 4], "F": ["H", "M"]}
    for name, expected in expected_sets.items():
        if data[name] != expected:
            problems.append(f"{name}: expected {expected}, got {data[name]}")
    if problems:
        return finish(problems)
    T, J, L, F = data["T"], data["J"], data["L"], data["F"]
    domains = {"days": set(T), "P": set(T), "D": {(j, t) for j in J for t in T}, "pi": {(j, t) for j in J for t in T}}
    domains.update({name: set(L) for name in ["c", "R", "kbar", "phi"]})
    domains.update({name: set(F) for name in ["Ibar", "I0", "r_in", "r_out", "c_in", "c_out"]})
    valid = {name: check_values(name, data[name], keys, problems) for name, keys in domains.items()}
    if valid["days"]:
        expected_days = [calendar.monthrange(2025 if t <= 9 else 2026, (t + 2) % 12 + 1)[1] for t in T]
        if list(data["days"][t] for t in T) != expected_days:
            problems.append("days: counts must match April 2025 through March 2026 (365 days)")
    if valid["phi"]:
        for route, value in data["phi"].items():
            if value > 1:
                problems.append(f"phi[{route}]: {value} is outside [0, 1]")
    if valid["I0"] and valid["Ibar"]:
        for field in F:
            if data["I0"][field] > data["Ibar"][field]:
                problems.append(f"I0[{field}]: opening inventory exceeds capacity")
    for name, expected in {"L_j": {"NY": [1, 2], "NJ": [3], "PA": [4]}, "F_j": {"NY": ["M"], "NJ": [], "PA": []}, "F0": ["H"]}.items():
        if data[name] != expected:
            problems.append(f"{name}: expected network mapping {expected}, got {data[name]}")
    for name, low, high in [("D", 1e5, 1e8), ("P", 0.5, 50), ("pi", 0.5, 50)]:
        if valid[name]:
            unusual = [(key, value) for key, value in data[name].items() if not low <= value <= high]
            if unusual:
                warnings.warn(f"{name}: outside usual range [{low}, {high}]; verify units: {unusual[:3]}", stacklevel=2)
    return finish(problems)


def validate_solution(solution, data, tol=1e-6):
    if not math.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    problems = validate_inputs(data)
    if problems:
        return problems
    if not isinstance(solution, dict) or solution.get("status") != "OPTIMAL":
        return finish([f"Solution status must be OPTIMAL, got {solution.get('status') if isinstance(solution, dict) else solution}"])
    T, J, L, F = data["T"], data["J"], data["L"], data["F"]
    domains = {"x": set(T), "k": set(L), "s": {(l, t) for l in L for t in T}, "u": {(j, t) for j in J for t in T}}
    domains.update({name: {(f, t) for f in F for t in T} for name in ["qin", "qout", "I"]})
    for name, keys in domains.items():
        check_values(name, solution.get(name), keys, problems, nonnegative=False)
    if problems:
        return finish(problems)
    for name in domains:
        for key, value in solution[name].items():
            if value < -tol:
                problems.append(f"{name}[{key}]: negative solution value {value}")
    def equal(name, left, right):
        if abs(left - right) > tol:
            problems.append(f"{name}: residual {left - right:.9g} exceeds {tol}")
    def upper(name, value, limit):
        if value - limit > tol:
            problems.append(f"{name}: {value:.9g} exceeds {limit:.9g}")
    x, s, u = solution["x"], solution["s"], solution["u"]
    qin, qout, inventory, capacity = [solution[name] for name in ["qin", "qout", "I", "k"]]
    for t in T:
        equal(f"HB[{t}]", x[t] + sum(qout[f, t] - qin[f, t] for f in data["F0"]), sum(s[l, t] for l in L))
        for j in J:
            delivered = sum((1 - data["phi"][l]) * s[l, t] for l in data["L_j"][j])
            stored = sum(qout[f, t] - qin[f, t] for f in data["F_j"][j])
            equal(f"DM[{j},{t}]", delivered + stored + u[j, t], data["D"][j, t])
        for l in L:
            upper(f"PC[{l},{t}]", s[l, t], data["days"][t] * capacity[l])
        for f in F:
            previous = data["I0"][f] if t == T[0] else inventory[f, t - 1]
            equal(f"IB[{f},{t}]", inventory[f, t], previous + qin[f, t] - qout[f, t])
            upper(f"SL_cap[{f},{t}]", inventory[f, t], data["Ibar"][f])
            upper(f"SL_in[{f},{t}]", qin[f, t], data["days"][t] * data["r_in"][f])
            upper(f"SL_out[{f},{t}]", qout[f, t], data["days"][t] * data["r_out"][f])
    for l in L:
        upper(f"KC[{l}]", capacity[l], data["kbar"][l])
    for f in F:
        equal(f"CI[{f}]", inventory[f, T[-1]], data["I0"][f])
    costs = {
        "purchase": sum(data["P"][t] * x[t] for t in T),
        "pipeline_usage": sum(data["c"][l] * s[l, t] for l in L for t in T),
        "storage_fees": sum(data["c_in"][f] * qin[f, t] + data["c_out"][f] * qout[f, t] for f in F for t in T),
        "spot": sum(data["pi"][j, t] * u[j, t] for j in J for t in T),
        "reservation": sum(len(T) * data["R"][l] * capacity[l] for l in L),
    }
    if check_values("costs", solution.get("costs"), set(costs), problems):
        for name, value in costs.items():
            equal(f"costs[{name}]", solution["costs"][name], value)
    if check_values("objective", {"total": solution.get("objective")}, {"total"}, problems):
        equal("objective", solution["objective"], sum(costs.values()))
    summer, winter = range(1, 8), range(8, 13)
    for name, values, preferred in [("injections", qin, summer), ("withdrawals", qout, winter)]:
        total = sum(values.values())
        if total > tol and sum(value for (f, t), value in values.items() if t in preferred) < total / 2:
            warnings.warn(f"Most storage {name} occur outside the expected season; inspect prices and constraints.", stacklevel=2)
    if sum(u.values()) > tol and sum(value for (j, t), value in u.items() if t in winter) < sum(u.values()) / 2:
        warnings.warn("Most local purchases occur outside November–March; inspect costs and capacity.", stacklevel=2)
    return finish(problems)
