class TreeTally:
    def __init__(self):
        self._own = {}

    def add(self, path: str, n: int = 1) -> int:
        if n < 1:
            raise ValueError("n must be >= 1")
        self._own[path] = self._own.get(path, 0) + n
        return self._own[path]

    def own(self, path: str) -> int:
        return self._own.get(path, 0)

    def rollup(self, path: str) -> int:
        total = self._own.get(path, 0)
        prefix = path + "/"
        for p, v in self._own.items():
            if p.startswith(prefix):
                total += v
        return total

    def clear(self, path: str) -> int:
        prev = self.rollup(path)
        prefix = path + "/"
        for p in [p for p in self._own if p == path or p.startswith(prefix)]:
            del self._own[p]
        return prev

    def paths(self) -> list:
        return sorted(self._own.keys())
