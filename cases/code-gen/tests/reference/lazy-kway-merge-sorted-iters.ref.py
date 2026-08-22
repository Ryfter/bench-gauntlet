def lazy_merge_sorted(*iterables):
    import heapq
    heap = []
    for idx, iterable in enumerate(iterables):
        it = iter(iterable)
        try:
            val = next(it)
        except StopIteration:
            continue
        heapq.heappush(heap, (val, idx, it))
    while heap:
        val, idx, it = heapq.heappop(heap)
        yield val
        try:
            nxt = next(it)
        except StopIteration:
            continue
        heapq.heappush(heap, (nxt, idx, it))
