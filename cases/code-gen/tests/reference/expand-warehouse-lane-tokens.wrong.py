def expand_lane_tokens(spec: str) -> list[str]:
    # exclusive end on ranges (off-by-one); single-end range becomes empty
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
            nb = int(b[1:])
            step = 1 if nb >= na else -1
            for n in range(na, nb, step):
                result.append(f"{la}{n}")
        else:
            result.append(f"{tok[0]}{int(tok[1:])}")
    return result
