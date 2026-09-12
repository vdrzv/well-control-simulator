def pressure_limit_breaches(P_cs: float, casing_p: float, drillpipe_p: float, case_data: dict) -> list[dict]:
    """Return every pressure-limit breach detected after a simulation step."""
    checks = (
        ("conductor_fracture", "Conductor fracture pressure exceeded", P_cs, case_data.get("conductor_frac_pressure")),
        ("wellhead_pressure", "Maximum wellhead pressure exceeded", casing_p, case_data.get("max_wellhead_pressure")),
        ("pump_pressure", "Maximum pump pressure exceeded", drillpipe_p, case_data.get("max_pump_pressure")),
    )
    breaches = []
    for code, message, actual, limit in checks:
        if actual is None or limit is None:
            continue
        if float(actual) > float(limit):
            breaches.append({"code": code, "message": message, "actual": float(actual), "limit": float(limit)})
    return breaches


def capture_conductor_pressure(current: float, cumulative_volume: float, conductor_volume: float, pressure: float) -> float:
    """Capture pressure once, at the first cell crossing the conductor depth."""
    if current == -1 and cumulative_volume > conductor_volume:
        return float(pressure)
    return current
