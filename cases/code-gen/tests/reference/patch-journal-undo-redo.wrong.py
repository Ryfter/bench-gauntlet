class PatchJournal:
    def __init__(self, start: int = 0):
        self._v = start
        self._undo = []
        self._redo = []

    def apply(self, delta: int) -> int:
        self._undo.append(self._v)
        self._v += delta
        return self._v

    def set(self, n: int) -> int:
        self._undo.append(self._v)
        self._v = n
        return self._v

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._v)
        self._v = self._undo.pop()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._v)
        self._v = self._redo.pop()
        return True

    def value(self) -> int:
        return self._v
