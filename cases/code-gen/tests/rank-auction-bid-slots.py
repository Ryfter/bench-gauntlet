# GAUNTLET-CANARY-c31be8170328
def check(ns):
    f = ns.get("rank_bid_slots")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([("alice", 100, 1), ("bob", 50, 2)], 1) == ["alice"]),
        t(lambda: f([("alice", 100, 1), ("bob", 200, 2)], 2) == ["bob", "alice"]),
        t(lambda: f([], 5) == []),
        t(lambda: f([("solo", 1, 0)], 0) == []),
        t(lambda: f([("solo", 42, 9)], 1) == ["solo"]),
        t(lambda: f([("x", 10, 5), ("y", 10, 3)], 2) == ["y", "x"]),
        t(lambda: f([("b", 10, 1), ("a", 10, 1)], 2) == ["a", "b"]),
        t(lambda: f([("alice", 50, 1), ("alice", 80, 2), ("bob", 70, 1)], 3) == ["alice", "bob"]),
        t(lambda: f([("a", -1, 1), ("b", -5, 1), ("c", 0, 1)], 3) == ["c", "a", "b"]),
        t(lambda: f([("z", 1, 9), ("m", 1, 9), ("y", 2, 8), ("y", 2, 100)], 10) == ["y", "m", "z"]),
    ]
