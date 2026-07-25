def parse_nested_kv(s):
    if s == "":
        return {}
    root = {}
    for field in s.split(";"):
        if not field or "=" not in field:
            continue
        k, v = field.split("=", 1)
        parts = k.split(".")
        if not parts or any(p == "" for p in parts):
            continue
        cur = root
        for p in parts[:-1]:
            if p not in cur or not isinstance(cur[p], dict):
                cur[p] = {}
            cur = cur[p]
        if parts[-1] not in cur:
            cur[parts[-1]] = v
    return root
