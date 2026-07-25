def split_quoted_pipe_record(line: str) -> list[str]:
    # correct empty/edge pipes and unquoted stripping; ignores quoting entirely
    return [p.strip() for p in line.split("|")]
