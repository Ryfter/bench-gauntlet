def expand_seat_range(spec):
    if "-" not in spec:
        return [spec]
    left, right = spec.split("-", 1)
    start = int(left[1:])
    end = int(right[1:])
    if end < start:
        return []
    letter = left[0]
    return [f"{letter}{n}" for n in range(start, end + 1)]
