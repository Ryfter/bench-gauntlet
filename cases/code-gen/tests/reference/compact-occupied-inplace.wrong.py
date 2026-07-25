def compact_occupied_inplace(seats):
    # Single left-bubble pass: multi-gap lists are not fully compacted.
    for i in range(1, len(seats)):
        if seats[i] is not None and seats[i - 1] is None:
            seats[i - 1], seats[i] = seats[i], None
