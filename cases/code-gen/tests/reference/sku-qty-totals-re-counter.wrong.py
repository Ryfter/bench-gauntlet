import re
import collections

def sku_qty_totals(lines: list[str]) -> list[tuple[str, int]]:
    pat = re.compile(r"SKU=([A-Za-z0-9]+)\s+qty=(-?\d+)")
    totals = collections.Counter()
    for line in lines:
        m = pat.search(line)
        if m:
            totals[m.group(1)] += int(m.group(2))
    items = list(totals.items())
    items.sort(key=lambda x: (-x[1], x[0]))
    return items
