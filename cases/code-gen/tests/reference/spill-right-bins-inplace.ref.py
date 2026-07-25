def spill_right_inplace(bins, limit):
    for i in range(len(bins) - 1):
        if bins[i] > limit:
            bins[i + 1] += bins[i] - limit
            bins[i] = limit
