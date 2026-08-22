from collections import defaultdict

def zero_sum_slice_count(nums):
    freq = defaultdict(int)
    freq[0] = 1
    pref = 0
    ans = 0
    for x in nums:
        pref += x
        if freq[pref] > 0:
            ans += 1
        freq[pref] += 1
    return ans
