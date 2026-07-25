from collections import deque

def max_stable_span(readings, max_drift):
    if max_drift < 0 or not readings:
        return 0
    minq, maxq = deque(), deque()
    left = 0
    best = 0
    for right, v in enumerate(readings):
        while minq and readings[minq[-1]] >= v:
            minq.pop()
        minq.append(right)
        while maxq and readings[maxq[-1]] <= v:
            maxq.pop()
        maxq.append(right)
        while left <= right and readings[maxq[0]] - readings[minq[0]] > max_drift:
            left += 1
            while minq and minq[0] < left:
                minq.popleft()
            while maxq and maxq[0] < left:
                maxq.popleft()
        best = max(best, right - left + 1)
    return best
