def to_grams(qty: int, unit: str) -> int:
    if qty < 0:
        raise ValueError("negative qty")
    if unit == "g":
        return qty
    if unit == "kg":
        return qty * 1000
    if unit == "mg":
        return (qty + 999) // 1000
    if unit == "oz":
        return qty * 28
    return 0

def total_grams(items: list):
    if not items:
        return None
    return sum(to_grams(q, u) for q, u in items)
