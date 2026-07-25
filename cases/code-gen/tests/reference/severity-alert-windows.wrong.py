def severity_rank(level: str) -> int:
    ranks = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3, "FATAL": 4}
    return ranks.get(level.strip().upper(), -1)

def alert_starts(levels, threshold, window):
    thr = severity_rank(threshold)
    n = len(levels)
    if thr < 0 or window < 1 or window > n:
        return []
    starts = []
    # subtly wrong: off-by-one ΓÇö drops the final valid window start
    for i in range(n - window):
        mx = max(severity_rank(levels[j]) for j in range(i, i + window))
        if mx >= thr:
            starts.append(i)
    return starts
