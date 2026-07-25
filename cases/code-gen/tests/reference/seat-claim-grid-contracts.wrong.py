def claim_seat(layout, row, col, name):
    if not isinstance(name, str):
        raise TypeError("name must be str")
    if name == "":
        raise ValueError("name must be non-empty")
    if not isinstance(row, int) or not isinstance(col, int):
        raise TypeError("row and col must be int")
    if not isinstance(layout, list):
        raise TypeError("layout must be list")
    if len(layout) == 0:
        raise IndexError("empty layout")
    row_list = layout[row]
    if not isinstance(row_list, list):
        raise TypeError("row must be list")
    cell = row_list[col]
    if cell is None or cell == "":
        layout[row][col] = name
        return True
    if cell == name:
        return False
    raise ValueError("seat occupied")
