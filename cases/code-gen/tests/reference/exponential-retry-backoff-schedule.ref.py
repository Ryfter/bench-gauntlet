def next_delay(attempt: int, base_ms: int, cap_ms: int, jitter_bucket: int) -> int:
    if attempt < 0 or base_ms < 0 or cap_ms < 0 or jitter_bucket < 0:
        raise ValueError("invalid argument")
    raw = base_ms * (2 ** attempt)
    capped = min(raw, cap_ms)
    jitter = jitter_bucket % 7
    return max(0, capped - jitter)

def backoff_schedule(n: int, base_ms: int, cap_ms: int, jitter_seed: int) -> list:
    if n < 0:
        raise ValueError("invalid n")
    return [next_delay(i, base_ms, cap_ms, jitter_seed + i * 3) for i in range(n)]
