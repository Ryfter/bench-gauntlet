# GAUNTLET-CANARY-77fe3eafe520
def check(ns):
    C = ns.get("PatchJournal")
    if not callable(C):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def a0():
        j = C()
        return j.value() == 0 and j.apply(5) == 5 and j.value() == 5
    def a1():
        j = C(10)
        return j.set(3) == 3 and j.value() == 3
    def a2():
        j = C()
        j.apply(4)
        return j.undo() is True and j.value() == 0
    def a3():
        j = C()
        j.apply(4)
        j.undo()
        return j.redo() is True and j.value() == 4
    def a4():
        j = C()
        return j.undo() is False and j.redo() is False
    def a5():
        j = C()
        j.apply(1)
        j.apply(2)
        j.apply(3)
        j.undo()
        j.undo()
        return j.value() == 1 and j.undo() is True and j.value() == 0
    def a6():
        j = C()
        j.apply(10)
        j.apply(20)
        j.undo()
        j.redo()
        j.redo()
        return j.value() == 30 and j.redo() is False
    def a7():
        j = C()
        j.apply(1)
        j.apply(2)
        j.apply(3)
        j.undo()
        j.undo()
        j.apply(100)
        return j.value() == 101 and j.redo() is False and j.undo() is True and j.value() == 1
    def a8():
        j = C()
        j.set(5)
        j.set(8)
        j.apply(-3)
        j.undo()
        j.apply(1)
        return (
            j.value() == 9
            and j.redo() is False
            and j.undo() is True
            and j.value() == 8
            and j.undo() is True
            and j.value() == 5
        )
    def a9():
        j = C(0)
        for d in (5, -2, 10, -7, 3):
            j.apply(d)
        if j.value() != 9:
            return False
        j.undo()
        j.undo()
        j.undo()
        if j.value() != 3:
            return False
        j.apply(50)
        if j.redo() is not False or j.value() != 53:
            return False
        j.undo()
        j.undo()
        if j.value() != 5:
            return False
        j.redo()
        if j.value() != 3:
            return False
        j.redo()
        if j.value() != 53:
            return False
        return j.redo() is False
    return [
        t(lambda: a0()), t(lambda: a1()), t(lambda: a2()), t(lambda: a3()), t(lambda: a4()),
        t(lambda: a5()), t(lambda: a6()), t(lambda: a7()), t(lambda: a8()), t(lambda: a9()),
    ]
