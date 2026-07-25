class BudgetEnvelope:
    def __init__(self, soft, hard):
        if not isinstance(soft, int) or not isinstance(hard, int):
            raise TypeError("soft and hard must be int")
        if soft < 0 or hard < 0 or soft > hard:
            raise ValueError("require 0 <= soft <= hard")
        self._soft = soft
        self._hard = hard
        self._spent = 0

    def spend(self, amount):
        if not isinstance(amount, int) or amount <= 0:
            return "rejected"
        if self._spent + amount > self._hard:
            return "rejected"
        # subtle bug: treats soft as a hard reject boundary
        if self._spent + amount > self._soft:
            return "rejected"
        self._spent += amount
        return "ok"

    def refund(self, amount):
        if not isinstance(amount, int) or amount <= 0 or amount > self._spent:
            return False
        self._spent -= amount
        return True

    def spent(self):
        return self._spent

    def remaining(self):
        return self._hard - self._spent

    def soft_remaining(self):
        r = self._soft - self._spent
        return r if r > 0 else 0
