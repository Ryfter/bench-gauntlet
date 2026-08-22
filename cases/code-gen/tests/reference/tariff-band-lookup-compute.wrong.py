def lookup_band(bands, quantity):
    if quantity is None or quantity < 0 or not bands:
        return None
    for band in bands:
        limit = band["limit"]
        if limit is None or quantity < limit:
            return band["rate"]
    return None

def compute_tariff(bands, quantity):
    rate = lookup_band(bands, quantity)
    if rate is None:
        return None
    return float(quantity) * rate
