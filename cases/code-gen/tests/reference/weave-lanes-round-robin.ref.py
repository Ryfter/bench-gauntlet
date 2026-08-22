def weave_lanes(lanes):
    idxs = [0] * len(lanes)
    while True:
        progressed = False
        for i, lane in enumerate(lanes):
            j = idxs[i]
            if j < len(lane):
                yield lane[j]
                idxs[i] = j + 1
                progressed = True
        if not progressed:
            break
