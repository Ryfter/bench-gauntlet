def claim_seat(layout, row, col, name):
    if not isinstance(name, str):
        raise TypeError("name must be str")
    if name == "":
        raise ValueError("name must be non-empty")
    if type(row) is not int or type(col) is not int:
        raise TypeError("row and col must be plain int")
    if not isinstance(layout, list):
        raise TypeError("layout must be list")
    if len(layout) == 0:
        raise IndexError("empty layout")
    if row < 0 or col < 0:
        raise IndexError("negative coordinates")
    if row >= len(layout):
        raise IndexError("row out of range")
    row_list = layout[row]
    if not isinstance(row_list, list):
        raise TypeError("row must be list")
    if col >= len(row_list):
        raise IndexError("col out of range")
    cell = row_list[col]
    if cell is None or cell == "":
        layout[row][col] = name
        return True
    if cell == name:
        return False
    raise ValueError("seat occupied")
