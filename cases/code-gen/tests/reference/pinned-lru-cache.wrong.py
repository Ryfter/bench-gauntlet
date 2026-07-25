from collections import OrderedDict

class PinnedLRUCache:
    def __init__(self, capacity: int):
        self._cap = capacity
        self._data = OrderedDict()
        self._pinned = set()

    def put(self, key: str, value: int) -> bool:
        if key in self._data:
            self._data[key] = value
            self._data.move_to_end(key)
            return True
        if len(self._data) >= self._cap:
            # ignores pins: always evicts true LRU
            victim = next(iter(self._data))
            del self._data[victim]
            self._pinned.discard(victim)
        self._data[key] = value
        return True

    def get(self, key: str):
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def pin(self, key: str) -> bool:
        if key not in self._data:
            return False
        self._pinned.add(key)
        return True

    def unpin(self, key: str) -> bool:
        if key not in self._pinned:
            return False
        self._pinned.discard(key)
        return True

    def size(self) -> int:
        return len(self._data)

    def pinned_count(self) -> int:
        return len(self._pinned)
