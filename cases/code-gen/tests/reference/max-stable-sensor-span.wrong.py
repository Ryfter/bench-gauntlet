def max_stable_span(readings, max_drift):
    if max_drift < 0 or not readings:
        return 0
    best = 1
    left = 0
    for right in range(len(readings)):
        while left < right and abs(readings[right] - readings[left]) > max_drift:
            left += 1
        best = max(best, right - left + 1)
    return best
