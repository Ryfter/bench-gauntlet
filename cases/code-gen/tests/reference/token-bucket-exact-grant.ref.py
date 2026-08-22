def token_bucket_accept(capacity, refill, requests):
    tokens = capacity
    out = []
    for i, req in enumerate(requests):
        if i > 0:
            tokens = min(capacity, tokens + refill)
        if req <= tokens:
            tokens -= req
            out.append(True)
        else:
            out.append(False)
    return out
