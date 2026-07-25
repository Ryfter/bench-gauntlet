def first_fit_assign(weights, capacity):
    remaining = []
    assign = []
    for w in weights:
        placed = False
        for i in range(len(remaining) - 1, -1, -1):
            if remaining[i] >= w:
                remaining[i] -= w
                assign.append(i)
                placed = True
                break
        if not placed:
            remaining.append(capacity - w)
            assign.append(len(remaining) - 1)
    return assign
