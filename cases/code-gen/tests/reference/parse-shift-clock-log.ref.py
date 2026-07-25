def parse_shift_log(raw: str) -> list[dict]:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.rsplit(None, 1)
        if len(parts) != 2 or parts[1] not in ("IN", "OUT"):
            continue
        action = parts[1]
        rest = parts[0]
        head = rest.split(None, 1)
        if len(head) != 2:
            continue
        time_s, name = head[0], head[1].strip()
        if len(time_s) != 5 or time_s[2] != ":":
            continue
        hh_s, mm_s = time_s[:2], time_s[3:]
        if not (hh_s.isdigit() and mm_s.isdigit()):
            continue
        hh, mm = int(hh_s), int(mm_s)
        if hh > 23 or mm > 59:
            continue
        out.append({"time": time_s, "name": name, "action": action})
    return out
