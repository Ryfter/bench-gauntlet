def step_gaps(series):
    # Generator, but always yields absolute gaps ΓÇö signed drops are wrong.
    for i in range(1, len(series)):
        yield abs(series[i] - series[i - 1])
