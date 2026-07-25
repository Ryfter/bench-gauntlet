def rank_bid_slots(bids, k):
    if k <= 0 or not bids:
        return []
    ordered = sorted(bids, key=lambda x: -x[1])
    return [b[0] for b in ordered[:k]]
