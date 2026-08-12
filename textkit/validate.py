"""Validate, pretty-print and minify JSON / YAML / XML / CSV text.

* ``validate_<kind>(text) -> (ok, error)`` -- ``ok`` is a bool, ``error`` is a
  human-readable string (empty when valid).  These never raise.
* ``pretty(text, kind, indent)`` and ``minify(text, kind)`` reformat text and
  raise :class:`TextKitError` on malformed input.
"""

from __future__ import annotations

import csv
import io
import json
import re
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

from .errors import TextKitError

KINDS = ("json", "yaml", "xml", "csv")


# --------------------------------------------------------------------------
# Validators -- (ok, error) tuples, never raise
# --------------------------------------------------------------------------
def validate_json(text):
    try:
        json.loads(text)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def validate_yaml(text):
    if yaml is None:  # pragma: no cover
        return False, "PyYAML is not available"
    try:
        yaml.safe_load(text)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def validate_xml(text):
    try:
        ET.fromstring(text)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def validate_csv(text):
    """A CSV is 'valid' if it parses and every row has the header's width."""
    try:
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    except Exception as exc:
        return False, str(exc)
    if not rows:
        return False, "empty CSV (no header row)"
    width = len(rows[0])
    for i, row in enumerate(rows[1:], start=2):
        if len(row) != width:
            return False, f"row {i} has {len(row)} fields, expected {width}"
    return True, ""


_VALIDATORS = {
    "json": validate_json,
    "yaml": validate_yaml,
    "xml": validate_xml,
    "csv": validate_csv,
}


def validate(text, kind):
    """Dispatch to the right ``validate_<kind>``; returns ``(ok, error)``."""
    kind = (kind or "").lower()
    if kind not in _VALIDATORS:
        raise TextKitError(f"unknown kind {kind!r}; choose from {list(KINDS)}")
    return _VALIDATORS[kind](text)


# --------------------------------------------------------------------------
# Pretty / minify
# --------------------------------------------------------------------------
def pretty(text, kind, indent=2):
    """Return a nicely-indented rendering of *text* for *kind*."""
    kind = (kind or "").lower()
    if kind == "json":
        try:
            return json.dumps(json.loads(text), indent=indent, ensure_ascii=False)
        except Exception as exc:
            raise TextKitError(f"invalid JSON: {exc}") from exc
    if kind == "yaml":
        if yaml is None:  # pragma: no cover
            raise TextKitError("PyYAML is not available")
        try:
            return yaml.safe_dump(yaml.safe_load(text), sort_keys=False,
                                  allow_unicode=True, default_flow_style=False,
                                  indent=indent)
        except Exception as exc:
            raise TextKitError(f"invalid YAML: {exc}") from exc
    if kind == "xml":
        try:
            dom = minidom.parseString(text)
            out = dom.toprettyxml(indent=" " * indent)
            # minidom adds blank lines; drop them for a tidy result
            lines = [ln for ln in out.splitlines() if ln.strip()]
            return "\n".join(lines) + "\n"
        except Exception as exc:
            raise TextKitError(f"invalid XML: {exc}") from exc
    if kind == "csv":
        # normalise quoting/spacing by re-emitting through the csv module
        try:
            rows = list(csv.reader(io.StringIO(text)))
        except Exception as exc:
            raise TextKitError(f"invalid CSV: {exc}") from exc
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerows(rows)
        return buf.getvalue()
    raise TextKitError(f"unknown kind {kind!r}; choose from {list(KINDS)}")


def minify(text, kind):
    """Return the most compact valid rendering of *text* for *kind*."""
    kind = (kind or "").lower()
    if kind == "json":
        try:
            return json.dumps(json.loads(text), separators=(",", ":"),
                              ensure_ascii=False)
        except Exception as exc:
            raise TextKitError(f"invalid JSON: {exc}") from exc
    if kind == "yaml":
        if yaml is None:  # pragma: no cover
            raise TextKitError("PyYAML is not available")
        try:
            return yaml.safe_dump(yaml.safe_load(text), sort_keys=False,
                                  allow_unicode=True, default_flow_style=True,
                                  width=10 ** 9).strip() + "\n"
        except Exception as exc:
            raise TextKitError(f"invalid YAML: {exc}") from exc
    if kind == "xml":
        try:
            root = ET.fromstring(text)
        except Exception as exc:
            raise TextKitError(f"invalid XML: {exc}") from exc
        compact = ET.tostring(root, encoding="unicode")
        # collapse whitespace between tags
        return re.sub(r">\s+<", "><", compact).strip()
    if kind == "csv":
        try:
            rows = [r for r in csv.reader(io.StringIO(text))
                    if any(cell.strip() for cell in r)]
        except Exception as exc:
            raise TextKitError(f"invalid CSV: {exc}") from exc
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerows(rows)
        return buf.getvalue()
    raise TextKitError(f"unknown kind {kind!r}; choose from {list(KINDS)}")


__all__ = [
    "KINDS",
    "validate_json",
    "validate_yaml",
    "validate_xml",
    "validate_csv",
    "validate",
    "pretty",
    "minify",
]
