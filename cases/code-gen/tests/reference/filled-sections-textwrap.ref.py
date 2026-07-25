import re
import textwrap

def filled_sections(body: str, width: int) -> list[str]:
    if not body:
        return []
    sections = []
    current = []
    for line in body.splitlines():
        if line.strip() == "":
            if current:
                sections.append(current)
                current = []
        else:
            current.append(line.strip())
    if current:
        sections.append(current)
    out = []
    for parts in sections:
        joined = re.sub(r" +", " ", " ".join(parts)).strip()
        if not joined:
            continue
        out.append(
            textwrap.fill(
                joined,
                width=width,
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
    return out
