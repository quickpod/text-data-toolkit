"""Round-trip and conversion tests for textkit.convert."""

import json

import pytest

from textkit import (
    convert, json_to_csv, csv_to_json, json_to_yaml, yaml_to_json,
    json_to_xml, xml_to_json, csv_to_yaml, yaml_to_csv, csv_to_xml, xml_to_csv,
)
from textkit.errors import TextKitError


def _norm_json(text):
    return json.loads(text)


def test_json_yaml_roundtrip_lossless():
    obj = {"name": "Ada", "age": 36, "langs": ["python", "c"], "active": True,
           "nested": {"x": 1, "y": [2, 3]}}
    src = json.dumps(obj)
    yaml_text = json_to_yaml(src)
    back = yaml_to_json(yaml_text)
    assert _norm_json(back) == obj


def test_yaml_to_json_values_typed():
    yaml_text = "a: 1\nb: two\nc:\n  - x\n  - y\n"
    out = _norm_json(yaml_to_json(yaml_text))
    assert out == {"a": 1, "b": "two", "c": ["x", "y"]}


def test_json_csv_roundtrip_string_values():
    rows = [{"name": "Ada", "city": "London"},
            {"name": "Grace", "city": "New York"}]
    src = json.dumps(rows)
    csv_text = json_to_csv(src)
    assert csv_text.splitlines()[0] == "name,city"
    back = _norm_json(csv_to_json(csv_text))
    assert back == rows


def test_json_to_csv_single_object_is_one_row():
    csv_text = json_to_csv('{"a": "1", "b": "2"}')
    lines = csv_text.strip().splitlines()
    assert lines[0] == "a,b"
    assert lines[1] == "1,2"


def test_json_xml_roundtrip_string_scalars():
    obj = {"name": "Ada", "city": "London"}
    xml_text = json_to_xml(json.dumps(obj))
    assert "<name>Ada</name>" in xml_text
    back = _norm_json(xml_to_json(xml_text))
    assert back == obj


def test_json_xml_list_roundtrip():
    obj = {"item": ["a", "b", "c"]}
    xml_text = json_to_xml(json.dumps(obj))
    back = _norm_json(xml_to_json(xml_text))
    assert back == obj


def test_csv_yaml_roundtrip():
    rows = [{"k": "1", "v": "one"}, {"k": "2", "v": "two"}]
    csv_text = json_to_csv(json.dumps(rows))
    yaml_text = csv_to_yaml(csv_text)
    back_csv = yaml_to_csv(yaml_text)
    assert _norm_json(csv_to_json(back_csv)) == rows


def test_csv_to_xml_and_back():
    rows = [{"name": "Ada", "city": "London"}, {"name": "Grace", "city": "NY"}]
    csv_text = json_to_csv(json.dumps(rows))
    xml_text = csv_to_xml(csv_text)
    assert xml_text.count("<item>") == 2
    back_csv = xml_to_csv(xml_text)  # returns CSV text
    assert _norm_json(csv_to_json(back_csv)) == rows


def test_invalid_json_raises():
    with pytest.raises(TextKitError):
        json_to_yaml("{not valid")


def test_unknown_format_raises():
    with pytest.raises(TextKitError):
        convert("{}", "json", "toml")
