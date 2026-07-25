def peak_day_totals(text):
    from collections import defaultdict
    agg = defaultdict(int)
    for line in text.splitlines():
        if line == "":
            continue
        parts = line.split("|")
        if len(parts) != 3:
            continue
        dt, cat, num_s = parts
        if cat == "":
            continue
        try:
            n = int(num_s)
        except ValueError:
            continue
        token = dt.split(" ")
        if len(token) not in (1, 2):
            continue
        datepart = token[0]
        if len(token) == 2:
            tm = token[1]
            if len(tm) != 5 or tm[2] != ":":
                continue
            hh, mm = tm.split(":")
            if not (hh.isdigit() and mm.isdigit()):
                continue
            hi, mi = int(hh), int(mm)
            if hi > 23 or mi > 59:
                continue
        bits = datepart.split("/")
        if len(bits) != 3:
            continue
        dd_s, mm_s, yyyy_s = bits
        if not (dd_s.isdigit() and mm_s.isdigit() and yyyy_s.isdigit()):
            continue
        if len(yyyy_s) != 4:
            continue
        d, m, y = int(dd_s), int(mm_s), int(yyyy_s)
        if not (1 <= m <= 12 and 1 <= d <= 31):
            continue
        iso = f"{y:04d}-{m:02d}-{d:02d}"
        agg[iso] += n
    items = [[k, v] for k, v in agg.items() if v != 0]
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    return items
