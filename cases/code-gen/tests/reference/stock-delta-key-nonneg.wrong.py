def apply_stock_delta(stock, delta):
    if not isinstance(stock, dict) or not isinstance(delta, dict):
        raise TypeError("stock and delta must be dicts")
    for src in (stock, delta):
        for k, v in src.items():
            if not isinstance(k, str) or type(v) is not int:
                raise TypeError("keys must be str and values must be int")
    for k, v in delta.items():
        new = stock.get(k, 0) + v
        if new <= 0:
            raise ValueError("stock would go negative")
        stock[k] = new
    return stock
