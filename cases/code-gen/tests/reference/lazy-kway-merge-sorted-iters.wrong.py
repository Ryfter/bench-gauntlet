def lazy_merge_sorted(*iterables):
    items = []
    origins = []
    for idx, iterable in enumerate(iterables):
        for v in iterable:
            items.append(v)
            origins.append(idx)
    n = len(items)
    for i in range(n):
        for j in range(0, n - i - 1):
            if items[j] > items[j + 1] or (
                items[j] == items[j + 1] and origins[j] > origins[j + 1]
            ):
                items[j], items[j + 1] = items[j + 1], items[j]
                origins[j], origins[j + 1] = origins[j + 1], origins[j]
    for v in items:
        yield v
