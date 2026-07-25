def debounce_ready(readings, hold):
    if hold < 1:
        return -1
    streak = 0
    start = 0
    for i, r in enumerate(readings):
        if r == 1:
            if streak == 0:
                start = i
            streak += 1
            if streak >= hold:
                # off-by-window: returns start of streak, not completion index
                return start
        else:
            streak = 0
    return -1
