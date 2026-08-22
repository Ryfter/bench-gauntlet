def bus_boarding(capacity, groups):
    rem = capacity
    boarded = 0
    for g in groups:
        if g <= rem:
            rem -= g
            boarded += 1
        else:
            # stops at first no-fit instead of skipping
            break
    return boarded
