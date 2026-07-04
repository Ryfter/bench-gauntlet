def check(ns):
    cls = ns.get("Inventory")
    results = []
    try:
        inv = cls()
        results.append(inv.count("widget") == 0)          # never added -> 0
        inv.add("widget", 5)
        results.append(inv.count("widget") == 5)
        results.append(inv.remove("widget", 2) is True)
        results.append(inv.count("widget") == 3)
        results.append(inv.remove("widget", 10) is False)  # insufficient stock
        results.append(inv.count("widget") == 3)           # unchanged on failed remove
        results.append(inv.remove("gadget", 1) is False)   # never-added item
        inv.add("widget", 1)
        results.append(inv.count("widget") == 4)
        inv.add("gadget", 2)
        results.append(inv.remove("gadget", 2) is True)
        results.append(inv.count("gadget") == 0)
    except Exception:
        # Any hard failure (missing method, wrong signature) fails every
        # remaining assertion rather than crashing the harness.
        results.extend([False] * (10 - len(results)))
    return results
