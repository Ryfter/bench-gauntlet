from collections import defaultdict

def shortest_k_variety(items, k):
    if k <= 0 or not items:
        return 0
    freq = defaultdict(int)
    left = 0
    distinct = 0
    best = float("inf")
    for right, x in enumerate(items):
        if freq[x] == 0:
            distinct += 1
        freq[x] += 1
        while distinct >= k and left <= right:
            best = min(best, right - left + 1)
            y = items[left]
            freq[y] -= 1
            if freq[y] == 0:
                distinct -= 1
            left += 1
    return 0 if best == float("inf") else int(best)
