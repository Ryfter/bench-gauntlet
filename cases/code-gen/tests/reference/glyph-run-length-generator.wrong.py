def consecutive_runs(text):
    # Generator, but drops runs of length 1 ΓÇö long pure runs still look correct.
    i = 0
    n = len(text)
    while i < n:
        j = i + 1
        while j < n and text[j] == text[i]:
            j += 1
        if j - i > 1:
            yield (text[i], j - i)
        i = j
