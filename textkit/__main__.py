"""Command-line interface: ``python -m textkit <command> ...``.

Most commands read text from a positional file, from ``--text``, or from stdin,
and write to stdout (or ``-o FILE``).  Any :class:`TextKitError` is printed as a
clean ``error: ...`` line with a non-zero exit -- never a traceback.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .errors import TextKitError
# NOTE: import the submodules explicitly -- ``from . import convert`` would
# resolve to the re-exported *function* of the same name, not the module.
from .convert import convert as convert_text, FORMATS, DEFAULT_ROOT
from .validate import validate as validate_text, pretty as pretty_text, \
    minify as minify_text, KINDS
from .diff import text_diff, json_diff
from . import regex_util
from . import hashing
from . import encoding
from . import textops

_EXT_TO_FMT = {
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".csv": "csv",
}


# --------------------------------------------------------------------------
# input / output helpers
# --------------------------------------------------------------------------
def _read_input(a):
    """Return input text from ``--text``, a positional ``input`` file, or stdin."""
    if getattr(a, "text", None) is not None:
        return a.text
    path = getattr(a, "input", None)
    if path:
        if not os.path.isfile(path):
            raise TextKitError(f"file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError as exc:
            raise TextKitError(f"could not read {path!r}: {exc}") from exc
    if sys.stdin is not None and not sys.stdin.isatty():
        return sys.stdin.read()
    raise TextKitError("no input: pass a file, --text, or pipe data on stdin")


def _write_output(a, text):
    out = getattr(a, "output", None)
    if out:
        try:
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(text if text.endswith("\n") else text + "\n")
        except OSError as exc:
            raise TextKitError(f"could not write {out!r}: {exc}") from exc
        print(f"wrote {out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")


def _infer_fmt(path, label):
    if not path:
        raise TextKitError(f"could not infer {label} format; pass it explicitly")
    ext = os.path.splitext(path)[1].lower()
    fmt = _EXT_TO_FMT.get(ext)
    if not fmt:
        raise TextKitError(f"cannot infer {label} format from {path!r}; pass it explicitly")
    return fmt


# --------------------------------------------------------------------------
# command handlers
# --------------------------------------------------------------------------
def cmd_convert(a):
    src = a.from_fmt or _infer_fmt(getattr(a, "input", None), "source")
    dst = a.to_fmt or _infer_fmt(a.output, "target")
    _write_output(a, convert_text(_read_input(a), src, dst, root=a.root))


def cmd_validate(a):
    kind = a.kind or _infer_fmt(getattr(a, "input", None), "input")
    ok, err = validate_text(_read_input(a), kind)
    if ok:
        print(f"valid {kind}")
        return
    print(f"invalid {kind}: {err}", file=sys.stderr)
    raise TextKitError(f"invalid {kind}")


def cmd_pretty(a):
    kind = a.kind or _infer_fmt(getattr(a, "input", None), "input")
    _write_output(a, pretty_text(_read_input(a), kind, indent=a.indent))


def cmd_minify(a):
    kind = a.kind or _infer_fmt(getattr(a, "input", None), "input")
    _write_output(a, minify_text(_read_input(a), kind))


def cmd_diff(a):
    try:
        with open(a.a, "r", encoding="utf-8") as fh:
            text_a = fh.read()
        with open(a.b, "r", encoding="utf-8") as fh:
            text_b = fh.read()
    except OSError as exc:
        raise TextKitError(f"could not read input: {exc}") from exc
    if a.json:
        result = json_diff(text_a, text_b)
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    else:
        out = text_diff(text_a, text_b, a_label=a.a, b_label=a.b)
        sys.stdout.write(out if out else "(no differences)\n")


def cmd_regex(a):
    text = _read_input(a)
    if a.replace is not None:
        _write_output(a, regex_util.replace(a.pattern, a.replace, text, flags=a.flags))
        return
    matches = regex_util.test_regex(a.pattern, text, flags=a.flags)
    if a.json:
        sys.stdout.write(json.dumps(matches, indent=2, ensure_ascii=False) + "\n")
        return
    if not matches:
        print("no matches")
        return
    print(f"{len(matches)} match(es):")
    for m in matches:
        print(f"  [{m['start']}:{m['end']}] {m['match']!r}")
        if m["groups"]:
            print(f"      groups: {m['groups']}")
        if m["groupdict"]:
            print(f"      named:  {m['groupdict']}")


def cmd_hash(a):
    if a.dir:
        result = hashing.checksum_dir(a.dir, algo=a.algo)
        for rel, digest in result.items():
            print(f"{digest}  {rel}")
        return
    if getattr(a, "text", None) is not None:
        print(hashing.hash_text(a.text, algo=a.algo))
        return
    if a.input:
        print(f"{hashing.hash_file(a.input, algo=a.algo)}  {a.input}")
        return
    # stdin
    print(hashing.hash_text(_read_input(a), algo=a.algo))


def cmd_encode(a):
    _write_output(a, encoding.encode(_read_input(a), a.format))


def cmd_decode(a):
    _write_output(a, encoding.decode(_read_input(a), a.format))


def cmd_jwt(a):
    if a.token is not None:
        token = a.token
    elif sys.stdin is not None and not sys.stdin.isatty():
        token = sys.stdin.read().strip()
    else:
        raise TextKitError("no token: pass a JWT string or pipe it on stdin")
    result = encoding.jwt_decode(token)
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


def cmd_text(a):
    text = _read_input(a)
    if a.op == "sort":
        out = textops.sort_lines(text, reverse=a.reverse,
                                 case_insensitive=a.ignore_case, numeric=a.numeric)
    elif a.op == "dedupe":
        out = textops.dedupe_lines(text)
    elif a.op == "wrap":
        out = textops.wrap(text, width=a.width)
    elif a.op == "slugify":
        out = textops.slugify(text)
    else:
        out = textops.apply(a.op, text)
    _write_output(a, out)


def cmd_count(a):
    stats = textops.count(_read_input(a))
    for key in ("lines", "words", "chars", "chars_no_spaces", "bytes"):
        print(f"{key:<16} {stats[key]}")


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------
def _add_io(sp, with_input=True, with_output=True):
    if with_input:
        sp.add_argument("input", nargs="?", help="input file (default: stdin)")
        sp.add_argument("--text", help="inline input text instead of a file")
    if with_output:
        sp.add_argument("-o", "--output", help="output file (default: stdout)")


def build_parser():
    p = argparse.ArgumentParser(
        prog="textkit",
        description="Text & data utilities: convert / validate / format / diff / "
                    "regex / hash / encode / jwt / text transforms. Offline, "
                    "stdlib + PyYAML only.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add(name, help, handler):
        sp = sub.add_parser(name, help=help)
        sp.set_defaults(func=handler)
        return sp

    s = add("convert", "Convert between JSON/YAML/CSV/XML", cmd_convert)
    _add_io(s)
    s.add_argument("--from", dest="from_fmt", choices=list(FORMATS),
                   help="source format (default: infer from input extension)")
    s.add_argument("--to", dest="to_fmt", choices=list(FORMATS),
                   help="target format (default: infer from output extension)")
    s.add_argument("--root", default=DEFAULT_ROOT,
                   help="root element tag for XML output")

    s = add("validate", "Check JSON/YAML/XML/CSV validity", cmd_validate)
    _add_io(s, with_output=False)
    s.add_argument("--kind", choices=list(KINDS),
                   help="format (default: infer from extension)")

    s = add("pretty", "Pretty-print / indent", cmd_pretty)
    _add_io(s)
    s.add_argument("--kind", choices=list(KINDS))
    s.add_argument("--indent", type=int, default=2)

    s = add("minify", "Compact / minify", cmd_minify)
    _add_io(s)
    s.add_argument("--kind", choices=list(KINDS))

    s = add("diff", "Diff two files (text or --json structural)", cmd_diff)
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--json", action="store_true", help="structural JSON diff")

    s = add("regex", "Test a regex or --replace", cmd_regex)
    s.add_argument("pattern")
    _add_io(s)
    s.add_argument("--flags", default="", help="regex flags, e.g. 'ims'")
    s.add_argument("--replace", help="replacement string (substitution mode)")
    s.add_argument("--json", action="store_true", help="print matches as JSON")

    s = add("hash", "Hash text / file / directory", cmd_hash)
    s.add_argument("input", nargs="?", help="file to hash (default: stdin)")
    s.add_argument("--text", help="hash this literal text")
    s.add_argument("--dir", help="checksum every file under this directory")
    s.add_argument("--algo", default="sha256", choices=list(hashing.ALGOS))

    s = add("encode", "Encode base64/base32/hex/url", cmd_encode)
    _add_io(s)
    s.add_argument("--format", required=True, choices=list(encoding.CODECS))

    s = add("decode", "Decode base64/base32/hex/url", cmd_decode)
    _add_io(s)
    s.add_argument("--format", required=True, choices=list(encoding.CODECS))

    s = add("jwt", "Decode a JWT (NO verification)", cmd_jwt)
    s.add_argument("token", nargs="?", help="JWT string (default: stdin)")

    s = add("text", "Text transforms (case, lines, slug, wrap...)", cmd_text)
    s.add_argument("op", choices=sorted(textops.TRANSFORMS),
                   help="transform to apply")
    _add_io(s)
    s.add_argument("--reverse", action="store_true", help="sort: descending")
    s.add_argument("--ignore-case", action="store_true", help="sort: case-insensitive")
    s.add_argument("--numeric", action="store_true", help="sort: by leading number")
    s.add_argument("--width", type=int, default=80, help="wrap: column width")

    s = add("count", "Count chars / words / lines", cmd_count)
    _add_io(s, with_output=False)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except TextKitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:  # e.g. piping into head
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
