def parse_seat_token(token):
    import re
    if not isinstance(token, str):
        raise TypeError("token must be str")
    m = re.fullmatch(r"R(\d+)-C(\d+)", token)
    if not m:
        raise ValueError("malformed seat token")
    row = int(m.group(1))
    col = int(m.group(2))
    if not (0 <= row <= 99 and 1 <= col <= 51):
        raise ValueError("seat out of range")
    return (row, col)
