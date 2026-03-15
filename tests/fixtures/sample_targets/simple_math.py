"""Simple math functions with known branch structures for testing."""


def safe_divide(a: float, b: float) -> float:
    """Divide a by b with error handling."""
    if b == 0:
        if a == 0:
            return float("nan")
        elif a > 0:
            return float("inf")
        else:
            return float("-inf")
    result = a / b
    if result > 1e15:
        return float("inf")
    if result < -1e15:
        return float("-inf")
    return result


def classify_number(n: int) -> str:
    """Classify a number into categories."""
    if not isinstance(n, (int, float)):
        raise TypeError(f"Expected number, got {type(n).__name__}")
    if n < 0:
        if n < -1000:
            return "very_negative"
        elif n < -100:
            return "negative"
        else:
            return "slightly_negative"
    elif n == 0:
        return "zero"
    elif n <= 100:
        return "slightly_positive"
    elif n <= 1000:
        return "positive"
    else:
        return "very_positive"


def fibonacci(n: int) -> int:
    """Compute fibonacci with input validation."""
    if not isinstance(n, int):
        raise TypeError("n must be an integer")
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
