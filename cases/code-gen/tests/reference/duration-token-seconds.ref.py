def duration_to_seconds(s):
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    order = {"d": 0, "h": 1, "m": 2, "s": 3}
    if not s:
        return -1
    total = 0
    i = 0
    last_ord = -1
    seen = set()
    while i < len(s):
        if not s[i].isdigit():
            return -1
        j = i
        while j < len(s) and s[j].isdigit():
            j += 1
        if j == i or j >= len(s) or s[j] not in units:
            return -1
        u = s[j]
        if u in seen or order[u] <= last_ord:
            return -1
        seen.add(u)
        last_ord = order[u]
        total += int(s[i:j]) * units[u]
        i = j + 1
    return total
