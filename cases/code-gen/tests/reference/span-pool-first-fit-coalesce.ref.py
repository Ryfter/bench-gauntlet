class SpanPool:
    def __init__(self, capacity):
        if not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be int >= 1")
        self._free = [[0, capacity]]
        self._claimed = set()

    def claim(self, length):
        if not isinstance(length, int) or length < 1:
            return None
        for i, (s, L) in enumerate(self._free):
            if L >= length:
                start = s
                if L == length:
                    self._free.pop(i)
                else:
                    self._free[i] = [s + length, L - length]
                self._claimed.add((start, length))
                return start
        return None

    def release(self, start, length):
        if (start, length) not in self._claimed:
            return False
        self._claimed.remove((start, length))
        self._free.append([start, length])
        self._free.sort(key=lambda x: x[0])
        merged = []
        for s, L in self._free:
            if merged and merged[-1][0] + merged[-1][1] == s:
                merged[-1][1] += L
            else:
                merged.append([s, L])
        self._free = merged
        return True

    def free_total(self):
        return sum(L for _, L in self._free)

    def max_contiguous(self):
        if not self._free:
            return 0
        return max(L for _, L in self._free)

    def is_claimed(self, start):
        return any(s == start for s, _ in self._claimed)

    def claim_count(self):
        return len(self._claimed)
