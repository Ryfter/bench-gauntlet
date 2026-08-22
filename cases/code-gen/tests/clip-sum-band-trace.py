# GAUNTLET-CANARY-7748dd83aa8e
def check(ns):
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: ns.get("ANSWER_1") == 6),
        t(lambda: ns.get("ANSWER_2") == 6),
        t(lambda: ns.get("ANSWER_3") == 0),
        t(lambda: ns.get("ANSWER_4") == 0),
        t(lambda: ns.get("ANSWER_5") == 5),
        t(lambda: ns.get("ANSWER_6") == 1),
        t(lambda: ns.get("ANSWER_7") == 6),
        t(lambda: ns.get("ANSWER_8") == 0),
        t(lambda: ns.get("ANSWER_9") == 11),
        t(lambda: ns.get("ANSWER_10") == 24),
    ]
