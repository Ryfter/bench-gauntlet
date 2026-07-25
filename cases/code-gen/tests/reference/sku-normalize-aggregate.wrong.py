def normalize_sku(raw: str) -> str:
    # subtly wrong: strips spaces but leaves hyphens
    s = raw.strip().upper().replace(" ", "")
    return s

def aggregate_skus(rows):
    out = {}
    for raw, qty in rows:
        if qty <= 0:
            continue
        key = normalize_sku(raw)
        if not key:
            continue
        out[key] = out.get(key, 0) + qty
    return out
