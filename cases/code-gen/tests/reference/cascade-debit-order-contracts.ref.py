class ShortfallError(Exception):
    pass

class DuplicateOrderError(Exception):
    pass

def debit_cascade(ledgers, order, amount):
    if not isinstance(ledgers, list):
        raise TypeError("ledgers must be list")
    if not isinstance(order, list):
        raise TypeError("order must be list")
    if type(amount) is not int:
        raise TypeError("amount must be plain int")
    if amount <= 0:
        raise ValueError("amount must be positive")
    if len(order) == 0:
        raise IndexError("empty order")
    seen = set()
    for idx in order:
        if type(idx) is not int:
            raise TypeError("order indices must be plain int")
        if idx < 0 or idx >= len(ledgers):
            raise IndexError("order index out of range")
        if idx in seen:
            raise DuplicateOrderError(idx)
        seen.add(idx)
    for led in ledgers:
        if not isinstance(led, dict):
            raise TypeError("ledger must be dict")
        if "balance" not in led:
            raise KeyError("balance")
        bal = led["balance"]
        if type(bal) is not int:
            raise TypeError("balance must be plain int")
        if bal < 0:
            raise ValueError("negative balance")
    result = [dict(led) for led in ledgers]
    remaining = amount
    for idx in order:
        if remaining == 0:
            break
        bal = result[idx]["balance"]
        take = min(bal, remaining)
        result[idx]["balance"] = bal - take
        remaining -= take
    if remaining > 0:
        raise ShortfallError(remaining)
    return result
