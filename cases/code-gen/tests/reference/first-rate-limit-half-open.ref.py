def first_rate_limit_hit(timestamps, limit, window):
    if window <= 0 or limit < 0:
        return -1
    left = 0
    for right, t in enumerate(timestamps):
        while left <= right and timestamps[left] <= t - window:
            left += 1
        if right - left + 1 > limit:
            return t
    return -1
