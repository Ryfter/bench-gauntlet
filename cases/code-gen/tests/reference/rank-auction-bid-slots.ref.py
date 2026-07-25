def rank_bid_slots(bids, k):
    if k <= 0 or not bids:
        return []

    def better(cand, cur):
        if cand[0] != cur[0]:
            return cand[0] > cur[0]
        if cand[1] != cur[1]:
            return cand[1] < cur[1]
        return cand[2] < cur[2]

    best = {}
    for bidder_id, amount, timestamp in bids:
        cand = (amount, timestamp, bidder_id)
        if bidder_id not in best or better(cand, best[bidder_id]):
            best[bidder_id] = cand

    ranked = sorted(best.values(), key=lambda x: (-x[0], x[1], x[2]))
    return [b[2] for b in ranked[:k]]
