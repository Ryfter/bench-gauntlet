def check(ns):
    f = ns.get("transpose")
    cases = [
        ([], []),
        ([[]], []),
        ([[1, 2], [3, 4]], [[1, 3], [2, 4]]),
        ([[1, 2, 3]], [[1], [2], [3]]),
        ([[1], [2], [3]], [[1, 2, 3]]),
        ([[1, 2], [3, 4], [5, 6]], [[1, 3, 5], [2, 4, 6]]),
    ]
    results = []
    for arg, expected in cases:
        try:
            results.append(f(arg) == expected)
        except Exception:
            results.append(False)
    return results
