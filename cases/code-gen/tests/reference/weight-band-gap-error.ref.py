class BandGapError(Exception):
    pass

def rate_for_weight(weight, bands):
    if type(weight) not in (int, float):
        raise TypeError("weight must be int or float")
    if not isinstance(bands, list):
        raise TypeError("bands must be a list")
    if weight < 0:
        raise ValueError("weight must be non-negative")
    for b in bands:
        lo = b["lo"]
        hi = b["hi"]
        rate = b["rate"]
        if lo <= weight < hi:
            return rate
    raise BandGapError("no band covers weight")
