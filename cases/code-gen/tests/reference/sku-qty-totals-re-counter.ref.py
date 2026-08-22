import re
import collections

def sku_qty_totals(lines: list[str]) -> list[tuple[str, int]]:
    pat = re.compile(r"SKU=([A-Za-z0-9]+)\s+qty=(-?\d+)")
    totals = collections.Counter()
    for line in lines:
        for m in pat.finditer(line):
            totals[m.group(1)] += int(m.group(2))
    items = [(sku, n) for sku, n in totals.items() if n != 0]
    items.sort(key=lambda x: (-x[1], x[0]))
    return items
