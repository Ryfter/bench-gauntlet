def merge_half_open(intervals):
    cleaned = [(s, e) for s, e in intervals if s < e]
    if not cleaned:
        return []
    cleaned.sort()
    out = [cleaned[0]]
    for s, e in cleaned[1:]:
        ps, pe = out[-1]
        if s <= pe:
            out[-1] = (ps, max(pe, e))
        else:
            out.append((s, e))
    return out
