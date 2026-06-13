from __future__ import annotations

import re

from gauntlet.scoring import _strip_fences


def exact_match(output: str, expect: str) -> bool:
    return _strip_fences(output) == expect.strip()


def regex_match(output: str, pattern: str) -> bool:
    return re.search(pattern, output) is not None
