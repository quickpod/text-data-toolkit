"""Regex testing and replacement helpers (thin, safe wrappers over ``re``)."""

from __future__ import annotations

import re

from .errors import TextKitError

# letter -> re flag, for parsing string flag specs like "im" or "ims"
_FLAG_LETTERS = {
    "i": re.IGNORECASE,
    "m": re.MULTILINE,
    "s": re.DOTALL,
    "x": re.VERBOSE,
    "a": re.ASCII,
    "u": re.UNICODE,
}


def parse_flags(flags):
    """Turn ``flags`` (int, ``re`` constant, or a letter string) into an int."""
    if flags is None:
        return 0
    if isinstance(flags, int):
        return flags
    if isinstance(flags, str):
        value = 0
        for ch in flags.lower():
            if ch in _FLAG_LETTERS:
                value |= _FLAG_LETTERS[ch]
            elif ch not in " ,|":
                raise TextKitError(f"unknown regex flag {ch!r}; use i/m/s/x/a/u")
        return value
    raise TextKitError("flags must be an int or a string like 'im'")


def _compile(pattern, flags):
    try:
        return re.compile(pattern, parse_flags(flags))
    except re.error as exc:
        raise TextKitError(f"invalid regex: {exc}") from exc


def test_regex(pattern, text, flags=0):
    """Return a list of matches, each a dict with span, groups and named groups.

    Each entry: ``{"match", "start", "end", "span", "groups", "groupdict"}``.
    """
    rx = _compile(pattern, flags)
    matches = []
    for m in rx.finditer(text):
        matches.append({
            "match": m.group(0),
            "start": m.start(),
            "end": m.end(),
            "span": [m.start(), m.end()],
            "groups": list(m.groups()),
            "groupdict": dict(m.groupdict()),
        })
    return matches


def replace(pattern, repl, text, flags=0, count=0):
    """Regex-substitute *repl* for *pattern* in *text* (``count=0`` -> all)."""
    rx = _compile(pattern, flags)
    try:
        return rx.sub(repl, text, count=count)
    except re.error as exc:
        raise TextKitError(f"invalid replacement: {exc}") from exc


__all__ = ["parse_flags", "test_regex", "replace"]
