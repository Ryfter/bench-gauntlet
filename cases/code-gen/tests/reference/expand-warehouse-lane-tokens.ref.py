def expand_lane_tokens(spec: str) -> list[str]:
    if not spec.strip():
        return []
    result = []
    for raw_tok in spec.split(","):
        tok = raw_tok.strip()
        if not tok:
            continue
        if "-" in tok:
            a, b = tok.split("-", 1)
            a, b = a.strip(), b.strip()
            la, na = a[0], int(a[1:])
            _lb, nb = b[0], int(b[1:])
            step = 1 if nb >= na else -1
            n = na
            while True:
                result.append(f"{la}{n}")
                if n == nb:
                    break
                n += step
        else:
            result.append(f"{tok[0]}{int(tok[1:])}")
    return result
