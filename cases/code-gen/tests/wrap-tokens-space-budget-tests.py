def check(ns):
    ts = ns.get("test_suite")
    if not callable(ts):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def correct(words, width):
        if not words:
            return []
        lines = []
        cur = []
        cur_len = 0
        for w in words:
            if not cur:
                cur = [w]
                cur_len = len(w)
                continue
            if cur_len + 1 + len(w) <= width:
                cur.append(w)
                cur_len += 1 + len(w)
            else:
                lines.append(" ".join(cur))
                cur = [w]
                cur_len = len(w)
        if cur:
            lines.append(" ".join(cur))
        return lines
    def buggy_no_space_cost(words, width):
        if not words:
            return []
        lines = []
        cur = []
        cur_len = 0
        for w in words:
            if not cur:
                cur = [w]
                cur_len = len(w)
                continue
            if cur_len + len(w) <= width:
                cur.append(w)
                cur_len += 1 + len(w)
            else:
                lines.append(" ".join(cur))
                cur = [w]
                cur_len = len(w)
        if cur:
            lines.append(" ".join(cur))
        return lines
    def buggy_drop_long(words, width):
        if not words:
            return []
        lines = []
        cur = []
        cur_len = 0
        for w in words:
            if len(w) > width:
                if cur:
                    lines.append(" ".join(cur))
                    cur = []
                    cur_len = 0
                continue
            if not cur:
                cur = [w]
                cur_len = len(w)
                continue
            if cur_len + 1 + len(w) <= width:
                cur.append(w)
                cur_len += 1 + len(w)
            else:
                lines.append(" ".join(cur))
                cur = [w]
                cur_len = len(w)
        if cur:
            lines.append(" ".join(cur))
        return lines
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
        t(lambda: run(buggy_no_space_cost) is not None),
        t(lambda: not all(run(buggy_no_space_cost))),
        t(lambda: run(buggy_drop_long) is not None and not all(run(buggy_drop_long))),
        t(lambda: sum(1 for x in run(buggy_no_space_cost) if not x) >= 1),
        t(lambda: all(run(correct)) and len(run(correct)) >= 5),
        t(lambda: (lambda r: r is not None and any(r) and not all(r))(run(buggy_no_space_cost))),
        t(lambda: all(run(correct)) and not all(run(buggy_no_space_cost)) and not all(run(buggy_drop_long))),
    ]
