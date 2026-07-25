def debounce_ready(readings, hold):
    if hold < 1:
        return -1
    streak = 0
    for i, r in enumerate(readings):
        if r == 1:
            streak += 1
            if streak >= hold:
                return i
        else:
            streak = 0
    return -1
