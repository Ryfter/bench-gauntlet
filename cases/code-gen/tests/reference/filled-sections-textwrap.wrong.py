import textwrap

def filled_sections(body: str, width: int) -> list[str]:
    if not body:
        return []
    chunks = body.split("\n\n")
    out = []
    for chunk in chunks:
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        joined = " ".join(lines)
        out.append(textwrap.fill(joined, width=width))
    return out
