"""Tests for encoding: base64/base32/hex/url, EOL, detection, JWT."""

import pytest

from textkit import encoding as E
from textkit.errors import TextKitError

SAMPLE = "Hello, world! café — 42"


@pytest.mark.parametrize("codec", ["base64", "base32", "hex", "url"])
def test_encode_decode_roundtrip(codec):
    assert E.decode(E.encode(SAMPLE, codec), codec) == SAMPLE


def test_base64_known_value():
    assert E.base64_encode("abc") == "YWJj"
    assert E.base64_decode("YWJj") == "abc"


def test_hex_known_value():
    assert E.hex_encode("abc") == "616263"
    assert E.hex_decode("616263") == "abc"


def test_url_encode_spaces_and_symbols():
    assert E.url_encode("a b&c") == "a%20b%26c"
    assert E.url_decode("a%20b%26c") == "a b&c"


def test_eol_convert():
    assert E.eol_convert("a\r\nb\rc\n", "lf") == "a\nb\nc\n"
    assert E.eol_convert("a\nb\n", "crlf") == "a\r\nb\r\n"


def test_detect_encoding_utf8_and_bom():
    text, enc = E.detect_and_convert_encoding("héllo".encode("utf-8"))
    assert text == "héllo" and enc == "utf-8"
    text, enc = E.detect_and_convert_encoding(b"\xef\xbb\xbfhi")
    assert text == "hi" and enc == "utf-8-sig"


def test_jwt_decode_known_token():
    token = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
             "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
             "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")
    out = E.jwt_decode(token)
    assert out["header"] == {"alg": "HS256", "typ": "JWT"}
    assert out["payload"]["sub"] == "1234567890"
    assert out["payload"]["name"] == "John Doe"
    assert out["payload"]["iat"] == 1516239022
    assert out["signature"] == "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"


def test_jwt_decode_bad_token_raises():
    with pytest.raises(TextKitError):
        E.jwt_decode("not-a-jwt")


def test_invalid_base64_raises():
    # "/w==" decodes to 0xFF, which is not valid UTF-8 text.
    with pytest.raises(TextKitError):
        E.base64_decode("/w==")
