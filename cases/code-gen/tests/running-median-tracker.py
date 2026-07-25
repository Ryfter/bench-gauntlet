def check(ns):
    f = ns.get('RunningMedianTracker')
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def a0():
        m = f()
        m.add(10)
        return m.median() == 10.0 and m.count() == 1
    def a1():
        m = f()
        return m.median() is None and m.count() == 0
    def a2():
        m = f()
        for x in (3, 1, 2):
            m.add(x)
        return m.median() == 2.0 and m.count() == 3
    def a3():
        m = f()
        for x in (1, 2, 3, 4):
            m.add(x)
        return m.median() == 2.5
    def a4():
        m = f()
        m.add(5)
        m.add(5)
        return m.median() == 5.0 and m.remove(5) is True and m.count() == 1 and m.median() == 5.0
    def a5():
        m = f()
        m.add(1)
        return m.remove(2) is False and m.count() == 1 and m.remove(1) is True and m.median() is None
    def a6():
        m = f()
        for x in (-3, -1, -2, -8):
            m.add(x)
        # sorted -8,-3,-2,-1 -> mean of -3 and -2 = -2.5
        return m.median() == -2.5
    def a7():
        m = f()
        for x in (9, 1, 1, 1, 8):
            m.add(x)
        # sorted 1,1,1,8,9 -> median 1.0
        c1 = m.median() == 1.0
        m.remove(1)
        m.remove(1)
        # 1,8,9 -> 8.0
        c2 = m.median() == 8.0 and m.count() == 3
        return c1 and c2
    def a8():
        m = f()
        for x in (0, 100, -50, 25, 25, -50):
            m.add(x)
        # sorted -50,-50,0,25,25,100 -> mean 0 and 25 = 12.5
        c1 = m.median() == 12.5
        m.remove(-50)
        # -50,0,25,25,100 -> 25.0
        c2 = m.median() == 25.0
        m.remove(100)
        m.remove(25)
        # -50,0,25 -> 0.0
        c3 = m.median() == 0.0 and m.count() == 3
        return c1 and c2 and c3
    def a9():
        m = f()
        data = [4, 7, 1, 9, 2, 8, 3, 6, 5, 0]
        for x in data:
            m.add(x)
        # 0..9 -> mean 4 and 5 = 4.5
        c1 = m.median() == 4.5 and m.count() == 10
        for x in (0, 9, 1, 8):
            m.remove(x)
        # 2,3,4,5,6,7 -> mean 4 and 5 = 4.5
        c2 = m.median() == 4.5 and m.count() == 6
        m.remove(4)
        m.remove(5)
        # 2,3,6,7 -> mean 3 and 6 = 4.5
        c3 = m.median() == 4.5
        m.add(100)
        m.add(-100)
        # -100,2,3,6,7,100 -> mean 3 and 6 = 4.5
        c4 = m.median() == 4.5 and m.count() == 6
        m.remove(2)
        m.remove(3)
        m.remove(6)
        m.remove(7)
        # -100,100 -> 0.0
        c5 = m.median() == 0.0
        m.remove(-100)
        m.remove(100)
        c6 = m.median() is None and m.remove(0) is False and m.count() == 0
        return c1 and c2 and c3 and c4 and c5 and c6
    return [
        t(lambda: a0()),
        t(lambda: a1()),
        t(lambda: a2()),
        t(lambda: a3()),
        t(lambda: a4()),
        t(lambda: a5()),
        t(lambda: a6()),
        t(lambda: a7()),
        t(lambda: a8()),
        t(lambda: a9()),
    ]
