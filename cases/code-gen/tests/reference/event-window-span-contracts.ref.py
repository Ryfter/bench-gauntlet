class ChronologyError(Exception):
    pass

def window_span(events, i, j):
    if not isinstance(events, list):
        raise TypeError("events must be list")
    if type(i) is not int or type(j) is not int:
        raise TypeError("i and j must be plain int")
    if i < 0 or j < 0:
        raise IndexError("negative index")
    if i >= len(events) or j >= len(events):
        raise IndexError("index out of range")
    if i > j:
        raise ValueError("i > j")
    labels = []
    prev_t = None
    for k in range(i, j + 1):
        ev = events[k]
        if not isinstance(ev, dict):
            raise TypeError("event must be dict")
        if "t" not in ev:
            raise KeyError("t")
        if "label" not in ev:
            raise KeyError("label")
        t = ev["t"]
        lab = ev["label"]
        if type(t) is not int:
            raise TypeError("t must be plain int")
        if not isinstance(lab, str):
            raise TypeError("label must be str")
        if prev_t is not None and t < prev_t:
            raise ChronologyError(k)
        prev_t = t
        labels.append(lab)
    duration = events[j]["t"] - events[i]["t"]
    return (",".join(labels), duration)
