from decimal import Decimal, ROUND_HALF_EVEN

def round_money(amount, places=2):
    if places < 0:
        places = 0
    quant = Decimal(10) ** -places
    return float(Decimal(str(amount)).quantize(quant, rounding=ROUND_HALF_EVEN))

def price_bundle(lines, tax_rate):
    nets = []
    for unit_price, qty, discount_pct in lines:
        raw = unit_price * qty * (1 - discount_pct / 100.0)
        nets.append(round_money(raw, 2))
    subtotal = round_money(sum(nets), 2) if nets else 0.0
    tax = round_money(subtotal * tax_rate / 100.0, 2)
    total = round_money(subtotal + tax, 2)
    return (subtotal, tax, total)
