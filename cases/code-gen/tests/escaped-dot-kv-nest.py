# GAUNTLET-CANARY-6d920f3e10a7
def check(ns):
    f = ns.get("parse_nested_kv")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("a=1") == {"a": "1"}),
        t(lambda: f("a=1;b=2") == {"a": "1", "b": "2"}),
        t(lambda: f("user.name=ada") == {"user": {"name": "ada"}}),
        t(lambda: f("a.b.c=x") == {"a": {"b": {"c": "x"}}}),
        t(lambda: f("a=;b=2") == {"a": "", "b": "2"}),
        t(lambda: f("") == {}),
        t(lambda: f("a.b=1;a.c=2") == {"a": {"b": "1", "c": "2"}}),
        t(lambda: f("a=1;a=2") == {"a": "2"}),
        t(lambda: f("eq\\=ual=v") == {"eq=ual": "v"}),
        t(lambda: f("x\\.y=z") == {"x.y": "z"}),
    ]
