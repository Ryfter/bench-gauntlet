# GAUNTLET-CANARY-fcfcf0f249fc
def check(ns):
    f = ns.get("peak_day_totals")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("10/10/2024|a|5") == [["2024-10-10", 5]]),
        t(lambda: f("10/10/2024|a|5\n10/10/2024|b|3") == [["2024-10-10", 8]]),
        t(lambda: f("") == []),
        t(lambda: f("10/10/2024|a|5\n10/10/2024|b|-5") == []),
        t(lambda: f("10/10/2024 12:30|a|4") == [["2024-10-10", 4]]),
        t(lambda: f("01/01/2024|a|10\n02/01/2024|b|10") == [["2024-01-01", 10], ["2024-01-02", 10]]),
        t(lambda: f("01/01/2024|a|5\n02/01/2024|b|2") == [["2024-01-01", 5], ["2024-01-02", 2]]),
        t(lambda: f("03/04/2024|x|5\n04/03/2024|y|5\n03/04/2024 12:00|z|3") == [["2024-04-03", 8], ["2024-03-04", 5]]),
        t(lambda: f("badline\n15/01/2024|ok|7") == [["2024-01-15", 7]]),
        t(lambda: f("15/01/2024|a|-3\n15/01/2024|b|10") == [["2024-01-15", 7]]),
    ]
