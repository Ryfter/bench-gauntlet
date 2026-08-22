def weave_lanes(lanes):
    # Generator, but drains each lane fully before moving to the next.
    for lane in lanes:
        for x in lane:
            yield x
