class StockCorruptError(Exception):
    pass

def reconcile_stock(on_hand, movements):
    if not isinstance(on_hand, dict):
        raise TypeError("on_hand must be dict")
    if not isinstance(movements, list):
        raise TypeError("movements must be list")
    for sku, qty in on_hand.items():
        if not isinstance(qty, int):
            raise TypeError("quantities must be int")
        if qty < 0:
            raise ValueError(sku)
    result = dict(on_hand)
    for item in movements:
        if not isinstance(item, tuple) or len(item) != 2:
            raise TypeError("movement must be 2-tuple")
        sku, delta = item
        if not isinstance(sku, str):
            raise TypeError("sku must be str")
        if not isinstance(delta, int):
            raise TypeError("delta must be int")
        if sku not in result:
            raise KeyError(sku)
        result[sku] = result[sku] + delta
    for sku, qty in result.items():
        if qty < 0:
            raise ValueError("negative stock")
    return result
