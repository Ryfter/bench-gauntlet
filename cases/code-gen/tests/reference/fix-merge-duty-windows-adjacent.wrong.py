def merge_duty_windows(windows):
    cleaned = [(s, e) for s, e in windows if s < e]
    if not cleaned:
        return []
    cleaned.sort(key=lambda w: (w[0], w[1]))
    out = [list(cleaned[0])]
    for s, e in cleaned[1:]:
        if s < out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [tuple(pair) for pair in out]
