"""Tests for validate / pretty / minify."""

import json

import pytest

from textkit import (
    validate, validate_json, validate_yaml, validate_xml, validate_csv,
    pretty, minify,
)
from textkit.errors import TextKitError


def test_validate_json_good_and_bad():
    ok, err = validate_json('{"a": 1}')
    assert ok and err == ""
    ok, err = validate_json("{a: 1}")
    assert not ok and err


def test_validate_yaml():
    assert validate_yaml("a: 1\nb: 2")[0] is True
    assert validate_yaml("a: :\n  - [")[0] is False


def test_validate_xml():
    assert validate_xml("<root><a>1</a></root>")[0] is True
    assert validate_xml("<root><a>1</root>")[0] is False


def test_validate_csv():
    assert validate_csv("a,b\n1,2\n3,4")[0] is True
    ok, err = validate_csv("a,b\n1,2,3")
    assert not ok and "expected" in err


def test_pretty_json_indent():
    out = pretty('{"a":1,"b":2}', "json", indent=2)
    assert out == '{\n  "a": 1,\n  "b": 2\n}'


def test_minify_json():
    assert minify('{\n  "a": 1,\n  "b": 2\n}', "json") == '{"a":1,"b":2}'


def test_pretty_then_minify_roundtrip():
    src = '{"a":[1,2,3],"b":{"c":4}}'
    formatted = pretty(src, "json")
    assert json.loads(minify(formatted, "json")) == json.loads(src)


def test_pretty_xml_indents():
    out = pretty("<root><a>1</a><b>2</b></root>", "xml", indent=2)
    assert "<a>1</a>" in out and "\n" in out


def test_minify_xml_collapses():
    out = minify("<root>\n  <a>1</a>\n</root>", "xml")
    assert out == "<root><a>1</a></root>"


def test_pretty_invalid_raises():
    with pytest.raises(TextKitError):
        pretty("{bad", "json")
