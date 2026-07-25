def check(ns):
    f = ns.get('PinnedLRUCache')
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def a0():
        c = f(2)
        return c.put('a', 1) is True and c.get('a') == 1
    def a1():
        c = f(3)
        c.put('a', 1)
        c.put('b', 2)
        return c.size() == 2 and c.pinned_count() == 0
    def a2():
        c = f(2)
        c.put('a', 1)
        c.put('a', 9)
        return c.get('a') == 9 and c.size() == 1
    def a3():
        c = f(2)
        c.put('a', 1)
        c.put('b', 2)
        c.put('c', 3)  # evicts a (LRU)
        return c.get('a') is None and c.get('b') == 2 and c.get('c') == 3
    def a4():
        c = f(2)
        c.put('a', 1)
        c.put('b', 2)
        c.get('a')  # a becomes MRU; b is LRU
        c.put('c', 3)  # evicts b
        return c.get('b') is None and c.get('a') == 1 and c.get('c') == 3
    def a5():
        c = f(2)
        c.put('a', 1)
        return c.pin('a') is True and c.pin('missing') is False and c.pinned_count() == 1
    def a6():
        c = f(2)
        c.put('a', 1)
        c.put('b', 2)
        c.pin('a')
        c.put('c', 3)  # must evict b, not pinned a
        return c.get('a') == 1 and c.get('b') is None and c.get('c') == 3 and c.pinned_count() == 1
    def a7():
        c = f(2)
        c.put('a', 1)
        c.put('b', 2)
        c.pin('a')
        c.pin('b')
        return c.put('c', 3) is False and c.size() == 2 and c.get('a') == 1 and c.get('b') == 2
    def a8():
        c = f(2)
        c.put('a', 1)
        c.put('b', 2)
        c.pin('a')
        c.pin('b')
        ok = c.unpin('a') is True and c.unpin('a') is False
        c.put('c', 3)  # a unpinned and LRU among unpinned? both a,b present; a unpinned, b pinned
        # only a is unpinned so a is evicted
        return ok and c.get('a') is None and c.get('b') == 2 and c.get('c') == 3 and c.pinned_count() == 1
    def a9():
        c = f(3)
        c.put('a', 1)
        c.put('b', 2)
        c.put('d', 4)
        c.pin('b')
        c.get('a')  # order LRU->MRU among unpinned matters: after get a, recency a MRU
        # residents insertion order with moves: start a,b,d; pin b; get a -> a MRU
        # LRU unpinned is d (b pinned, a most recent unpinned)
        c.put('e', 5)  # evict d
        c1 = c.get('d') is None and c.get('b') == 2 and c.get('a') == 1 and c.get('e') == 5
        c.put('b', 20)  # update pinned b, stays pinned, becomes MRU
        c2 = c.get('b') == 20 and c.pinned_count() == 1 and c.size() == 3
        c.unpin('b')
        c.pin('e')
        c.put('f', 6)
        c.put('g', 7)  # capacity 3; need two evictions across puts
        # after unpin b, pin e: keys a,b,e with e pinned
        # put f: evict LRU unpinned. Order: after put b as MRU then unpin: need careful
        # Re-run compact scripted sequence from clean state for final invariant:
        c = f(3)
        c.put('x', 1)
        c.put('y', 2)
        c.put('z', 3)
        c.pin('x')
        c.pin('y')
        # full and 2 pinned; z is only unpinned LRU
        c.put('w', 4)  # evict z
        c3 = c.get('z') is None and c.get('x') == 1 and c.get('y') == 2 and c.get('w') == 4
        c.pin('w')  # all three pinned
        c4 = c.put('q', 9) is False and c.size() == 3
        c.unpin('x')
        c.put('q', 9)  # evict x
        c5 = c.get('x') is None and c.get('q') == 9 and c.pinned_count() == 2
        return c1 and c2 and c3 and c4 and c5
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
