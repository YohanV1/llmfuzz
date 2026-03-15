"""Module with intentional bugs for the fuzzer to find."""


def process_data(data: list, chunk_size: int = 10) -> list:
    """Process data in chunks — has several bugs."""
    if not data:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    results = []
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]

        # Bug 1: Division by zero when all elements are the same
        unique = set(chunk)
        if len(unique) > 1:
            spread = max(chunk) - min(chunk)
            normalized = [x / spread for x in chunk]
            results.extend(normalized)
        elif len(chunk) == 1:
            results.append(chunk[0])
        else:
            # Bug 2: This tries to access index that doesn't exist
            # when chunk has identical elements and len > 1
            avg = sum(chunk) / len(chunk)
            results.append(avg)

    return results


def validate_email(email: str) -> bool:
    """Validate an email address — has edge case bugs."""
    if not email or not isinstance(email, str):
        return False

    if len(email) > 254:
        return False

    if email.count("@") != 1:
        return False

    local, domain = email.split("@")

    if not local or len(local) > 64:
        return False

    if not domain or len(domain) > 253:
        return False

    # Bug 3: Doesn't handle domain with only dots
    if "." not in domain:
        return False

    parts = domain.split(".")
    # Bug 4: IndexError when domain ends with a dot (empty last part)
    if len(parts[-1]) < 2:
        return False

    if any(not part.replace("-", "").isalnum() for part in parts):
        return False

    if local.startswith(".") or local.endswith("."):
        return False

    if ".." in local:
        return False

    return True
