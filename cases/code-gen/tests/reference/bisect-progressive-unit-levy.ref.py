def progressive_levy(amount, cuts, rates):
    fee = 0
    lower = 0
    for i, upper in enumerate(cuts):
        chunk = min(amount, upper) - lower
        if chunk > 0:
            fee += chunk * rates[i]
        lower = upper
        if amount <= upper:
            return fee
    fee += (amount - lower) * rates[len(cuts)]
    return fee
