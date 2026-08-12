"""Convert between JSON, CSV, XML and YAML.

Everything pivots through plain Python objects (dicts / lists / scalars): each
source format is *loaded* into an object and each target format is *dumped* from
one.  Public helpers take a text string and return a text string.

Round-trip notes (what is and isn't lossless):
  * **JSON <-> YAML** -- fully lossless in both directions (YAML is a JSON
    superset; we emit block YAML with keys in insertion order).
  * **JSON <-> CSV** -- lossless only for a *list of flat objects with string
    values*.  CSV has no types, so numbers/booleans come back as strings; nested
    objects/lists are stored as embedded JSON text and are NOT re-expanded on the
    way back.  A single object is written as a one-row CSV.
  * **JSON <-> XML** -- lossless for dicts/lists of string scalars.  The root
    element tag is synthesised on export and dropped on import, so it does not
    round-trip.  A *single-item* list becomes a lone element and reads back as a
    scalar (XML cannot tell "one" from "not-a-list").  All text values come back
    as strings.
"""

from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET

try:
    import yaml
except Exception as _exc:  # pragma: no cover - PyYAML is a declared dependency
    yaml = None
    _YAML_IMPORT_ERROR = _exc

from .errors import TextKitError

FORMATS = ("json", "yaml", "csv", "xml")
DEFAULT_ROOT = "root"
LIST_ITEM_TAG = "item"


# --------------------------------------------------------------------------
# Loaders: text -> python object
# --------------------------------------------------------------------------
def _load_json(text):
    try:
        return json.loads(text)
    except Exception as exc:
        raise TextKitError(f"invalid JSON: {exc}") from exc


def _load_yaml(text):
    if yaml is None:  # pragma: no cover
        raise TextKitError(f"PyYAML is required for YAML support: {_YAML_IMPORT_ERROR}")
    try:
        return yaml.safe_load(text)
    except Exception as exc:
        raise TextKitError(f"invalid YAML: {exc}") from exc


def _load_csv(text):
    """Parse CSV text into a list of row dicts (header row required)."""
    try:
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]
    except Exception as exc:
        raise TextKitError(f"invalid CSV: {exc}") from exc


def _elem_to_obj(elem):
    """Convert an ElementTree element into a python object."""
    children = list(elem)
    if not children:
        return elem.text if elem.text is not None else ""
    result = {}
    for child in children:
        value = _elem_to_obj(child)
        tag = child.tag
        if tag in result:
            if not isinstance(result[tag], list):
                result[tag] = [result[tag]]
            result[tag].append(value)
        else:
            result[tag] = value
    return result


def _load_xml(text):
    try:
        root = ET.fromstring(text)
    except Exception as exc:
        raise TextKitError(f"invalid XML: {exc}") from exc
    return _elem_to_obj(root)


# --------------------------------------------------------------------------
# Dumpers: python object -> text
# --------------------------------------------------------------------------
def _dump_json(obj, indent=2):
    try:
        return json.dumps(obj, indent=indent, ensure_ascii=False)
    except Exception as exc:
        raise TextKitError(f"could not serialise to JSON: {exc}") from exc


def _dump_yaml(obj):
    if yaml is None:  # pragma: no cover
        raise TextKitError(f"PyYAML is required for YAML support: {_YAML_IMPORT_ERROR}")
    try:
        return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True,
                              default_flow_style=False)
    except Exception as exc:
        raise TextKitError(f"could not serialise to YAML: {exc}") from exc


