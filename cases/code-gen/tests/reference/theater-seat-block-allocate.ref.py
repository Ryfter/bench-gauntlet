def fits_block(row: list, start: int, length: int) -> bool:
    if length < 1 or start < 0:
        raise ValueError("invalid start/length")
    if start + length > len(row):
        return False
    return all(not row[i] for i in range(start, start + length))

def allocate_seats(row: list, parties: list) -> list:
    if any(p < 1 for p in parties):
        raise ValueError("invalid party size")
    work = list(row)
    out = []
    for size in parties:
        placed = None
        for start in range(0, len(work) - size + 1):
            if fits_block(work, start, size):
                for i in range(start, start + size):
                    work[i] = True
                placed = start
                break
        out.append(placed)
    return out
