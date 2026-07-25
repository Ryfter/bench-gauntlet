def intervals_overlap(a_start, a_end, b_start, b_end):
    if a_start >= a_end or b_start >= b_end:
        return False
    return a_start < b_end and b_start < a_end

def find_conflicts(shifts):
    out = []
    n = len(shifts)
    for i in range(n):
        for j in range(i + 1, n):
            a = shifts[i]
            b = shifts[j]
            if intervals_overlap(a["start"], a["end"], b["start"], b["end"]):
                pair = tuple(sorted((a["id"], b["id"])))
                out.append(pair)
    return sorted(out)
