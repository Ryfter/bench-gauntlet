import math

def allocate_units(total, weights):
    if total < 0:
        raise ValueError("total must be non-negative")
    if any(w < 0 for w in weights):
        raise ValueError("weights must be non-negative")
    if not weights:
        return []
    s = sum(weights)
    if s == 0:
        return [0] * len(weights)
    exact = [total * w / s for w in weights]
    floors = [math.floor(x) for x in exact]
    rem = total - sum(floors)
    order = sorted(
        range(len(weights)),
        key=lambda i: (-(exact[i] - floors[i]), i),
    )
    for k in range(rem):
        floors[order[k]] += 1
    return floors
