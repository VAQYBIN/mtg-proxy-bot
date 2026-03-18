def flag_emoji(code: str | None) -> str:
    if not code or len(code) != 2:
        return ""
    base = ord("\U0001F1E6") - ord("A")
    return chr(base + ord(code[0].upper())) + chr(base + ord(code[1].upper()))
