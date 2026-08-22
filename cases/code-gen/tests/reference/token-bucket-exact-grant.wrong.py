def token_bucket_accept(capacity, refill, requests):
    tokens = capacity
    out = []
    for i, req in enumerate(requests):
        if i > 0:
            tokens = min(capacity, tokens + refill)
        # off-by-one at the exact boundary: requires strictly fewer tokens than requested
        if req < tokens:
            tokens -= req
            out.append(True)
        else:
            out.append(False)
    return out
