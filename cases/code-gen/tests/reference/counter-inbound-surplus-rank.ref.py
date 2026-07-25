from collections import Counter

def surplus_skus(inbound, outbound):
    c = Counter(inbound)
    c.subtract(outbound)
    result = [(sku, n) for sku, n in c.items() if n > 0]
    result.sort(key=lambda x: (-x[1], x[0]))
    return result
