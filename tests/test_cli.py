"""End-to-end tests for the argparse CLI and headless GUI guard."""

import json

from textkit.__main__ import main


def test_cli_convert_json_to_yaml(capsys):
    rc = main(["convert", "--from", "json", "--to", "yaml", "--text", '{"a": 1}'])
    out = capsys.readouterr().out
    assert rc == 0
    assert "a: 1" in out


def test_cli_validate_good(capsys):
    rc = main(["validate", "--kind", "json", "--text", '{"a": 1}'])
    assert rc == 0
    assert "valid json" in capsys.readouterr().out


def test_cli_validate_bad_nonzero(capsys):
    rc = main(["validate", "--kind", "json", "--text", "{bad"])
    assert rc == 1
    assert "invalid json" in capsys.readouterr().err


def test_cli_hash_text(capsys):
    rc = main(["hash", "--text", "abc", "--algo", "sha256"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


def test_cli_encode_decode_roundtrip(capsys):
    rc = main(["encode", "--format", "base64", "--text", "hi"])
    encoded = capsys.readouterr().out.strip()
    assert rc == 0 and encoded == "aGk="
    rc = main(["decode", "--format", "base64", "--text", encoded])
    assert capsys.readouterr().out.strip() == "hi"


def test_cli_jwt(capsys):
    token = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
             "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
             "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")
    rc = main(["jwt", token])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["payload"]["name"] == "John Doe"


def test_cli_text_snake(capsys):
    rc = main(["text", "snake", "--text", "HelloWorld"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "hello_world"


def test_cli_error_is_clean(capsys):
    rc = main(["hash", "--text", "x", "--algo", "sha256"])  # sanity ok path
    assert rc == 0
    capsys.readouterr()
    rc = main(["convert", "--from", "json", "--to", "yaml", "--text", "{bad"])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_gui_imports_without_side_effects():
    from textkit import gui  # noqa: F401
    assert hasattr(gui, "main")


def test_gui_main_headless_returns_zero():
    from textkit import gui
    assert gui.main() == 0
