def coalesce_ranges(ranges):
    cleaned = [(a, b) for a, b in ranges if a < b]
    if not cleaned:
        return []
    cleaned.sort(key=lambda x: (x[0], x[1]))
    out = [list(cleaned[0])]
    for a, b in cleaned[1:]:
        if a < out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [tuple(x) for x in out]
