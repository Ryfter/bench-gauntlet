def first_viable_window(loads, capacity, width):
    n = len(loads)
    if width <= 0 or width > n:
        return -1
    s = sum(loads[:width])
    if s <= capacity:
        return 0
    for i in range(width, n):
        s += loads[i] - loads[i - width]
        if s <= capacity:
            return i - width + 1
    return -1
