class HoldBoard:
    def __init__(self, slots):
        if not isinstance(slots, int) or slots < 1:
            raise ValueError("slots must be int >= 1")
        self._n = slots
        self._slots = {i: ("free", None) for i in range(slots)}
        self._by_holder = {}

    def hold(self, slot, holder):
        if not isinstance(slot, int) or slot < 0 or slot >= self._n:
            return False
        if not isinstance(holder, str) or holder == "":
            return False
        if holder in self._by_holder:
            return False
        st, _ = self._slots[slot]
        if st != "free":
            return False
        self._slots[slot] = ("held", holder)
        self._by_holder[holder] = slot
        return True

    def confirm(self, holder):
        if holder not in self._by_holder:
            return False
        slot = self._by_holder[holder]
        st, _ = self._slots[slot]
        if st != "held":
            return False
        self._slots[slot] = ("booked", holder)
        return True

    def cancel(self, holder):
        if holder not in self._by_holder:
            return False
        slot = self._by_holder[holder]
        self._slots[slot] = ("free", None)
        del self._by_holder[holder]
        return True

    def status(self, slot):
        if not isinstance(slot, int) or slot < 0 or slot >= self._n:
            return None
        return self._slots[slot][0]

    def holder_of(self, slot):
        if not isinstance(slot, int) or slot < 0 or slot >= self._n:
            return None
        return self._slots[slot][1]

    def free_count(self):
        return sum(1 for st, _ in self._slots.values() if st == "free")
