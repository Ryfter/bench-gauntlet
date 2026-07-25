def count_filled_slots(row):
    n = 0
    for cell in row:
        if cell is not None and cell != "":
            n += 1
    return n
