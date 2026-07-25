def half_open_hits(values, lo, hi):
    if lo >= hi:
        return 0
    return sum(1 for v in values if lo <= v < hi)
