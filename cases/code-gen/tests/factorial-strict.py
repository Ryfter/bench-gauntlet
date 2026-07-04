def check(ns):
    f = ns.get("factorial")
    results = []

    for n, expected in ((0, 1), (1, 1), (5, 120), (10, 3628800), (20, 2432902008176640000)):
        try:
            results.append(f(n) == expected)
        except Exception:
            results.append(False)

    for n in (-1, -5):
        try:
            f(n)
            results.append(False)  # should have raised
        except ValueError:
            results.append(True)
        except Exception:
            results.append(False)

    return results
