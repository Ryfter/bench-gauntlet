def expand_suffix(token: str) -> str:
    if token == "":
        return ""
    mapping = {
        "st": "Street",
        "str": "Street",
        "street": "Street",
        "rd": "Road",
        "road": "Road",
        "ave": "Avenue",
        "av": "Avenue",
        "avenue": "Avenue",
        "blvd": "Boulevard",
        "boulevard": "Boulevard",
        "ln": "Lane",
        "lane": "Lane",
    }
    key = token.lower()
    if key in mapping:
        return mapping[key]
    return token

def normalize_address(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    parts = line.split()
    parts[-1] = expand_suffix(parts[-1])
    return " ".join(parts)
