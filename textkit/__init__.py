"""textkit -- a permissively-licensed text & data utilities library.

Pure standard library plus PyYAML.  Every public function takes text in and
returns text (or a simple python structure) out, and raises
:class:`TextKitError` -- and only that -- on failure, so the CLI and the GUI
have a single exception to catch.  Import what you need::

    from textkit import convert, hash_text, jwt_decode
    print(convert('{"a": 1}', "json", "yaml"))

The tkinter GUI in :mod:`textkit.gui` builds on this module; importing it does
nothing until :func:`textkit.gui.main` is called.
"""

from __future__ import annotations

from .errors import TextKitError
from .convert import (
    convert,
    json_to_csv,
    csv_to_json,
    json_to_yaml,
    yaml_to_json,
    json_to_xml,
    xml_to_json,
    csv_to_yaml,
    yaml_to_csv,
    csv_to_xml,
    xml_to_csv,
    yaml_to_xml,
    xml_to_yaml,
)
from .validate import (
    validate,
    validate_json,
    validate_yaml,
    validate_xml,
    validate_csv,
    pretty,
    minify,
)
from .diff import text_diff, json_diff
from .regex_util import test_regex, replace, parse_flags
from .hashing import hash_text, hash_file, hash_bytes, checksum_dir
from .encoding import (
    encode,
    decode,
    base64_encode,
    base64_decode,
    base32_encode,
    base32_decode,
    hex_encode,
    hex_decode,
    url_encode,
    url_decode,
    eol_convert,
    detect_and_convert_encoding,
    jwt_decode,
)
from . import textops

__version__ = "1.0.5"

__all__ = [
    "TextKitError",
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
    "validate",
    "validate_json",
    "validate_yaml",
    "validate_xml",
    "validate_csv",
    "pretty",
    "minify",
    "text_diff",
    "json_diff",
    "test_regex",
    "replace",
    "parse_flags",
    "hash_text",
    "hash_file",
    "hash_bytes",
    "checksum_dir",
    "encode",
    "decode",
    "base64_encode",
    "base64_decode",
    "base32_encode",
    "base32_decode",
    "hex_encode",
    "hex_decode",
    "url_encode",
    "url_decode",
    "eol_convert",
    "detect_and_convert_encoding",
    "jwt_decode",
    "textops",
    "__version__",
]
