def total_payload_bytes(manifest):
    mult = {
        "B": 1,
        "KB": 1000,
        "MB": 1000000,
        "GB": 1000000000,
        "KiB": 1024,
        "MiB": 1024 ** 2,
        "GiB": 1024 ** 3,
    }
    total = 0
    for line in manifest.splitlines():
        if line == "":
            continue
        parts = line.split("|")
        if len(parts) != 3:
            continue
        sku, qty_s, size_s = parts
        if sku == "":
            continue
        try:
            qty = int(qty_s)
        except ValueError:
            continue
        if qty < 0:
            continue
        i = 0
        num_chars = []
        saw_digit = False
        saw_dot = False
        while i < len(size_s) and (size_s[i].isdigit() or (size_s[i] == "." and not saw_dot)):
            if size_s[i] == ".":
                saw_dot = True
            else:
                saw_digit = True
            num_chars.append(size_s[i])
            i += 1
        if not saw_digit:
            continue
        suf = size_s[i:]
        if suf == "":
            suf = "B"
        if suf not in mult:
            continue
        try:
            raw = float("".join(num_chars))
        except ValueError:
            continue
        units = int(raw * mult[suf])
        total += qty * units
    return total
