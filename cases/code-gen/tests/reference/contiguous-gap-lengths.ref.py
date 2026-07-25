def contiguous_gap_lengths(row):
    result = []
    count = 0
    for ch in row:
        if ch == ".":
            count += 1
        else:
            if count:
                result.append(count)
                count = 0
    if count:
        result.append(count)
    return result
