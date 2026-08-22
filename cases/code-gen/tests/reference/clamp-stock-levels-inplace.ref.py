def clamp_inplace(values, lo, hi):
    for i in range(len(values)):
        if values[i] < lo:
            values[i] = lo
        elif values[i] > hi:
            values[i] = hi
