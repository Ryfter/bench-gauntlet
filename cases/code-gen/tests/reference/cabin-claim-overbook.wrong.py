class OverbookError(Exception):
    pass

def claim_cabin_slots(manifest, claims):
    if not isinstance(manifest, dict):
        raise TypeError("manifest must be a dict")
    if not isinstance(claims, (list, tuple)):
        raise TypeError("claims must be a list or tuple")
    for cabin, cap in manifest.items():
        if not isinstance(cabin, str) or type(cap) is not int or cap < 0:
            raise ValueError("invalid manifest entry")
    remaining = manifest
    for item in claims:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise TypeError("each claim must be a pair")
        cabin, n = item
        if not isinstance(cabin, str) or type(n) is not int:
            raise TypeError("cabin_id must be str and n must be int")
        if cabin not in remaining:
            raise KeyError(cabin)
        if n < 0:
            raise ValueError("n must be >= 1")
        if n >= remaining[cabin]:
            raise OverbookError(cabin)
        remaining[cabin] -= n
    return remaining
