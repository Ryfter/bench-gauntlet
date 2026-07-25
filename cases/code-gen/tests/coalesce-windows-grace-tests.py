def check(ns):
    ts = ns.get("test_suite")
    if not callable(ts):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def correct(intervals, grace):
        valid = [(s, e) for s, e in intervals if s < e]
        if not valid:
            return []
        valid.sort(key=lambda x: (x[0], x[1]))
        out = [list(valid[0])]
        for s, e in valid[1:]:
            if s <= out[-1][1] + grace:
                out[-1][1] = max(out[-1][1], e)
            else:
                out.append([s, e])
        return [(a, b) for a, b in out]
    def buggy_ignore_grace(intervals, grace):
        valid = [(s, e) for s, e in intervals if s < e]
        if not valid:
            return []
        valid.sort(key=lambda x: (x[0], x[1]))
        out = [list(valid[0])]
        for s, e in valid[1:]:
            if s <= out[-1][1]:
                out[-1][1] = max(out[-1][1], e)
            else:
                out.append([s, e])
        return [(a, b) for a, b in out]
    def buggy_grace_plus_one(intervals, grace):
        valid = [(s, e) for s, e in intervals if s < e]
        if not valid:
            return []
        valid.sort(key=lambda x: (x[0], x[1]))
        out = [list(valid[0])]
        for s, e in valid[1:]:
            if s <= out[-1][1] + grace + 1:
                out[-1][1] = max(out[-1][1], e)
            else:
                out.append([s, e])
        return [(a, b) for a, b in out]
    def run(impl):
        out = ts(impl)
        if not isinstance(out, list) or not out:
            return None
        if not all(isinstance(x, bool) for x in out):
            return None
        return out
    return [
        t(lambda: run(correct) is not None),
        t(lambda: len(run(correct)) >= 3),
        t(lambda: all(run(correct))),
        t(lambda: run(buggy_ignore_grace) is not None),
        t(lambda: not all(run(buggy_ignore_grace))),
        t(lambda: run(buggy_grace_plus_one) is not None and not all(run(buggy_grace_plus_one))),
        t(lambda: sum(1 for x in run(buggy_ignore_grace) if not x) >= 1),
        t(lambda: all(run(correct)) and len(run(correct)) >= 5),
        t(lambda: (lambda r: r is not None and any(r) and not all(r))(run(buggy_ignore_grace))),
        t(lambda: all(run(correct)) and not all(run(buggy_ignore_grace)) and not all(run(buggy_grace_plus_one))),
    ]
