# GAUNTLET-CANARY-218ffc6c84fe
def check(ns):
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: ns.get("ANSWER_1") == 31),
        t(lambda: ns.get("ANSWER_2") == 42),
        t(lambda: ns.get("ANSWER_3") == 0),
        t(lambda: ns.get("ANSWER_4") == 0),
        t(lambda: ns.get("ANSWER_5") == 0),
        t(lambda: ns.get("ANSWER_6") == 9),
        t(lambda: ns.get("ANSWER_7") == -531),
        t(lambda: ns.get("ANSWER_8") == 200),
        t(lambda: ns.get("ANSWER_9") == 20),
        t(lambda: ns.get("ANSWER_10") == -2),
    ]
