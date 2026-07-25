def bus_boarding(capacity, groups):
    rem = capacity
    boarded = 0
    for g in groups:
        if g <= rem:
            rem -= g
            boarded += 1
    return boarded
