def parse_shift_log(raw: str) -> list[dict]:
    # only splits on \n (bare \r batches stay one line); no HH/MM range checks
    out = []
    for line in raw.split("\n"):
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
        if not (time_s[:2].isdigit() and time_s[3:].isdigit()):
            continue
        out.append({"time": time_s, "name": name, "action": action})
    return out
