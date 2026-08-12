"""Tests for text and JSON diffs."""

from textkit import diff as D


def test_text_diff_identical_empty():
    assert D.text_diff("same\ntext\n", "same\ntext\n") == ""


def test_text_diff_shows_changes():
    out = D.text_diff("a\nb\nc\n", "a\nB\nc\n")
    assert "-b" in out and "+B" in out


def test_json_diff_added_removed_changed():
    a = {"keep": 1, "drop": 2, "change": 3}
    b = {"keep": 1, "change": 4, "add": 5}
    d = D.json_diff(a, b)
    assert d["removed"] == {"/drop": 2}
    assert d["added"] == {"/add": 5}
    assert d["changed"] == {"/change": {"old": 3, "new": 4}}


def test_json_diff_nested_paths():
    a = {"user": {"name": "ada", "age": 36}}
    b = {"user": {"name": "ada", "age": 37}}
    d = D.json_diff(a, b)
    assert d["changed"] == {"/user/age": {"old": 36, "new": 37}}


def test_json_diff_lists_by_index():
    d = D.json_diff({"xs": [1, 2, 3]}, {"xs": [1, 9, 3, 4]})
    assert d["changed"] == {"/xs/1": {"old": 2, "new": 9}}
    assert d["added"] == {"/xs/3": 4}


def test_json_diff_accepts_strings():
    d = D.json_diff('{"a": 1}', '{"a": 2}')
    assert d["changed"] == {"/a": {"old": 1, "new": 2}}
