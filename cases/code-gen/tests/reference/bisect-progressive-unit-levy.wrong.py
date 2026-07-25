import bisect

def progressive_levy(amount, cuts, rates):
    if amount <= 0:
        return 0
    idx = bisect.bisect_right(cuts, amount - 1)
    return amount * rates[idx]
