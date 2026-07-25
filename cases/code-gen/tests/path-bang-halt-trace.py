def check(ns):
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: ns.get("ANSWER_1") == 3),
        t(lambda: ns.get("ANSWER_2") == 1),
        t(lambda: ns.get("ANSWER_3") == 0),
        t(lambda: ns.get("ANSWER_4") == 0),
        t(lambda: ns.get("ANSWER_5") == 2),
        t(lambda: ns.get("ANSWER_6") == 0),
        t(lambda: ns.get("ANSWER_7") == -1),
        t(lambda: ns.get("ANSWER_8") == 1),
        t(lambda: ns.get("ANSWER_9") == 0),
        t(lambda: ns.get("ANSWER_10") == 0),
    ]
