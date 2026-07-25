def half_open_hits(values, lo, hi):
    if lo >= hi:
        return 0
    # closed on the right: incorrectly includes hi
    return sum(1 for v in values if lo <= v <= hi)
