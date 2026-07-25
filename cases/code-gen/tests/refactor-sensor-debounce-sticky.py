def check(ns):
    f = ns.get("debounce_series")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([], 2, 2) == []),
        t(lambda: f(None, 2, 2) == []),
        t(lambda: f([50, 50, 50], 2, 2) == ["ok", "ok", "ok"]),
        t(lambda: f([150, 150], 2, 2) == ["ok", "warn"]),
        t(lambda: f([150], 1, 1) == ["warn"]),
        t(lambda: f([250, 250], 2, 2) == ["ok", "fault"]),
        t(lambda: f([250, 250, 50, 50, 50], 2, 3) == ["ok", "fault", "fault", "fault", "ok"]),
        t(lambda: f([250, 250, 150, 150, 150], 2, 2) == ["ok", "fault", "fault", "fault", "fault"]),
        t(lambda: f([150, None, 150], 2, 2) == ["ok", "ok", "ok"]),
        t(lambda: f([100, 100, 200, 200], 2, 2) == ["ok", "ok", "ok", "warn"] and f([201, 201], 2, 2) == ["ok", "fault"]),
    ]
