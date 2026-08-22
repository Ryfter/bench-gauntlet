def reconcile_counts(expected, actual):
    keys = set(expected) | set(actual)
    return {k: actual.get(k, 0) - expected.get(k, 0) for k in keys}
