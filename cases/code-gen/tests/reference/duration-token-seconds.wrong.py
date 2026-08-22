def duration_to_seconds(s):
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    if s == "":
        return 0
    total = 0
    i = 0
    while i < len(s):
        if not s[i].isdigit():
            return -1
        j = i
        while j < len(s) and s[j].isdigit():
            j += 1
        if j == len(s) or s[j] not in units:
            return -1
        total += int(s[i:j]) * units[s[j]]
        i = j + 1
    return total
