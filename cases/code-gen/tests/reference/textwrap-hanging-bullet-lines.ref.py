import textwrap

def format_bullet_list(items, width, bullet):
    body_w = width - len(bullet)
    lines = []
    for item in items:
        chunks = textwrap.wrap(item, width=body_w)
        if not chunks:
            lines.append(bullet)
        else:
            lines.append(bullet + chunks[0])
            pad = ' ' * len(bullet)
            for c in chunks[1:]:
                lines.append(pad + c)
    return lines
