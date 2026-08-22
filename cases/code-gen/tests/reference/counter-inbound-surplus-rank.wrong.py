from collections import Counter

def surplus_skus(inbound, outbound):
    c = Counter(inbound)
    for x in set(outbound):
        c[x] -= 1
    result = [(sku, n) for sku, n in c.items() if n > 0]
    result.sort(key=lambda x: (-x[1], x[0]))
    return result
