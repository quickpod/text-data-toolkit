"""Tests for regex_util."""

import re

import pytest

from textkit import regex_util as R
from textkit.errors import TextKitError


def test_test_regex_matches_and_spans():
    matches = R.test_regex(r"\d+", "a12b345")
    assert [m["match"] for m in matches] == ["12", "345"]
    assert matches[0]["span"] == [1, 3]


def test_test_regex_groups():
    matches = R.test_regex(r"(\w+)@(\w+)", "ada@lovelace")
    assert matches[0]["groups"] == ["ada", "lovelace"]


def test_test_regex_named_groups():
    matches = R.test_regex(r"(?P<user>\w+)@(?P<host>\w+)", "grace@hopper")
    assert matches[0]["groupdict"] == {"user": "grace", "host": "hopper"}


def test_flags_ignorecase():
    assert len(R.test_regex("abc", "ABC", flags="i")) == 1
    assert len(R.test_regex("abc", "ABC")) == 0


def test_replace():
    assert R.replace(r"\d+", "#", "a1b22c333") == "a#b#c#"


def test_replace_with_group_ref():
    assert R.replace(r"(\w+)@(\w+)", r"\2.\1", "ada@io") == "io.ada"


def test_invalid_regex_raises():
    with pytest.raises(TextKitError):
        R.test_regex("(", "text")


def test_parse_flags_int_passthrough():
    assert R.parse_flags(re.IGNORECASE) == re.IGNORECASE
