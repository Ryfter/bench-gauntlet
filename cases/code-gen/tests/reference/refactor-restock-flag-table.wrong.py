def restock_flag(qty, days):
    if qty is None or days is None:
        return "unknown"
    if qty < 0 or days < 0:
        return "bad"
    if qty == 0:
        return "critical"
    # off-by-one: strict < on qty band edges instead of <=
    if qty < 5:
        if days <= 2:
            return "critical"
        if days <= 7:
            return "high"
        return "medium"
    if qty < 20:
        if days <= 2:
            return "high"
        if days <= 7:
            return "medium"
        return "low"
    if days <= 1:
        return "medium"
    return "low"
