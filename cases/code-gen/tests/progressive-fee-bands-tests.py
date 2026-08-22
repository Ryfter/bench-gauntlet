# GAUNTLET-CANARY-54204ba95494
def check(ns):
    ts = ns.get("test_suite")
    if not callable(ts):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def correct(weight, brackets):
        if weight <= 0 or not brackets:
            return 0
        rem = int(weight)
        total = 0
        for i, (cap, rate) in enumerate(brackets):
            if rem <= 0:
                break
            if i < len(brackets) - 1:
                take = min(rem, max(0, int(cap)))
            else:
                take = rem
            total += take * int(rate)
            rem -= take
        return total
    def buggy_flat_landing(weight, brackets):
        if weight <= 0 or not brackets:
            return 0
        rem = weight
        for i, (cap, rate) in enumerate(brackets):
            if i < len(brackets) - 1:
                if rem <= cap:
                    return weight * rate
                rem -= cap
            else:
                return weight * rate
        return 0
    def buggy_no_absorb(weight, brackets):
        if weight <= 0 or not brackets:
            return 0
        rem = int(weight)
        total = 0
        for cap, rate in brackets:
            take = min(rem, max(0, int(cap)))
            total += take * int(rate)
            rem -= take
            if rem <= 0:
                break
        return total
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
        t(lambda: run(buggy_flat_landing) is not None),
        t(lambda: not all(run(buggy_flat_landing))),
        t(lambda: run(buggy_no_absorb) is not None and not all(run(buggy_no_absorb))),
        t(lambda: sum(1 for x in run(buggy_flat_landing) if not x) >= 1),
        t(lambda: all(run(correct)) and len(run(correct)) >= 5),
        t(lambda: (lambda r: r is not None and any(r) and not all(r))(run(buggy_flat_landing))),
        t(lambda: all(run(correct)) and not all(run(buggy_flat_landing)) and not all(run(buggy_no_absorb))),
    ]
