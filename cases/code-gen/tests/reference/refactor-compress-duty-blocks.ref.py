def compress_duty_blocks(blocks, max_gap):
    if max_gap is None or max_gap < 0:
        return None
    if blocks is None:
        return None
    cleaned = []
    for b in blocks:
        if not isinstance(b, (list, tuple)) or len(b) != 3:
            continue
        s, e, r = b
        if s is None or e is None or r is None:
            continue
        if type(s) is not int or type(e) is not int:
            continue
        if s >= e:
            continue
        cleaned.append((s, e, r))
    cleaned.sort(key=lambda x: (x[0], x[1], str(x[2])))
    if not cleaned:
        return []
    out = [[cleaned[0][0], cleaned[0][1], cleaned[0][2]]]
    for s, e, r in cleaned[1:]:
        ps, pe, pr = out[-1]
        if r == pr and s <= pe + max_gap:
            out[-1][1] = max(pe, e)
        else:
            out.append([s, e, r])
    return [(x[0], x[1], x[2]) for x in out]
