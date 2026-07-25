def check(ns):
    f = ns.get("dispatch_orders")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([('only', 5, 1)], 1) == [['only']]),
        t(lambda: f([], 3) == [[], [], []]),
        t(lambda: f([('a', 4, 1), ('b', 4, 2)], 1) == [['b', 'a']]),
        t(lambda: f([('a', 5, 1), ('b', 3, 2), ('c', 3, 2)], 2) == [['b', 'a'], ['c']]),
        t(lambda: f([('x', 1, 5), ('y', 1, 5), ('z', 1, 5)], 2) == [['x', 'z'], ['y']]),
        t(lambda: f([('late', 10, 1), ('early', 2, 9)], 2) == [['early'], ['late']]),
        t(lambda: f([('p', 3, 1), ('q', 3, 1), ('r', 3, 1), ('s', 3, 1)], 2) == [['p', 'r'], ['q', 's']]),
        t(lambda: f([('aa', 1, 1), ('ab', 1, 1)], 2) == [['aa'], ['ab']]),
        t(lambda: f([('slow', 100, 5), ('fast', 1, 5), ('mid', 10, 5)], 1) == [['fast', 'mid', 'slow']]),
        t(lambda: f([('c0', 5, 3), ('c1', 5, 3), ('c2', 5, 1)], 3) == [['c0'], ['c1'], ['c2']]),
    ]
