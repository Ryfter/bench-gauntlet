import bisect

class RunningMedianTracker:
    def __init__(self):
        self._xs = []

    def add(self, x: int) -> None:
        bisect.insort(self._xs, x)

    def remove(self, x: int) -> bool:
        i = bisect.bisect_left(self._xs, x)
        if i == len(self._xs) or self._xs[i] != x:
            return False
        self._xs.pop(i)
        return True

    def median(self):
        n = len(self._xs)
        if n == 0:
            return None
        if n % 2 == 1:
            return float(self._xs[n // 2])
        return (self._xs[n // 2 - 1] + self._xs[n // 2]) / 2.0

    def count(self) -> int:
        return len(self._xs)
