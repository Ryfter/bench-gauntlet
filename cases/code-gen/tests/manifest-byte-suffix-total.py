# GAUNTLET-CANARY-722981cbcdfe
def check(ns):
    f = ns.get("total_payload_bytes")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("a|1|10") == 10),
        t(lambda: f("a|2|10") == 20),
        t(lambda: f("a|1|1KiB") == 1024),
        t(lambda: f("a|1|512B") == 512),
        t(lambda: f("a|3|2MiB") == 6291456),
        t(lambda: f("a|1|10\nb|2|5") == 20),
        t(lambda: f("a|1|10\n\nb|1|5") == 15),
        t(lambda: f("a|1|1KB") == 1000),
        t(lambda: f("a|1|1.5KB") == 1500),
        t(lambda: f("a|2|1MB") == 2000000),
    ]
