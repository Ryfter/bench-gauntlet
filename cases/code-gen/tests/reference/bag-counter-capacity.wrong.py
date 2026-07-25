class BagCounter:
    def __init__(self, capacity):
        if not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._names = set()

    def check_in(self, name):
        if not isinstance(name, str) or name == "" or name in self._names:
            return False
        # off-by-one: allows one guest past capacity
        if len(self._names) > self._capacity:
            return False
        self._names.add(name)
        return True

    def check_out(self, name):
        if name not in self._names:
            return False
        self._names.remove(name)
        return True

    def count(self):
        return len(self._names)

    def contains(self, name):
        return name in self._names

    def remaining(self):
        return self._capacity - len(self._names)
