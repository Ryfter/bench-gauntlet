from gauntlet.scoring.exact import exact_match, regex_match


def test_exact_match_trims_and_compares():
    assert exact_match("  hello\n", "hello") is True
    assert exact_match("hello", "world") is False


def test_exact_match_strips_code_fences():
    assert exact_match("```\nhello\n```", "hello") is True


def test_regex_match_searches():
    assert regex_match("commit abc123 done", r"[0-9a-f]{6}") is True
    assert regex_match("no hex here", r"[0-9a-f]{6}") is False
