def strip_void_rows(rows):
    rows[:] = [r for r in rows if r.strip() != ""]
    return rows
