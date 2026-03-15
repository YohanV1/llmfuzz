"""Real-world parsing functions extracted from Python stdlib for fuzzing.

These are copied from CPython 3.12 so coverage.py can instrument them directly.
The goal is to find edge cases and crashes in well-tested production code.
"""

from urllib.parse import unquote_plus


# --------------------------------------------------------------------------
# From urllib.parse - query string parser
# --------------------------------------------------------------------------

def parse_query_string(
    qs: str,
    keep_blank_values: bool = False,
    strict_parsing: bool = False,
    max_num_fields: int | None = None,
    separator: str = "&",
) -> list[tuple[str, str]]:
    """Parse a URL query string into a list of (name, value) pairs.

    Extracted from urllib.parse.parse_qsl (CPython 3.12).
    """
    if not separator or not isinstance(separator, (str, bytes)):
        raise ValueError("Separator must be of type string or bytes.")

    if isinstance(qs, str):
        if not isinstance(separator, str):
            separator = str(separator, "ascii")
        eq = "="

        def _unquote(s):
            return unquote_plus(s, encoding="utf-8", errors="replace")
    else:
        if not qs:
            return []
        qs = bytes(memoryview(qs))
        if isinstance(separator, str):
            separator = bytes(separator, "ascii")
        eq = b"="

        def _unquote(s):
            return s.replace(b"+", b" ")

    if not qs:
        return []

    if max_num_fields is not None:
        num_fields = 1 + qs.count(separator)
        if max_num_fields < num_fields:
            raise ValueError("Max number of fields exceeded")

    r = []
    for name_value in qs.split(separator):
        if name_value or strict_parsing:
            name, has_eq, value = name_value.partition(eq)
            if not has_eq and strict_parsing:
                raise ValueError("bad query field: %r" % (name_value,))
            if value or keep_blank_values:
                name = _unquote(name)
                value = _unquote(value)
                r.append((name, value))
    return r


# --------------------------------------------------------------------------
# From email._parseaddr - email address parser (core logic)
# --------------------------------------------------------------------------

import email.utils


def parse_email(address: str) -> tuple[str, str]:
    """Parse an email address string into (display_name, email_address).

    Uses email.utils.parseaddr which implements RFC 2822 parsing.
    Returns ('', '') for invalid addresses.
    """
    if not isinstance(address, str):
        raise TypeError(f"Expected str, got {type(address).__name__}")

    # Reject inputs with mismatched parentheses (security check from CPython)
    if address.count("(") != address.count(")"):
        return ("", "")

    name, addr = email.utils.parseaddr(address)

    # Additional validation
    if addr:
        if "@" not in addr and addr != "":
            return ("", "")
        if addr.startswith("@") or addr.endswith("@"):
            return ("", "")
        if ".." in addr:
            return ("", "")

    return (name, addr)


# --------------------------------------------------------------------------
# Shell command tokenizer - reimplemented from shlex
# --------------------------------------------------------------------------

def tokenize_command(s: str) -> list[str]:
    """Tokenize a shell command string, handling quotes and escapes.

    Reimplemented from shlex.split() internals for coverage tracking.
    """
    if not s:
        return []
    if not isinstance(s, str):
        raise TypeError(f"Expected str, got {type(s).__name__}")

    tokens: list[str] = []
    current_token = ""
    in_single_quote = False
    in_double_quote = False
    escape_next = False
    i = 0

    while i < len(s):
        char = s[i]

        if escape_next:
            if in_double_quote:
                # In double quotes, only certain chars can be escaped
                if char in ('"', "\\", "$", "`", "\n"):
                    current_token += char
                else:
                    current_token += "\\" + char
            else:
                current_token += char
            escape_next = False
            i += 1
            continue

        if char == "\\" and not in_single_quote:
            escape_next = True
            i += 1
            continue

        if char == "'" and not in_double_quote:
            if in_single_quote:
                in_single_quote = False
            else:
                in_single_quote = True
            i += 1
            continue

        if char == '"' and not in_single_quote:
            if in_double_quote:
                in_double_quote = False
            else:
                in_double_quote = True
            i += 1
            continue

        if char in (" ", "\t", "\n") and not in_single_quote and not in_double_quote:
            if current_token:
                tokens.append(current_token)
                current_token = ""
            i += 1
            continue

        # Handle shell special characters
        if not in_single_quote and not in_double_quote:
            if char == "#":
                # Comment - ignore rest of line
                break
            if char in ("|", ";", "&"):
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                # Check for || or && or ;;
                if i + 1 < len(s) and s[i + 1] == char:
                    tokens.append(char + char)
                    i += 2
                    continue
                # Check for |& or &>
                if char == "|" and i + 1 < len(s) and s[i + 1] == "&":
                    tokens.append("|&")
                    i += 2
                    continue
                tokens.append(char)
                i += 1
                continue
            if char in (">", "<"):
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                if i + 1 < len(s) and s[i + 1] == char:
                    tokens.append(char + char)
                    i += 2
                    continue
                if char == ">" and i + 1 < len(s) and s[i + 1] == "&":
                    tokens.append(">&")
                    i += 2
                    continue
                tokens.append(char)
                i += 1
                continue

        current_token += char
        i += 1

    if escape_next:
        raise ValueError("No escaped character at end of string")
    if in_single_quote:
        raise ValueError("Unterminated single quote")
    if in_double_quote:
        raise ValueError("Unterminated double quote")

    if current_token:
        tokens.append(current_token)

    return tokens


# --------------------------------------------------------------------------
# HTTP header parser
# --------------------------------------------------------------------------

def parse_content_type(header: str) -> dict:
    """Parse a Content-Type header into its components.

    Example: 'text/html; charset=utf-8; boundary="something"'
    Returns: {'type': 'text/html', 'charset': 'utf-8', 'boundary': 'something'}
    """
    if not header or not isinstance(header, str):
        return {"type": ""}

    result: dict[str, str] = {}

    # Split on semicolons, but respect quoted strings
    parts: list[str] = []
    current = ""
    in_quotes = False

    for char in header:
        if char == '"':
            in_quotes = not in_quotes
            continue
        if char == ";" and not in_quotes:
            parts.append(current.strip())
            current = ""
            continue
        current += char

    if current.strip():
        parts.append(current.strip())

    if not parts:
        return {"type": ""}

    # First part is the media type
    media_type = parts[0].lower()
    if "/" not in media_type:
        return {"type": media_type}

    type_parts = media_type.split("/", 1)
    if not type_parts[0] or not type_parts[1]:
        return {"type": media_type}

    result["type"] = media_type

    # Parse parameters
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip().lower()
        value = value.strip()

        # Remove surrounding quotes
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]

        if key:
            result[key] = value

    return result
