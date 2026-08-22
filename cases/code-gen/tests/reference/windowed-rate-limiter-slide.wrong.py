class WindowRateLimiter:
    def __init__(self, limit: int, window: int):
        self._limit = limit
        self._window = window
        self._events = []
        self._bucket = None

    def allow(self, t: int) -> bool:
        bucket = t // self._window
        if self._bucket is None or bucket != self._bucket:
            self._events = []
            self._bucket = bucket
        if len(self._events) < self._limit:
            self._events.append(t)
            return True
        return False

    def counted(self, t: int) -> int:
        bucket = t // self._window
        if self._bucket is None or bucket != self._bucket:
            return 0
        return len(self._events)
