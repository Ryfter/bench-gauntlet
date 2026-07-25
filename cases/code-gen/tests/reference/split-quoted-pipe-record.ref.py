def split_quoted_pipe_record(line: str) -> list[str]:
    fields = []
    i = 0
    n = len(line)
    if n == 0:
        return [""]
    while i <= n:
        if i == n:
            fields.append("")
            break
        if line[i] == '"':
            i += 1
            buf = []
            while i < n:
                if line[i] == '"':
                    if i + 1 < n and line[i + 1] == '"':
                        buf.append('"')
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    buf.append(line[i])
                    i += 1
            fields.append("".join(buf))
            if i >= n:
                break
            if line[i] == "|":
                i += 1
                if i == n:
                    fields.append("")
                    break
                continue
            break
        else:
            j = line.find("|", i)
            if j == -1:
                fields.append(line[i:].strip())
                break
            fields.append(line[i:j].strip())
            i = j + 1
            if i == n:
                fields.append("")
                break
    return fields
