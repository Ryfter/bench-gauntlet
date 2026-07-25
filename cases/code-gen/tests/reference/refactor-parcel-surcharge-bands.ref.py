def parcel_surcharge(weight_kg, region, fragile):
    if weight_kg is None or weight_kg <= 0:
        return -1
    if region not in ("local", "domestic", "intl"):
        return -1
    if weight_kg <= 1:
        base = 0
    elif weight_kg <= 5:
        base = 2
    elif weight_kg <= 20:
        base = 5
    else:
        base = 12
    region_fee = {"local": 0, "domestic": 3, "intl": 8}[region]
    if fragile:
        fragile_fee = 7 if weight_kg > 20 else 4
    else:
        fragile_fee = 0
    intl_extra = 2 if region == "intl" and weight_kg > 5 else 0
    return base + region_fee + fragile_fee + intl_extra
