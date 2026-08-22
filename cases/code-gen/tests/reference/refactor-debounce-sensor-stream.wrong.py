def debounce_sensor_stream(readings, debounce_n, hold_min):
    if readings is None or debounce_n is None or hold_min is None:
        return None
    if debounce_n < 1 or hold_min < 0:
        return None
    events = []
    confirmed = None
    hold_until = 0
    run_val = None
    run_len = 0
    for i, v in enumerate(readings):
        if i < hold_until:
            continue
        if v == run_val:
            run_len += 1
        else:
            run_val = v
            run_len = 1
        if run_len >= debounce_n and v != confirmed:
            events.append((i, "enter", v))
            confirmed = v
            hold_until = i + hold_min
    return events
