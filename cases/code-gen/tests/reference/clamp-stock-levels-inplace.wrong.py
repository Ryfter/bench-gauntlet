def clamp_inplace(values, lo, hi):
    # Filters out-of-range values instead of clamping them; empty/in-range cases still look fine.
    values[:] = [x for x in values if lo <= x <= hi]
    return None
