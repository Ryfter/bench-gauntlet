def circular_shift_inplace(xs, k):
    n = len(xs)
    if n == 0:
        return xs
    k = abs(k)
    while k >= n:
        k -= n
    if k == 0:
        return xs
    xs[:] = xs[k:] + xs[:k]
    return xs
