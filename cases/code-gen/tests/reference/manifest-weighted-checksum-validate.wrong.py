def item_checksum(sku, qty):
    s = sum(ord(c) for c in sku)
    return (s + qty) % 1000

def validate_manifest(items, expected_total):
    if expected_total < 0:
        return False
    if not items:
        return expected_total == 0
    seen = set()
    total = 0
    for it in items:
        sku = it["sku"]
        qty = it["qty"]
        if not isinstance(sku, str) or sku == "" or not isinstance(qty, int) or qty < 0:
            return False
        if sku in seen:
            return False
        seen.add(sku)
        if item_checksum(sku, qty) != it["checksum"]:
            return False
        total += qty
    return total == expected_total
