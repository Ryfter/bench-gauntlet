def build_invoice_lines(items):
    out = []
    for sku, qty, unit_price in items:
        if sku is None or sku == "":
            continue
        if not qty:
            continue
        out.append({
            "sku": sku,
            "qty": qty,
            "unit_price": unit_price,
            "line_total": qty * unit_price,
        })
    return out
