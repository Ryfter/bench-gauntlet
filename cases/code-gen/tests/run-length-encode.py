def check(ns):
    f = ns.get("run_length_encode")
    cases = [
        ("", ""),
        ("a", "a1"),
        ("aaabbc", "a3b2c1"),
        ("aabbcc", "a2b2c2"),
        ("abcabc", "a1b1c1a1b1c1"),
        ("aaaaaaaaaa", "a10"),
    ]
    results = []
    for arg, expected in cases:
        try:
            results.append(f(arg) == expected)
        except Exception:
            results.append(False)
    return results
