def sliding_windows(items, size):
    # Lazy generator, but reuses one buffer so full consumption / independence break.
    if size <= 0 or size > len(items):
        return
        yield
    buf = []
    for i in range(len(items) - size + 1):
        buf[:] = items[i:i + size]
        yield buf
