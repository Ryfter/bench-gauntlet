def check(ns):
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: ns.get("ANSWER_1") == [0, 1]),
        t(lambda: ns.get("ANSWER_2") == [0, 2, 4]),
        t(lambda: ns.get("ANSWER_3") == []),
        t(lambda: ns.get("ANSWER_4") == []),
        t(lambda: ns.get("ANSWER_5") == [0, 1, 3]),
        t(lambda: ns.get("ANSWER_6") == [1, 2]),
        t(lambda: ns.get("ANSWER_7") == [0]),
        t(lambda: ns.get("ANSWER_8") == [0, 1, 4, 5]),
        t(lambda: ns.get("ANSWER_9") == [0, 1]),
        t(lambda: ns.get("ANSWER_10") == [0, 3, 4, 6, 7]),
    ]
