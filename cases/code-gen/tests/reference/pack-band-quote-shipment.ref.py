def pack_weight_band(grams: int) -> str:
    if grams < 0:
        return "invalid"
    if grams <= 500:
        return "letter"
    if grams <= 2000:
        return "parcel"
    if grams <= 10000:
        return "freight"
    return "oversize"

def quote_shipment(items_grams, rates):
    total = 0
    for g in items_grams:
        band = pack_weight_band(g)
        if band == "invalid":
            continue
        total += rates.get(band, 0)
    return total
