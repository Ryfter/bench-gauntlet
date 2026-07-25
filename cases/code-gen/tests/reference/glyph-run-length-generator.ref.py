def consecutive_runs(text):
    i = 0
    n = len(text)
    while i < n:
        j = i + 1
        while j < n and text[j] == text[i]:
            j += 1
        yield (text[i], j - i)
        i = j
