class BookingLedger:
    def __init__(self, capacity: int):
        self._cap = capacity
        self._held = {}

    def book(self, name: str, seats: int) -> bool:
        if seats < 1:
            return False
        if self.free() < seats:
            return False
        self._held[name] = seats
        return True

    def cancel(self, name: str) -> int:
        return self._held.pop(name, 0)

    def free(self) -> int:
        return self._cap - sum(self._held.values())

    def held(self, name: str) -> int:
        return self._held.get(name, 0)
