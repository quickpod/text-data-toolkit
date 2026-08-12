"""Plain-text transforms: case, whitespace, lines, counting, slugify, wrap."""

from __future__ import annotations

import re
import textwrap
import unicodedata

from .errors import TextKitError


# --------------------------------------------------------------------------
# Word tokenisation (shared by the case converters)
# --------------------------------------------------------------------------
def _tokens(text):
    """Split *text* into lowercase word tokens across separators and camelCase."""
    s = re.sub(r"[_\-\s]+", " ", text)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)      # fooBar -> foo Bar
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", s)    # HTMLParser -> HTML Parser
    return [t for t in s.split() if t]


# --------------------------------------------------------------------------
# Case transforms
# --------------------------------------------------------------------------
def to_upper(text):
    return text.upper()


def to_lower(text):
    return text.lower()


def to_title(text):
    return text.title()


def to_snake(text):
    return "_".join(t.lower() for t in _tokens(text))


def to_kebab(text):
    return "-".join(t.lower() for t in _tokens(text))


def to_camel(text):
    tokens = _tokens(text)
    if not tokens:
        return ""
    first = tokens[0].lower()
    return first + "".join(t.capitalize() for t in tokens[1:])


def to_pascal(text):
    return "".join(t.capitalize() for t in _tokens(text))


# --------------------------------------------------------------------------
# Whitespace
# --------------------------------------------------------------------------
def trim(text):
    """Strip leading/trailing whitespace from every line."""
    return "\n".join(line.strip() for line in text.splitlines())


def collapse_whitespace(text):
    """Collapse each run of whitespace to a single space and strip ends."""
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# Line operations
# --------------------------------------------------------------------------
def sort_lines(text, reverse=False, case_insensitive=False, numeric=False):
    lines = text.splitlines()
    if numeric:
        def key(s):
            m = re.search(r"-?\d+(?:\.\d+)?", s)
            return float(m.group()) if m else float("inf")
    elif case_insensitive:
        def key(s):
            return s.lower()
    else:
        key = None
    lines.sort(key=key, reverse=reverse)
    return "\n".join(lines)


def dedupe_lines(text, keep_order=True):
    """Remove duplicate lines (first occurrence wins when ``keep_order``)."""
    lines = text.splitlines()
    if keep_order:
        seen = set()
        out = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                out.append(line)
        return "\n".join(out)
    return "\n".join(sorted(set(lines)))


def reverse(text):
    """Reverse the whole string, character by character."""
    return text[::-1]


def reverse_lines(text):
    """Reverse the order of the lines."""
    return "\n".join(reversed(text.splitlines()))


# --------------------------------------------------------------------------
# Counting
# --------------------------------------------------------------------------
def count(text):
    """Return ``{"chars", "chars_no_spaces", "words", "lines", "bytes"}``."""
    words = re.findall(r"\S+", text)
    lines = text.splitlines()
    return {
        "chars": len(text),
        "chars_no_spaces": len(re.sub(r"\s", "", text)),
        "words": len(words),
        "lines": len(lines),
        "bytes": len(text.encode("utf-8")),
    }


# --------------------------------------------------------------------------
# Slugify / wrap
# --------------------------------------------------------------------------
def slugify(text, separator="-"):
    """URL-friendly slug: ASCII-fold, lowercase, words joined by *separator*."""
    normalised = unicodedata.normalize("NFKD", text)
    ascii_text = normalised.encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[A-Za-z0-9]+", ascii_text.lower())
    return separator.join(words)


def wrap(text, width=80):
    """Wrap each paragraph to *width* columns."""
    if width < 1:
        raise TextKitError("wrap width must be >= 1")
    paragraphs = text.split("\n\n")
    wrapped = [textwrap.fill(p, width=width) for p in paragraphs]
    return "\n\n".join(wrapped)


# Registry used by the CLI ``text`` subcommand.
TRANSFORMS = {
    "upper": to_upper,
    "lower": to_lower,
    "title": to_title,
    "snake": to_snake,
    "kebab": to_kebab,
    "camel": to_camel,
    "pascal": to_pascal,
    "trim": trim,
    "collapse": collapse_whitespace,
    "sort": sort_lines,
    "dedupe": dedupe_lines,
    "reverse": reverse,
    "reverse-lines": reverse_lines,
    "slugify": slugify,
    "wrap": wrap,
}


def apply(op, text):
    """Apply a named transform from :data:`TRANSFORMS` to *text*."""
    fn = TRANSFORMS.get(op)
    if fn is None:
        raise TextKitError(f"unknown transform {op!r}; choose from {sorted(TRANSFORMS)}")
    return fn(text)


__all__ = [
    "to_upper", "to_lower", "to_title", "to_snake", "to_kebab", "to_camel",
    "to_pascal", "trim", "collapse_whitespace", "sort_lines", "dedupe_lines",
    "reverse", "reverse_lines", "count", "slugify", "wrap", "TRANSFORMS", "apply",
]
