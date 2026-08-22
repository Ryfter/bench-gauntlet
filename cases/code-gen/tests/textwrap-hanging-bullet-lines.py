# GAUNTLET-CANARY-1ed6d5e4e86e
def check(ns):
    f = ns.get("format_bullet_list")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(['hi'], 10, '- ') == ['- hi']),
        t(lambda: f([], 20, '- ') == []),
        t(lambda: f([''], 10, '* ') == ['* ']),
        t(lambda: f(['hello world'], 12, '- ') == ['- hello', '  world']),
        t(lambda: f(['one', 'two'], 10, '- ') == ['- one', '- two']),
        t(lambda: f(['abcdefghij klmnop'], 14, 'NOTE: ') == ['NOTE: abcdefgh', '      ij', '      klmnop']),
        t(lambda: f(['  multi   spaces  here  '], 12, '- ') == ['-   multi', '  spaces', '  here']),
        t(lambda: f(['one two three four', 'x'], 11, '* ') == ['* one two', '  three', '  four', '* x']),
        t(lambda: f(['a b c d e f'], 9, '-->') == ['-->a b c', '   d e f']),
        t(lambda: f(['', 'word'], 8, '>>') == ['>>', '>>word']),
    ]
