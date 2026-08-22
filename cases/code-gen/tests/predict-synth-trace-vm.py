# GAUNTLET-CANARY-467627ca5f1c
def check(ns):
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: ns.get("ANSWER_1") == 8),
        t(lambda: ns.get("ANSWER_2") == 4),
        t(lambda: ns.get("ANSWER_3") == 10),
        t(lambda: ns.get("ANSWER_4") == 9),
        t(lambda: ns.get("ANSWER_5") == 0),
        t(lambda: ns.get("ANSWER_6") == -6),
        t(lambda: ns.get("ANSWER_7") == 14),
        t(lambda: ns.get("ANSWER_8") == 105),
        t(lambda: ns.get("ANSWER_9") == 3),
        t(lambda: ns.get("ANSWER_10") == -4),
    ]
