def check(ns):
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: ns.get("ANSWER_1") == [[1, 5]]),
        t(lambda: ns.get("ANSWER_2") == [[1, 2], [3, 4]]),
        t(lambda: ns.get("ANSWER_3") == []),
        t(lambda: ns.get("ANSWER_4") == [[1, 2], [5, 6]]),
        t(lambda: ns.get("ANSWER_5") == [[1, 5]]),
        t(lambda: ns.get("ANSWER_6") == [[1, 3]]),
        t(lambda: ns.get("ANSWER_7") == [[0, 1]]),
        t(lambda: ns.get("ANSWER_8") == [[0, 5]]),
        t(lambda: ns.get("ANSWER_9") == [[2, 2]]),
        t(lambda: ns.get("ANSWER_10") == [[10, 14], [15, 15]]),
    ]
