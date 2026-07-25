def check(ns):
    f = ns.get("parse_shift_log")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("09:00 Alice IN\n17:30 Alice OUT") == [
            {"time": "09:00", "name": "Alice", "action": "IN"},
            {"time": "17:30", "name": "Alice", "action": "OUT"},
        ]),
        t(lambda: f("09:00 Bob IN") == [
            {"time": "09:00", "name": "Bob", "action": "IN"},
        ]),
        t(lambda: f("") == []),
        t(lambda: f("# ignore\n10:00 Eve IN\n# tail") == [
            {"time": "10:00", "name": "Eve", "action": "IN"},
        ]),
        t(lambda: f("\n\n09:15 Sam OUT\n") == [
            {"time": "09:15", "name": "Sam", "action": "OUT"},
        ]),
        t(lambda: f("10:00 Ada Lovelace IN") == [
            {"time": "10:00", "name": "Ada Lovelace", "action": "IN"},
        ]),
        t(lambda: f("09:00 A IN\r\n10:00 B OUT") == [
            {"time": "09:00", "name": "A", "action": "IN"},
            {"time": "10:00", "name": "B", "action": "OUT"},
        ]),
        t(lambda: f("09:00 A IN\r10:00 B OUT") == [
            {"time": "09:00", "name": "A", "action": "IN"},
            {"time": "10:00", "name": "B", "action": "OUT"},
        ]),
        t(lambda: f("25:00 Bad IN\n10:00 Ok IN") == [
            {"time": "10:00", "name": "Ok", "action": "IN"},
        ]),
        t(lambda: f("10:60 Bad IN\nnot a line\n08:05 Z OUT") == [
            {"time": "08:05", "name": "Z", "action": "OUT"},
        ]),
    ]
