def strip_void_rows(rows):
    i = 0
    while i < len(rows):
        if rows[i] == "":
            del rows[i]
        else:
            i += 1
    return rows
