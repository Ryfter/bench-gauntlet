class WindowRateLimiter:
    def __init__(self, limit: int, window: int):
        self._limit = limit
        self._window = window
        self._events = []

    def allow(self, t: int) -> bool:
        cutoff = t - self._window
        self._events = [e for e in self._events if e > cutoff]
        if len(self._events) < self._limit:
            self._events.append(t)
            return True
        return False

    def counted(self, t: int) -> int:
        cutoff = t - self._window
        return sum(1 for e in self._events if e > cutoff)
