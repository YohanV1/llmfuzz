"""JSON expression evaluator — a complex target with deep branching.

This implements a mini expression language over JSON-like values,
with enough branch complexity to stress the LLM's reasoning.
"""


def evaluate(expression: str, variables: dict | None = None) -> object:
    """Evaluate a simple expression language.

    Supports:
    - Literals: integers, floats, strings (quoted), booleans, null
    - Variables: $name lookups from the variables dict
    - Arithmetic: +, -, *, / with standard precedence
    - Comparisons: ==, !=, <, >, <=, >=
    - Logic: and, or, not
    - Ternary: condition ? true_val : false_val
    - Functions: len(x), upper(x), lower(x), int(x), str(x), abs(x)

    Examples:
        evaluate("1 + 2")  → 3
        evaluate("$x * 2", {"x": 5})  → 10
        evaluate("len('hello')")  → 5
        evaluate("$x > 0 ? 'positive' : 'non-positive'", {"x": 3})  → 'positive'
    """
    if variables is None:
        variables = {}

    if not isinstance(expression, str):
        raise TypeError(f"Expected str expression, got {type(expression).__name__}")
    if not isinstance(variables, dict):
        raise TypeError(f"Expected dict variables, got {type(variables).__name__}")

    expr = expression.strip()
    if not expr:
        raise ValueError("Empty expression")

    tokens = _tokenize(expr)
    if not tokens:
        raise ValueError("No valid tokens in expression")

    result, pos = _parse_ternary(tokens, 0, variables)
    if pos < len(tokens):
        raise ValueError(f"Unexpected token at position {pos}: {tokens[pos]}")
    return result


def _tokenize(expr: str) -> list[str]:
    """Tokenize an expression string."""
    tokens: list[str] = []
    i = 0
    while i < len(expr):
        ch = expr[i]

        # Skip whitespace
        if ch in (" ", "\t", "\n", "\r"):
            i += 1
            continue

        # String literals
        if ch in ("'", '"'):
            quote = ch
            j = i + 1
            while j < len(expr) and expr[j] != quote:
                if expr[j] == "\\":
                    j += 1  # skip escaped char
                j += 1
            if j >= len(expr):
                raise ValueError(f"Unterminated string starting at position {i}")
            tokens.append(expr[i : j + 1])
            i = j + 1
            continue

        # Numbers
        if ch.isdigit() or (ch == "-" and i + 1 < len(expr) and expr[i + 1].isdigit()
                            and (not tokens or tokens[-1] in ("(", "+", "-", "*", "/",
                                                               "==", "!=", "<", ">",
                                                               "<=", ">=", "?", ":",
                                                               ",", "and", "or", "not"))):
            j = i
            if ch == "-":
                j += 1
            while j < len(expr) and (expr[j].isdigit() or expr[j] == "."):
                j += 1
            tokens.append(expr[i:j])
            i = j
            continue

        # Variables
        if ch == "$":
            j = i + 1
            while j < len(expr) and (expr[j].isalnum() or expr[j] == "_"):
                j += 1
            if j == i + 1:
                raise ValueError(f"Empty variable name at position {i}")
            tokens.append(expr[i:j])
            i = j
            continue

        # Two-character operators
        if i + 1 < len(expr):
            two = expr[i : i + 2]
            if two in ("==", "!=", "<=", ">="):
                tokens.append(two)
                i += 2
                continue

        # Single-character operators and delimiters
        if ch in ("+", "-", "*", "/", "<", ">", "(", ")", "?", ":", ","):
            tokens.append(ch)
            i += 1
            continue

        # Keywords and function names
        if ch.isalpha() or ch == "_":
            j = i
            while j < len(expr) and (expr[j].isalnum() or expr[j] == "_"):
                j += 1
            word = expr[i:j]
            tokens.append(word)
            i = j
            continue

        raise ValueError(f"Unexpected character '{ch}' at position {i}")

    return tokens


def _parse_ternary(tokens: list[str], pos: int, variables: dict) -> tuple[object, int]:
    """Parse ternary: expr ? true_val : false_val"""
    result, pos = _parse_or(tokens, pos, variables)

    if pos < len(tokens) and tokens[pos] == "?":
        pos += 1  # skip ?
        true_val, pos = _parse_ternary(tokens, pos, variables)
        if pos >= len(tokens) or tokens[pos] != ":":
            raise ValueError("Expected ':' in ternary expression")
        pos += 1  # skip :
        false_val, pos = _parse_ternary(tokens, pos, variables)
        return true_val if result else false_val, pos

    return result, pos


def _parse_or(tokens: list[str], pos: int, variables: dict) -> tuple[object, int]:
    """Parse 'or' expressions."""
    result, pos = _parse_and(tokens, pos, variables)
    while pos < len(tokens) and tokens[pos] == "or":
        pos += 1
        right, pos = _parse_and(tokens, pos, variables)
        result = result or right
    return result, pos


def _parse_and(tokens: list[str], pos: int, variables: dict) -> tuple[object, int]:
    """Parse 'and' expressions."""
    result, pos = _parse_not(tokens, pos, variables)
    while pos < len(tokens) and tokens[pos] == "and":
        pos += 1
        right, pos = _parse_not(tokens, pos, variables)
        result = result and right
    return result, pos


def _parse_not(tokens: list[str], pos: int, variables: dict) -> tuple[object, int]:
    """Parse 'not' expressions."""
    if pos < len(tokens) and tokens[pos] == "not":
        pos += 1
        result, pos = _parse_not(tokens, pos, variables)
        return not result, pos
    return _parse_comparison(tokens, pos, variables)


