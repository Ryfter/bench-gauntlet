def sliding_windows(items, size):
    if size <= 0:
        return
    n = len(items)
    if size > n:
        return
    for i in range(n - size + 1):
        yield items[i:i + size]
