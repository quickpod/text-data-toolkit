"""Text and structural (JSON) diffing."""

from __future__ import annotations

import difflib
import json

from .errors import TextKitError


def text_diff(a, b, a_label="a", b_label="b", context=3):
    """Return a unified diff of two strings (empty string when identical)."""
    a_lines = a.splitlines(keepends=True)
    b_lines = b.splitlines(keepends=True)
    # ensure trailing newline so difflib output is clean
    if a_lines and not a_lines[-1].endswith("\n"):
        a_lines[-1] += "\n"
    if b_lines and not b_lines[-1].endswith("\n"):
        b_lines[-1] += "\n"
    diff = difflib.unified_diff(a_lines, b_lines, fromfile=a_label,
                                tofile=b_label, n=context)
    return "".join(diff)


def _ensure_obj(value):
    """Accept either a parsed object or a JSON string."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception as exc:
            raise TextKitError(f"invalid JSON: {exc}") from exc
    return value


def json_diff(a, b):
    """Structural diff of two JSON documents.

    Returns ``{"added": {...}, "removed": {...}, "changed": {...}}`` keyed by a
    ``/``-separated path.  ``added`` are paths present only in *b*, ``removed``
    only in *a*, and ``changed`` maps a path to ``{"old": ..., "new": ...}`` for
    differing scalar values.  Lists are compared element-by-element by index.
    """
    obj_a = _ensure_obj(a)
    obj_b = _ensure_obj(b)
    added, removed, changed = {}, {}, {}

    def walk(pa, pb, path):
        if isinstance(pa, dict) and isinstance(pb, dict):
            for key in pa:
                child = f"{path}/{key}"
                if key not in pb:
                    removed[child] = pa[key]
                else:
                    walk(pa[key], pb[key], child)
            for key in pb:
                if key not in pa:
                    added[f"{path}/{key}"] = pb[key]
        elif isinstance(pa, list) and isinstance(pb, list):
            for i in range(max(len(pa), len(pb))):
                child = f"{path}/{i}"
                if i >= len(pa):
                    added[child] = pb[i]
                elif i >= len(pb):
                    removed[child] = pa[i]
                else:
                    walk(pa[i], pb[i], child)
        else:
            if pa != pb:
                changed[path] = {"old": pa, "new": pb}

    walk(obj_a, obj_b, "")
    return {"added": added, "removed": removed, "changed": changed}


__all__ = ["text_diff", "json_diff"]
