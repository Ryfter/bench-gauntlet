class SeatHoldBoard:
    def __init__(self, n_seats: int):
        self._n = n_seats
        self._holds = {}
        self._ids = {}

    def _purge(self, now: int) -> None:
        # off-by-one: still treats now == expires_at as live
        dead = [s for s, (_, exp) in self._holds.items() if now > exp]
        for s in dead:
            hid, _ = self._holds.pop(s)
            self._ids.pop(hid, None)

    def hold(self, seat: int, hold_id: str, now: int, ttl: int) -> bool:
        if seat < 0 or seat >= self._n or ttl < 1:
            return False
        self._purge(now)
        if hold_id in self._ids:
            return False
        if seat in self._holds:
            return False
        exp = now + ttl
        self._holds[seat] = (hold_id, exp)
        self._ids[hold_id] = seat
        return True

    def release(self, hold_id: str) -> bool:
        if hold_id not in self._ids:
            return False
        seat = self._ids.pop(hold_id)
        self._holds.pop(seat, None)
        return True

    def is_free(self, seat: int, now: int) -> bool:
        if seat < 0 or seat >= self._n:
            return False
        self._purge(now)
        return seat not in self._holds

    def free_count(self, now: int) -> int:
        self._purge(now)
        return self._n - len(self._holds)
