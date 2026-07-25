def check(ns):
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: ns.get("ANSWER_1") == 7),
        t(lambda: ns.get("ANSWER_2") is None),
        t(lambda: ns.get("ANSWER_3") == 0),
        t(lambda: ns.get("ANSWER_4") == 6),
        t(lambda: ns.get("ANSWER_5") == 1),
        t(lambda: ns.get("ANSWER_6") is None),
        t(lambda: ns.get("ANSWER_7") == 0),
        t(lambda: ns.get("ANSWER_8") == 5),
        t(lambda: ns.get("ANSWER_9") == 0),
        t(lambda: ns.get("ANSWER_10") == 5),
    ]
