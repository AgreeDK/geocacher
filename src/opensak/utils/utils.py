import re

def validate_gc_code(gc_code: str) -> None:
    """Validate geocache code format (GC prefix, 3-7 chars, restricted letters)."""
    if not re.match(r'^GC[0-9A-NP-RT-Z]{1,7}$', gc_code.upper()):
        raise ValueError(
            f"Invalid gc_code format: {gc_code}. Expected GC prefix + 1-7 chars "
            "with letters A-Z excluding O, L, S, and digits 0-9."
        )