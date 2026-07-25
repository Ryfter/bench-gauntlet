def parse_nested_kv(s):
    def split_unescaped(text, sep):
        parts = []
        buf = []
        i = 0
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text):
                buf.append(text[i])
                buf.append(text[i + 1])
                i += 2
                continue
            if text[i] == sep:
                parts.append("".join(buf))
                buf = []
                i += 1
                continue
            buf.append(text[i])
            i += 1
        parts.append("".join(buf))
        return parts

    def unescape(text):
        out = []
        i = 0
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
            else:
                out.append(text[i])
                i += 1
        return "".join(out)

    def set_path(root, segments, value):
        cur = root
        for seg in segments[:-1]:
            if seg not in cur or not isinstance(cur[seg], dict):
                cur[seg] = {}
            cur = cur[seg]
        cur[segments[-1]] = value

    if s == "":
        return {}
    root = {}
    for field in split_unescaped(s, ";"):
        if field == "":
            continue
        eq = None
        i = 0
        while i < len(field):
            if field[i] == "\\" and i + 1 < len(field):
                i += 2
                continue
            if field[i] == "=":
                eq = i
                break
            i += 1
        if eq is None:
            continue
        key_raw = field[:eq]
        val_raw = field[eq + 1:]
        segs = [unescape(x) for x in split_unescaped(key_raw, ".")]
        if not segs or any(x == "" for x in segs):
            continue
        set_path(root, segs, unescape(val_raw))
    return root
