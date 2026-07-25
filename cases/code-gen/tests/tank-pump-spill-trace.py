def check(ns):
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: ns.get("ANSWER_1") == [1, 3, 6]),
        t(lambda: ns.get("ANSWER_2") == [5, 10, -5]),
        t(lambda: ns.get("ANSWER_3") == []),
        t(lambda: ns.get("ANSWER_4") == [3, 2, 4]),
        t(lambda: ns.get("ANSWER_5") == [2, 0, 1]),
        t(lambda: ns.get("ANSWER_6") == [-10]),
        t(lambda: ns.get("ANSWER_7") == [-15]),
        t(lambda: ns.get("ANSWER_8") == [8, -6, -8]),
        t(lambda: ns.get("ANSWER_9") == [0, 0]),
        t(lambda: ns.get("ANSWER_10") == [6, -2, 0, 4]),
    ]
