# GAUNTLET-CANARY-fa41c0ec1540
def check(ns):
    ts = ns.get("test_suite")
    if not callable(ts):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def correct(items, max_units, max_skus):
        if not items:
            return []
        bags = []
        cur = []
        for sku in items:
            if not cur:
                cur = [sku]
                continue
            units_ok = len(cur) + 1 <= max_units
            dist = set(cur)
            skus_ok = sku in dist or len(dist) + 1 <= max_skus
            if units_ok and skus_ok:
                cur.append(sku)
            else:
                bags.append(cur)
                cur = [sku]
        if cur:
            bags.append(cur)
        return bags
    def buggy_units_only(items, max_units, max_skus):
        if not items:
            return []
        bags = []
        cur = []
        for sku in items:
            if not cur:
                cur = [sku]
                continue
            if len(cur) + 1 <= max_units:
                cur.append(sku)
            else:
                bags.append(cur)
                cur = [sku]
        if cur:
            bags.append(cur)
        return bags
    def buggy_skus_only(items, max_units, max_skus):
        if not items:
            return []
        bags = []
        cur = []
        for sku in items:
            if not cur:
                cur = [sku]
                continue
            dist = set(cur)
            skus_ok = sku in dist or len(dist) + 1 <= max_skus
            if skus_ok:
                cur.append(sku)
            else:
                bags.append(cur)
                cur = [sku]
        if cur:
            bags.append(cur)
        return bags
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
        t(lambda: run(buggy_units_only) is not None),
        t(lambda: not all(run(buggy_units_only))),
        t(lambda: run(buggy_skus_only) is not None and not all(run(buggy_skus_only))),
        t(lambda: sum(1 for x in run(buggy_units_only) if not x) >= 1),
        t(lambda: all(run(correct)) and len(run(correct)) >= 5),
        t(lambda: (lambda r: r is not None and any(r) and not all(r))(run(buggy_units_only))),
        t(lambda: all(run(correct)) and not all(run(buggy_units_only)) and not all(run(buggy_skus_only))),
    ]
