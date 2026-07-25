def count_filled_slots(row):
    n = 0
    for cell in row:
        if cell is None:
            continue
        if isinstance(cell, str) and cell.strip() == "":
            continue
        n += 1
    return n
