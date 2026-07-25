def to_grams(qty: int, unit: str) -> int:
    if qty < 0:
        raise ValueError("negative qty")
    if unit == "g":
        return qty
    if unit == "kg":
        return qty * 1000
    if unit == "mg":
        return qty // 1000
    if unit == "oz":
        return qty * 28
    raise ValueError("unknown unit")

def total_grams(items: list) -> int:
    return sum(to_grams(q, u) for q, u in items)
