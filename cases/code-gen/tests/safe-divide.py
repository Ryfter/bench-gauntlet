def check(ns):
    f = ns.get("safe_divide")
    cases = [
        ((6, 2), 3.0),
        ((5, 0), None),
        ((-9, 3), -3.0),
        ((0, 5), 0.0),
        ((0, 0), None),
        ((1, 3), 1 / 3),
    ]
    results = []
    for args, expected in cases:
        try:
            got = f(*args)
            if expected is None:
                results.append(got is None)
            else:
                results.append(got is not None and abs(got - expected) < 1e-9)
        except Exception:
            results.append(False)
    return results
