def check(ns):
    f = ns.get("intervals_overlap")
    g = ns.get("find_conflicts")
    if not callable(f) or not callable(g):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    S = [{"id": "A", "start": 0, "end": 100}, {"id": "B", "start": 100, "end": 200}, {"id": "C", "start": 50, "end": 150}]
    S2 = [{"id": "z", "start": 0, "end": 50}, {"id": "a", "start": 49, "end": 100}, {"id": "m", "start": 100, "end": 150}]
    S3 = [{"id": "p", "start": 10, "end": 20}, {"id": "q", "start": 20, "end": 30}, {"id": "r", "start": 15, "end": 25}]
    S4 = [{"id": "n1", "start": 0, "end": 1}, {"id": "n2", "start": 1, "end": 2}, {"id": "n3", "start": 2, "end": 3}]
    return [
        t(lambda: f(0, 10, 5, 15) is True),
        t(lambda: f(0, 5, 10, 20) is False),
        t(lambda: f(10, 50, 0, 100) is True),
        t(lambda: f(5, 5, 0, 10) is False),
        t(lambda: f(0, 10, 0, 10) is True),
        t(lambda: g([]) == []),
        t(lambda: g([{"id": "X", "start": 0, "end": 10}]) == []),
        t(lambda: f(0, 10, 10, 20) is False),
        t(lambda: g(S) == [("A", "C"), ("B", "C")]),
        t(lambda: g(S3) == [("p", "r"), ("q", "r")] and g(S4) == [] and g(S2) == [("a", "z")]),
    ]
