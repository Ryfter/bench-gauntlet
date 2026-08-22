# GAUNTLET-CANARY-d996ed967a53
def check(ns):
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: ns.get("ANSWER_1") == (4, 2, 1)),
        t(lambda: ns.get("ANSWER_2") == (0, 0, 0)),
        t(lambda: ns.get("ANSWER_3") == (3, 0, 0)),
        t(lambda: ns.get("ANSWER_4") == (-9, 0, 3)),
        t(lambda: ns.get("ANSWER_5") == (1, 0, 2)),
        t(lambda: ns.get("ANSWER_6") == (-9, 2, 1)),
        t(lambda: ns.get("ANSWER_7") == (7, 1, 0)),
        t(lambda: ns.get("ANSWER_8") == (5, 1, 0)),
        t(lambda: ns.get("ANSWER_9") == (3, 0, 0)),
        t(lambda: ns.get("ANSWER_10") == (6, 1, 2)),
    ]
