def spill_right_inplace(bins, limit):
    # Cascades, but also clamps the final bin down to limit.
    for i in range(len(bins)):
        if bins[i] > limit:
            extra = bins[i] - limit
            bins[i] = limit
            if i + 1 < len(bins):
                bins[i + 1] += extra
