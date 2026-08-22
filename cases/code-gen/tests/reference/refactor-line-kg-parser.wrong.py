def line_kg(s):
    if s is None or type(s) is not str:
        return None
    t = s.strip().lower()
    # subtle: blank / n/a treated as missing instead of 0.0
    if t == "" or t == "n/a":
        return None
    t = "".join(t.split())
    if t.endswith("kg"):
        unit = "kg"
        num = t[:-2]
    elif t.endswith("g"):
        unit = "g"
        num = t[:-1]
    else:
        return None
    if num in ("", "-", "+", "."):
        return None
    try:
        v = float(num)
    except ValueError:
        return None
    if v < 0:
        return None
    if unit == "kg":
        return float(v)
    return float(v) / 1000.0
