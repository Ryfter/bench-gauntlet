# GAUNTLET-CANARY-1f333b90df4f
def check(ns):
    f = ns.get("severity_rank")
    g = ns.get("alert_starts")
    if not callable(f) or not callable(g):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("info") == 1),
        t(lambda: f("  ERROR ") == 3),
        t(lambda: f("trace") == -1),
        t(lambda: g(["INFO", "ERROR", "INFO"], "ERROR", 1) == [1]),
        t(lambda: g(["INFO", "INFO"], "ERROR", 1) == []),
        t(lambda: g(["WARN"], "WARN", 1) == [0]),
        t(lambda: g(["INFO", "WARN", "ERROR"], "WARN", 2) == [0, 1]),
        t(lambda: g(["DEBUG", "DEBUG", "FATAL"], "ERROR", 2) == [1]),
        t(lambda: g([], "INFO", 1) == []),
        t(lambda: g(["error", "info", "fatal", "debug"], "FATAL", 3) == [0, 1]),
    ]
