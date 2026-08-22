def reconcile_counts(expected, actual):
    return {k: actual.get(k, 0) - expected[k] for k in expected}
