"""Tests for text transforms."""

import pytest

from textkit import textops as T
from textkit.errors import TextKitError


def test_case_transforms():
    assert T.to_upper("abc") == "ABC"
    assert T.to_lower("ABC") == "abc"
    assert T.to_title("hello world") == "Hello World"


def test_snake():
    assert T.to_snake("HelloWorld") == "hello_world"
    assert T.to_snake("helloWorld") == "hello_world"
    assert T.to_snake("Hello World-Example") == "hello_world_example"


def test_kebab():
    assert T.to_kebab("HelloWorld") == "hello-world"


def test_camel_and_pascal():
    assert T.to_camel("hello world example") == "helloWorldExample"
    assert T.to_pascal("hello world") == "HelloWorld"


def test_slugify():
    assert T.slugify("Hello, World!") == "hello-world"
    assert T.slugify("Café del Mar") == "cafe-del-mar"


def test_dedupe_preserves_order():
    assert T.dedupe_lines("b\na\nb\nc\na") == "b\na\nc"


def test_sort_lines():
    assert T.sort_lines("c\na\nb") == "a\nb\nc"
    assert T.sort_lines("a\nb\nc", reverse=True) == "c\nb\na"


def test_sort_numeric():
    assert T.sort_lines("item10\nitem2\nitem1", numeric=True) == "item1\nitem2\nitem10"


def test_collapse_and_trim():
    assert T.collapse_whitespace("a   b\t\nc") == "a b c"
    assert T.trim("  a  \n  b ") == "a\nb"


def test_reverse():
    assert T.reverse("abc") == "cba"
    assert T.reverse_lines("a\nb\nc") == "c\nb\na"


def test_count():
    stats = T.count("hello world\nsecond line")
    assert stats["words"] == 4
    assert stats["lines"] == 2
    assert stats["chars"] == len("hello world\nsecond line")


def test_wrap():
    out = T.wrap("a b c d e f", width=3)
    assert all(len(line) <= 3 for line in out.splitlines())


def test_apply_unknown_raises():
    with pytest.raises(TextKitError):
        T.apply("nonsense", "text")
