# GAUNTLET-CANARY-87b916276102
def check(ns):
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: ns.get("ANSWER_1") == [[1, 5]]),
        t(lambda: ns.get("ANSWER_2") == [[1, 3], [4, 5]]),
        t(lambda: ns.get("ANSWER_3") == [[0, 2], [8, 10]]),
        t(lambda: ns.get("ANSWER_4") == []),
        t(lambda: ns.get("ANSWER_5") == [[0, 10]]),
        t(lambda: ns.get("ANSWER_6") == [[0, 10]]),
        t(lambda: ns.get("ANSWER_7") == [[2, 4]]),
        t(lambda: ns.get("ANSWER_8") == [[1, 5]]),
        t(lambda: ns.get("ANSWER_9") == [[1, 3], [5, 8]]),
        t(lambda: ns.get("ANSWER_10") == [[2, 9]]),
    ]
