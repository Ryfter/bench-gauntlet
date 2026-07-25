def check(ns):
    f = ns.get('TwoPhaseCommitLog')
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def a0():
        log = f()
        return log.begin('t1') is True and log.status('t1') == 'active'
    def a1():
        log = f()
        log.begin('t1')
        log.prepare('t1', 'k', 'v')
        log.commit('t1')
        return log.get('k') == 'v' and log.status('t1') == 'committed'
    def a2():
        log = f()
        log.begin('t1')
        log.prepare('t1', 'a', '1')
        log.abort('t1')
        return log.get('a') is None and log.status('t1') == 'aborted'
    def a3():
        log = f()
        return log.get('missing') is None and log.status('nope') == 'unknown'
    def a4():
        log = f()
        log.begin('t1')
        log.commit('t1')
        return (
            log.prepare('t1', 'k', 'v') is False
            and log.commit('t1') is False
            and log.abort('t1') is False
        )
    def a5():
        log = f()
        log.begin('t1')
        return log.begin('t1') is False
    def a6():
        log = f()
        log.begin('t1')
        log.prepare('t1', 'k', 'secret')
        # staged must not be visible
        return log.get('k') is None
    def a7():
        log = f()
        log.begin('t1')
        log.prepare('t1', 'k', 'old')
        log.commit('t1')
        log.begin('t2')
        log.prepare('t2', 'k', 'new')
        # still committed old while t2 active
        visible = log.get('k') == 'old'
        log.abort('t2')
        return visible and log.get('k') == 'old'
    def a8():
        log = f()
        log.begin('t1')
        log.prepare('t1', 'x', '1')
        log.prepare('t1', 'x', '2')
        log.prepare('t1', 'y', '3')
        log.commit('t1')
        return log.get('x') == '2' and log.get('y') == '3'
    def a9():
        log = f()
        log.begin('a')
        log.begin('b')
        log.prepare('a', 'k', 'A')
        log.prepare('b', 'k', 'B')
        log.prepare('b', 'm', 'M')
        log.commit('b')
        c1 = log.get('k') == 'B' and log.get('m') == 'M'
        log.commit('a')
        # a commits later and overwrites k
        c2 = log.get('k') == 'A' and log.get('m') == 'M'
        c3 = log.begin('a') is False and log.begin('b') is False
        c4 = log.prepare('ghost', 'z', '1') is False
        return c1 and c2 and c3 and c4
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
