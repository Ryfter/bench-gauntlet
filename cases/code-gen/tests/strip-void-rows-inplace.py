def check(ns):
    f = ns.get("strip_void_rows")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def run(inp):
        rows = list(inp)
        out = f(rows)
        return out is rows and rows == [r for r in inp if r.strip() != ""]
    return [
        t(lambda: run(["a", "b"])),
        t(lambda: run(["a", "", "b"])),
        t(lambda: run(["", "x"])),
        t(lambda: run(["x", ""])),
        t(lambda: run([])),
        t(lambda: run(["", "", ""])),
        t(lambda: run(["  ", "ok"])),
        t(lambda: run(["a", "  ", "b", "\t"])),
        t(lambda: run(["", "a", "", "b", ""])),
        t(lambda: run([" keep space ", "\n", "z"])),
    ]
