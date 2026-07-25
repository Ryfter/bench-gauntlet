import heapq

def dispatch_orders(orders, couriers):
    sorted_orders = sorted(orders, key=lambda o: (-o[2], o[1], o[0]))
    free = [(0, i) for i in range(couriers)]
    heapq.heapify(free)
    result = [[] for _ in range(couriers)]
    for oid, prep, pri in sorted_orders:
        t, idx = heapq.heappop(free)
        result[idx].append(oid)
        heapq.heappush(free, (t + prep, idx))
    return result
