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
        total = 0
        for p, v in self._own.items():
            if p == path or p.startswith(path):
                total += v
        return total

    def clear(self, path: str) -> int:
        prev = self.rollup(path)
        if path in self._own:
            del self._own[path]
        return prev

    def paths(self) -> list:
        return sorted(self._own.keys())
