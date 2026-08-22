def compact_occupied_inplace(seats):
    w = 0
    for x in seats:
        if x is not None:
            seats[w] = x
            w += 1
    for j in range(w, len(seats)):
        seats[j] = None
