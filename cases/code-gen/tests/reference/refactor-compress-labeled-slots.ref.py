def compress_slots(slots):
    if not slots:
        return []
    items = []
    for s in slots:
        if s is None:
            continue
        try:
            if len(s) != 3:
                continue
        except TypeError:
            continue
        a, b, lab = s[0], s[1], s[2]
        if a is None or b is None or lab is None:
            continue
        try:
            a = int(a)
            b = int(b)
        except (TypeError, ValueError):
            continue
        if b <= a:
            continue
        items.append([a, b, lab])
    if not items:
        return []
    items.sort(key=lambda x: (x[0], x[1], str(x[2])))
    out = [items[0][:]]
    for a, b, lab in items[1:]:
        if lab == out[-1][2] and a <= out[-1][1]:
            if b > out[-1][1]:
                out[-1][1] = b
        else:
            out.append([a, b, lab])
    return [(a, b, lab) for a, b, lab in out]
