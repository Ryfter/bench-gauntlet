def step_gaps(series):
    for i in range(1, len(series)):
        yield series[i] - series[i - 1]