def _cell(value):
    """Render one scalar (or nested structure) for a CSV cell."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _dump_csv(obj):
    """Serialise a list of objects (or a single object) to CSV text.

    A dict wrapping a single list of records (e.g. ``{"item": [...]}`` produced
    by XML import) is unwrapped so the records become the CSV rows.
    """
    if isinstance(obj, dict) and len(obj) == 1:
        only = next(iter(obj.values()))
        if isinstance(only, list):
            obj = only
    if isinstance(obj, dict):
        rows = [obj]
    elif isinstance(obj, list):
        rows = obj
    else:
        raise TextKitError("CSV export needs a list of records or a single object.")
    fieldnames = []
    for row in rows:
        if not isinstance(row, dict):
            raise TextKitError("each CSV record must be an object with named fields.")
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n",
                            extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _cell(row.get(k, "")) for k in fieldnames})
    return buf.getvalue()


def _scalar_text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _build_elem(tag, value):
    elem = ET.Element(tag)
    if isinstance(value, dict):
        for key, val in value.items():
            if isinstance(val, list):
                for item in val:
                    elem.append(_build_elem(key, item))
            else:
                elem.append(_build_elem(key, val))
    elif isinstance(value, list):
        for item in value:
            elem.append(_build_elem(LIST_ITEM_TAG, item))
    else:
        elem.text = _scalar_text(value)
    return elem


def _dump_xml(obj, root=DEFAULT_ROOT, indent=2):
    try:
        elem = _build_elem(root, obj)
        try:
            ET.indent(elem, space=" " * indent)  # Python 3.9+
        except Exception:
            pass
        return ET.tostring(elem, encoding="unicode")
    except TextKitError:
        raise
    except Exception as exc:
        raise TextKitError(f"could not serialise to XML: {exc}") from exc


_LOADERS = {"json": _load_json, "yaml": _load_yaml, "csv": _load_csv, "xml": _load_xml}
_DUMPERS = {"json": _dump_json, "yaml": _dump_yaml, "csv": _dump_csv, "xml": _dump_xml}


def convert(text, from_fmt, to_fmt, root=DEFAULT_ROOT):
    """Convert *text* from ``from_fmt`` to ``to_fmt`` (both in :data:`FORMATS`)."""
    from_fmt = (from_fmt or "").lower()
    to_fmt = (to_fmt or "").lower()
    if from_fmt not in _LOADERS:
        raise TextKitError(f"unknown source format {from_fmt!r}; choose from {list(FORMATS)}")
    if to_fmt not in _DUMPERS:
        raise TextKitError(f"unknown target format {to_fmt!r}; choose from {list(FORMATS)}")
    obj = _LOADERS[from_fmt](text)
    if to_fmt == "xml":
        return _dump_xml(obj, root=root)
    return _DUMPERS[to_fmt](obj)


# --------------------------------------------------------------------------
# Named pairwise convenience wrappers
# --------------------------------------------------------------------------
def json_to_csv(text):
    """JSON (list of flat objects) -> CSV.  See module docstring for caveats."""
    return convert(text, "json", "csv")


def csv_to_json(text):
    """CSV -> JSON (list of objects with string values)."""
    return convert(text, "csv", "json")


def json_to_yaml(text):
    """JSON -> YAML (lossless)."""
    return convert(text, "json", "yaml")


def yaml_to_json(text):
    """YAML -> JSON (lossless)."""
    return convert(text, "yaml", "json")


def json_to_xml(text, root=DEFAULT_ROOT):
    """JSON -> XML.  Root tag is synthesised; see caveats."""
    return convert(text, "json", "xml", root=root)


def xml_to_json(text):
    """XML -> JSON (values come back as strings; root tag dropped)."""
    return convert(text, "xml", "json")


def csv_to_yaml(text):
    """CSV -> YAML (list of objects)."""
    return convert(text, "csv", "yaml")


def yaml_to_csv(text):
    """YAML (list of flat objects) -> CSV."""
    return convert(text, "yaml", "csv")


def csv_to_xml(text, root=DEFAULT_ROOT):
    """CSV -> XML (each row an ``<item>`` element under the root)."""
    return convert(text, "csv", "xml", root=root)


def xml_to_csv(text):
    """XML (repeated child elements) -> CSV."""
    return convert(text, "xml", "csv")


def yaml_to_xml(text, root=DEFAULT_ROOT):
    """YAML -> XML."""
    return convert(text, "yaml", "xml", root=root)


def xml_to_yaml(text):
    """XML -> YAML."""
    return convert(text, "xml", "yaml")


__all__ = [
    "FORMATS",
    "convert",
    "json_to_csv",
    "csv_to_json",
    "json_to_yaml",
    "yaml_to_json",
    "json_to_xml",
    "xml_to_json",
    "csv_to_yaml",
    "yaml_to_csv",
    "csv_to_xml",
    "xml_to_csv",
    "yaml_to_xml",
    "xml_to_yaml",
]
