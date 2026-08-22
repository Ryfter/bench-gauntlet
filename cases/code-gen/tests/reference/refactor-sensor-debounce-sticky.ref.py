def debounce_series(readings, window, fault_hold):
    if readings is None:
        return []
    w = 1 if window is None or window < 1 else int(window)
    fh = w if fault_hold is None or fault_hold < 1 else int(fault_hold)

    def classify(r):
        if r > 200:
            return "fault"
        if r > 100:
            return "warn"
        return "ok"

    out = []
    state = "ok"
    pending = None
    pend_count = 0
    good_streak = 0
    for r in readings:
        if r is None:
            out.append(state)
            pending = None
            pend_count = 0
            continue
        raw = classify(r)
        if state == "fault":
            if raw == "ok":
                good_streak += 1
                if good_streak >= fh:
                    state = "ok"
                    good_streak = 0
                    pending = None
                    pend_count = 0
            else:
                good_streak = 0
            out.append(state)
            continue
        good_streak = 0
        if raw == state:
            pending = None
            pend_count = 0
        else:
            if raw == pending:
                pend_count += 1
            else:
                pending = raw
                pend_count = 1
            if pend_count >= w:
                state = pending
                pending = None
                pend_count = 0
        out.append(state)
    return out