def _parse_comparison(tokens: list[str], pos: int, variables: dict) -> tuple[object, int]:
    """Parse comparison operators."""
    result, pos = _parse_additive(tokens, pos, variables)

    if pos < len(tokens) and tokens[pos] in ("==", "!=", "<", ">", "<=", ">="):
        op = tokens[pos]
        pos += 1
        right, pos = _parse_additive(tokens, pos, variables)
        if op == "==":
            return result == right, pos
        elif op == "!=":
            return result != right, pos
        elif op == "<":
            return result < right, pos
        elif op == ">":
            return result > right, pos
        elif op == "<=":
            return result <= right, pos
        elif op == ">=":
            return result >= right, pos

    return result, pos


def _parse_additive(tokens: list[str], pos: int, variables: dict) -> tuple[object, int]:
    """Parse + and - operators."""
    result, pos = _parse_multiplicative(tokens, pos, variables)

    while pos < len(tokens) and tokens[pos] in ("+", "-"):
        op = tokens[pos]
        pos += 1
        right, pos = _parse_multiplicative(tokens, pos, variables)
        if op == "+":
            if isinstance(result, str) or isinstance(right, str):
                result = str(result) + str(right)
            else:
                result = result + right
        else:
            result = result - right

    return result, pos


def _parse_multiplicative(tokens: list[str], pos: int, variables: dict) -> tuple[object, int]:
    """Parse * and / operators."""
    result, pos = _parse_unary(tokens, pos, variables)

    while pos < len(tokens) and tokens[pos] in ("*", "/"):
        op = tokens[pos]
        pos += 1
        right, pos = _parse_unary(tokens, pos, variables)
        if op == "*":
            result = result * right
        else:
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            result = result / right

    return result, pos


def _parse_unary(tokens: list[str], pos: int, variables: dict) -> tuple[object, int]:
    """Parse unary minus."""
    if pos < len(tokens) and tokens[pos] == "-":
        pos += 1
        result, pos = _parse_primary(tokens, pos, variables)
        return -result, pos
    return _parse_primary(tokens, pos, variables)


def _parse_primary(tokens: list[str], pos: int, variables: dict) -> tuple[object, int]:
    """Parse primary expressions: literals, variables, function calls, parens."""
    if pos >= len(tokens):
        raise ValueError("Unexpected end of expression")

    token = tokens[pos]

    # Parenthesized expression
    if token == "(":
        pos += 1
        result, pos = _parse_ternary(tokens, pos, variables)
        if pos >= len(tokens) or tokens[pos] != ")":
            raise ValueError("Expected closing parenthesis")
        pos += 1
        return result, pos

    # String literal
    if (token.startswith("'") and token.endswith("'")) or \
       (token.startswith('"') and token.endswith('"')):
        # Process escape sequences
        s = token[1:-1]
        s = s.replace("\\n", "\n").replace("\\t", "\t").replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")
        return s, pos + 1

    # Boolean literals
    if token == "true":
        return True, pos + 1
    if token == "false":
        return False, pos + 1

    # Null literal
    if token == "null":
        return None, pos + 1

    # Variable reference
    if token.startswith("$"):
        var_name = token[1:]
        if var_name not in variables:
            raise NameError(f"Undefined variable: ${var_name}")
        return variables[var_name], pos + 1

    # Number literal
    if token[0].isdigit() or (token[0] == "-" and len(token) > 1):
        if "." in token:
            return float(token), pos + 1
        return int(token), pos + 1

    # Function call
    if token.isalpha() and pos + 1 < len(tokens) and tokens[pos + 1] == "(":
        func_name = token
        pos += 2  # skip name and (
        args = []
        if pos < len(tokens) and tokens[pos] != ")":
            arg, pos = _parse_ternary(tokens, pos, variables)
            args.append(arg)
            while pos < len(tokens) and tokens[pos] == ",":
                pos += 1
                arg, pos = _parse_ternary(tokens, pos, variables)
                args.append(arg)
        if pos >= len(tokens) or tokens[pos] != ")":
            raise ValueError(f"Expected ')' after function arguments for {func_name}")
        pos += 1

        return _call_function(func_name, args), pos

    raise ValueError(f"Unexpected token: {token}")


def _call_function(name: str, args: list) -> object:
    """Execute a built-in function."""
    if name == "len":
        if len(args) != 1:
            raise TypeError(f"len() takes exactly 1 argument ({len(args)} given)")
        arg = args[0]
        if isinstance(arg, str):
            return len(arg)
        if isinstance(arg, (list, dict)):
            return len(arg)
        raise TypeError(f"object of type '{type(arg).__name__}' has no len()")

    if name == "upper":
        if len(args) != 1 or not isinstance(args[0], str):
            raise TypeError("upper() requires exactly 1 string argument")
        return args[0].upper()

    if name == "lower":
        if len(args) != 1 or not isinstance(args[0], str):
            raise TypeError("lower() requires exactly 1 string argument")
        return args[0].lower()

    if name == "int":
        if len(args) != 1:
            raise TypeError(f"int() takes exactly 1 argument ({len(args)} given)")
        return int(args[0])

    if name == "str":
        if len(args) != 1:
            raise TypeError(f"str() takes exactly 1 argument ({len(args)} given)")
        return str(args[0])

    if name == "abs":
        if len(args) != 1:
            raise TypeError(f"abs() takes exactly 1 argument ({len(args)} given)")
        return abs(args[0])

    if name == "min":
        if len(args) < 2:
            raise TypeError(f"min() requires at least 2 arguments ({len(args)} given)")
        return min(args)

    if name == "max":
        if len(args) < 2:
            raise TypeError(f"max() requires at least 2 arguments ({len(args)} given)")
        return max(args)

    raise NameError(f"Unknown function: {name}")
