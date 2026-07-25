def check(ns):
    f = ns.get("rank_ready_parcels")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    as_of = "2024-06-15T12:00:00"
    return [
        t(lambda: f("tracking,zone,ready_at,weight\nA,1,2024-06-15T10:00:00,2.5\n", as_of) == ["A"]),
        t(lambda: f("tracking,zone,ready_at,weight\nB,2,2024-06-15T09:00:00,1\nA,1,2024-06-15T09:00:00,1\n", as_of) == ["A", "B"]),
        t(lambda: f("tracking,zone,ready_at,weight\n", as_of) == []),
        t(lambda: f("tracking,zone,ready_at,weight\nX,1,2024-06-15T13:00:00,5\n", as_of) == []),
        t(lambda: f("tracking,zone,ready_at,weight\nEq,1,2024-06-15T12:00:00,1\n", as_of) == ["Eq"]),
        t(lambda: f("tracking,zone,ready_at,weight\nH,1,2024-06-15T08:00:00,10\nL,1,2024-06-15T08:00:00,2\n", as_of) == ["H", "L"]),
        t(lambda: f("tracking,zone,ready_at,weight\nM,1,2024-06-15T08:00:00,10\nH,1,2024-06-15T08:00:00,10\n", as_of) == ["H", "M"]),
        t(lambda: f("tracking,zone,ready_at,weight\n ,1,2024-06-15T08:00:00,1\nZ,1,2024-06-15T08:00:00,0\nBad,x,nope,y\nOK,3,2024-06-15T08:00:00,4\n", as_of) == ["OK"]),
        t(lambda: f('tracking,zone,ready_at,weight\n"Q,1",2,2024-06-15T07:00:00,3.5\nP,2,2024-06-15T07:00:00,3.5\n', as_of) == ["P", "Q,1"]),
        t(lambda: f("tracking,zone,ready_at,weight\nC,1,2024-06-14T23:59:59,1\nD,1,2024-06-15T12:00:01,99\nE,0,2024-06-15T00:00:00,5\nF,0,2024-06-15T00:00:00,7\n", as_of) == ["F", "E", "C"]),
    ]
