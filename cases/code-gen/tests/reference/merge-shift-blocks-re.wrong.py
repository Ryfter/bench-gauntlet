import re

def merge_shift_blocks(records: list[str]) -> list[tuple[str, str]]:
    pat = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$")
    intervals = []
    for rec in records:
        m = pat.match(rec)
        if not m:
            continue
        h1, mi1, h2, mi2 = map(int, m.groups())
        if not (0 <= h1 <= 23 and 0 <= h2 <= 23 and 0 <= mi1 <= 59 and 0 <= mi2 <= 59):
            continue
        start = h1 * 60 + mi1
        end = h2 * 60 + mi2
        if end <= start:
            continue
        intervals.append((start, end))
    intervals.sort()
    if not intervals:
        return []
    merged = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    def fmt(mins: int) -> str:
        return f"{mins // 60:02d}:{mins % 60:02d}"

    return [(fmt(s), fmt(e)) for s, e in merged]
