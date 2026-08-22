def restock_flag(qty, days):
    if qty is None or days is None:
        return "unknown"
    if qty < 0 or days < 0:
        return "bad"
    if qty == 0:
        return "critical"
    # (qty_hi_inclusive, [(days_hi_inclusive, level), ...]) last days band is else
    bands = [
        (5, [(2, "critical"), (7, "high"), (None, "medium")]),
        (20, [(2, "high"), (7, "medium"), (None, "low")]),
        (None, [(1, "medium"), (None, "low")]),
    ]
    for qmax, day_rows in bands:
        if qmax is None or qty <= qmax:
            for dmax, level in day_rows:
                if dmax is None or days <= dmax:
                    return level
    return "low"
