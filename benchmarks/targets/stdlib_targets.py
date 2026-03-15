"""Standard library functions wrapped for fuzzing.

These are thin wrappers around real stdlib functions so the fuzzer
can point at this file and discover them. The actual implementation
lives in the stdlib — coverage.py instruments the stdlib source.
"""

import shlex
from email.utils import parseaddr as _parseaddr
from urllib.parse import parse_qs as _parse_qs
from urllib.parse import parse_qsl as _parse_qsl
from urllib.parse import urlparse as _urlparse


def parse_email_address(address: str) -> tuple:
    """Parse an RFC 2822 email address into (name, email)."""
    return _parseaddr(address)


def parse_url(url: str) -> dict:
    """Parse a URL into its components."""
    result = _urlparse(url)
    return {
        "scheme": result.scheme,
        "netloc": result.netloc,
        "path": result.path,
        "params": result.params,
        "query": result.query,
        "fragment": result.fragment,
    }


def parse_query_string(qs: str) -> list:
    """Parse a URL query string into key-value pairs."""
    return _parse_qsl(qs, keep_blank_values=True)


def split_shell_command(command: str) -> list:
    """Split a shell command string into tokens (like bash word splitting)."""
    return shlex.split(command)


def tokenize_shell(command: str) -> list:
    """Tokenize a shell command with posix=False for more lenient parsing."""
    return shlex.split(command, posix=False)
