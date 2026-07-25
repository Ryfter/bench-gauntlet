def max_span_under(values, limit):
    best = 0
    left = 0
    s = 0
    for right in range(len(values)):
        s += values[right]
        while s > limit and left <= right:
            s -= values[left]
            left += 1
        if s <= limit:
            best = max(best, right - left + 1)
    if limit == 0:
        return sum(1 for v in values if v == 0)
    return best
