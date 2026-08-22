def check(ns):
    is_prime = ns.get("is_prime")
    nth_prime = ns.get("nth_prime")
    results = []

    for n, expected in ((0, False), (1, False), (2, True), (3, True), (4, False),
                        (17, True), (18, False)):
        try:
            results.append(is_prime(n) == expected)
        except Exception:
            results.append(False)

    for n, expected in ((1, 2), (2, 3), (3, 5), (6, 13), (10, 29)):
        try:
            results.append(nth_prime(n) == expected)
        except Exception:
            results.append(False)

    try:
        nth_prime(0)
        results.append(False)  # should have raised
    except ValueError:
        results.append(True)
    except Exception:
        results.append(False)

    return results
