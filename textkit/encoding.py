"""Encoding utilities: base64/base32/hex/URL, EOL conversion, JWT decode.

All text<->bytes conversions default to UTF-8.  Nothing here does any network
or cryptographic *verification*; :func:`jwt_decode` in particular only decodes.
"""

from __future__ import annotations

import base64
import binascii
import json
import urllib.parse

from .errors import TextKitError

CODECS = ("base64", "base32", "hex", "url")
EOLS = {"lf": "\n", "crlf": "\r\n", "cr": "\r"}


# --------------------------------------------------------------------------
# base64 / base32 / hex / url
# --------------------------------------------------------------------------
def base64_encode(text, urlsafe=False, encoding="utf-8"):
    raw = text.encode(encoding)
    out = base64.urlsafe_b64encode(raw) if urlsafe else base64.b64encode(raw)
    return out.decode("ascii")


def base64_decode(text, urlsafe=False, encoding="utf-8"):
    try:
        data = text.encode("ascii")
        # tolerate missing padding
        data += b"=" * (-len(data) % 4)
        raw = base64.urlsafe_b64decode(data) if urlsafe else base64.b64decode(data)
        return raw.decode(encoding)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise TextKitError(f"invalid base64: {exc}") from exc


def base32_encode(text, encoding="utf-8"):
    return base64.b32encode(text.encode(encoding)).decode("ascii")


def base32_decode(text, encoding="utf-8"):
    try:
        data = text.encode("ascii").upper()
        data += b"=" * (-len(data) % 8)
        return base64.b32decode(data).decode(encoding)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise TextKitError(f"invalid base32: {exc}") from exc


def hex_encode(text, encoding="utf-8"):
    return text.encode(encoding).hex()


def hex_decode(text, encoding="utf-8"):
    try:
        return bytes.fromhex(text.strip()).decode(encoding)
    except (ValueError, UnicodeDecodeError) as exc:
        raise TextKitError(f"invalid hex: {exc}") from exc


def url_encode(text, safe="", encoding="utf-8"):
    return urllib.parse.quote(text, safe=safe, encoding=encoding)


def url_decode(text, encoding="utf-8"):
    try:
        return urllib.parse.unquote(text, encoding=encoding, errors="strict")
    except Exception as exc:
        raise TextKitError(f"invalid URL encoding: {exc}") from exc


_ENCODERS = {
    "base64": base64_encode,
    "base32": base32_encode,
    "hex": hex_encode,
    "url": url_encode,
}
_DECODERS = {
    "base64": base64_decode,
    "base32": base32_decode,
    "hex": hex_decode,
    "url": url_decode,
}


def encode(text, codec):
    codec = (codec or "").lower()
    if codec not in _ENCODERS:
        raise TextKitError(f"unknown codec {codec!r}; choose from {list(CODECS)}")
    return _ENCODERS[codec](text)


def decode(text, codec):
    codec = (codec or "").lower()
    if codec not in _DECODERS:
        raise TextKitError(f"unknown codec {codec!r}; choose from {list(CODECS)}")
    return _DECODERS[codec](text)


# --------------------------------------------------------------------------
# EOL conversion
# --------------------------------------------------------------------------
def eol_convert(text, eol="lf"):
    """Normalise all line endings in *text* to ``lf`` / ``crlf`` / ``cr``."""
    eol = (eol or "").lower()
    if eol not in EOLS:
        raise TextKitError(f"unknown EOL {eol!r}; choose from {list(EOLS)}")
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalised.replace("\n", EOLS[eol])


# --------------------------------------------------------------------------
# Encoding detection / conversion (stdlib only, best-effort)
# --------------------------------------------------------------------------
_BOMS = [
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
]


def detect_and_convert_encoding(data, target="utf-8"):
    """Best-effort decode of raw *bytes* and re-encode to *target*.

    Returns ``(text, source_encoding)``.  Detection is BOM-first, then tries
    UTF-8, then falls back to Latin-1 (which always succeeds).  No third-party
    detector is used -- this is a pragmatic stdlib-only heuristic.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    source = None
    text = None
    for bom, enc in _BOMS:
        if data.startswith(bom):
            source = enc
            text = data.decode(enc)
            break
    if text is None:
        for enc in ("utf-8", "latin-1"):
            try:
                text = data.decode(enc)
                source = enc
                break
            except UnicodeDecodeError:
                continue
    if text is None:  # pragma: no cover - latin-1 never fails
        raise TextKitError("could not decode input with any known encoding")
    try:
        # round-trip through the target so callers get consistent bytes
        text.encode(target)
    except UnicodeEncodeError as exc:
        raise TextKitError(f"cannot represent text in {target!r}: {exc}") from exc
    return text, source


# --------------------------------------------------------------------------
# JWT decode (NO verification -- decode only)
# --------------------------------------------------------------------------
def _b64url_decode(segment):
    data = segment.encode("ascii")
    data += b"=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data)


def jwt_decode(token):
    """Decode a JWT into ``{"header", "payload", "signature"}``.

    WARNING: this performs **NO signature verification** and does not check
    ``exp``/``nbf``.  It only base64url-decodes the header and payload segments
    (parsing each as JSON) and returns the raw signature segment.  Never trust a
    token decoded this way for authentication.
    """
    if not isinstance(token, str):
        raise TextKitError("JWT must be a string")
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise TextKitError("not a JWT: expected 3 dot-separated segments")
    try:
        header = json.loads(_b64url_decode(parts[0]))
        payload = json.loads(_b64url_decode(parts[1]))
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise TextKitError(f"invalid JWT segment: {exc}") from exc
    return {"header": header, "payload": payload, "signature": parts[2]}


__all__ = [
    "CODECS",
    "EOLS",
    "base64_encode",
    "base64_decode",
    "base32_encode",
    "base32_decode",
    "hex_encode",
    "hex_decode",
    "url_encode",
    "url_decode",
    "encode",
    "decode",
    "eol_convert",
    "detect_and_convert_encoding",
    "jwt_decode",
]
