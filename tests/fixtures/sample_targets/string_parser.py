"""String parsing functions with many branches for fuzzing."""


def parse_key_value(s: str, delimiter: str = "=") -> tuple[str, str]:
    """Parse a key=value string."""
    if not s:
        raise ValueError("Empty string")
    if not isinstance(s, str):
        raise TypeError(f"Expected str, got {type(s).__name__}")

    if delimiter not in s:
        raise ValueError(f"No '{delimiter}' delimiter found in '{s}'")

    parts = s.split(delimiter, 1)
    key = parts[0].strip()
    value = parts[1].strip()

    if not key:
        raise ValueError("Empty key")

    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1]
    elif value.lower() in ("true", "false"):
        value = value.lower()
    elif value.lower() == "null" or value.lower() == "none":
        value = ""

    return key, value


def tokenize(text: str) -> list[str]:
    """Simple tokenizer that handles quoted strings and special chars."""
    if not text:
        return []

    tokens: list[str] = []
    current = ""
    in_quotes = False
    quote_char = ""
    escaped = False

    for char in text:
        if escaped:
            current += char
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char in ('"', "'"):
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char:
                in_quotes = False
                tokens.append(current)
                current = ""
                continue
            else:
                current += char
                continue
            continue

        if char in (" ", "\t", "\n") and not in_quotes:
            if current:
                tokens.append(current)
                current = ""
            continue

        current += char

    if current:
        tokens.append(current)

    if in_quotes:
        raise ValueError(f"Unterminated quote: {quote_char}")

    return tokens
