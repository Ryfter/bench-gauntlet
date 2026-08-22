def shortest_k_variety(items, k):
    if k <= 0 or not items:
        return 0
    seen = set()
    for i, x in enumerate(items):
        seen.add(x)
        if len(seen) >= k:
            return i + 1
    return 0
