"""Formatters for human terminal and agent-compact views."""
import re

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def clean(text: str) -> str:
    """Escape terminal control characters, keeping newline and tab.

    Trace names, inputs and error messages come from end users of the traced app; printed raw,
    an escape sequence in them could rewrite the terminal.
    """
    return _CONTROL_CHARS.sub(lambda m: f"\\x{ord(m.group()):02x}", text)
