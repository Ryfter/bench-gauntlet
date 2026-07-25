# GAUNTLET-CANARY-f99aa2209ff9
def check(ns):
    ts = ns.get("test_suite")
    if not callable(ts):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def correct(base, ops):
        d = dict(base)
        for sku, delta in ops:
            d[sku] = d.get(sku, 0) + delta
        return {k: v for k, v in d.items() if v != 0}
    def buggy_keep_zero(base, ops):
        d = dict(base)
        for sku, delta in ops:
            d[sku] = d.get(sku, 0) + delta
        return d
    def buggy_drop_neg(base, ops):
        d = dict(base)
        for sku, delta in ops:
            d[sku] = d.get(sku, 0) + delta
        return {k: v for k, v in d.items() if v > 0}
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
        t(lambda: run(buggy_keep_zero) is not None),
        t(lambda: not all(run(buggy_keep_zero))),
        t(lambda: run(buggy_drop_neg) is not None and not all(run(buggy_drop_neg))),
        t(lambda: sum(1 for x in run(buggy_keep_zero) if x is False) >= 1),
        t(lambda: all(run(correct)) and len(run(correct)) >= 4),
        t(lambda: (lambda r: r is not None and any(r) and not all(r))(run(buggy_keep_zero))),
        t(lambda: all(run(correct)) and not all(run(buggy_keep_zero)) and not all(run(buggy_drop_neg))),
    ]
