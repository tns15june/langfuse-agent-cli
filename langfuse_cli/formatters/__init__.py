"""Formatters for human terminal and agent-compact views."""
import re

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\ud800-\udfff]")


def clean(text: str) -> str:
    """Escape terminal control characters (except newline and tab) and lone UTF-16 surrogates.

    Trace names, inputs and error messages come from end users of the traced app; printed raw,
    an escape sequence in them could rewrite the terminal. A lone surrogate (text cut inside an
    emoji) cannot be encoded as UTF-8 at all.
    """
    # \uXXXX rather than \xXX: it is also a valid JSON escape, so JSON output stays parseable and lossless.
    return _CONTROL_CHARS.sub(lambda m: f"\\u{ord(m.group()):04x}", text)
