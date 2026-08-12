"""Tests for hashing (known vectors)."""

import zlib

import pytest

from textkit import hashing as H
from textkit.errors import TextKitError

# Known digests of the string "abc".
KNOWN = {
    "md5": "900150983cd24fb0d6963f7d28e17f72",
    "sha1": "a9993e364706816aba3e25717850c26c9cd0d89d",
    "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    "sha512": ("ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a"
               "2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f"),
}


@pytest.mark.parametrize("algo,expected", KNOWN.items())
def test_hash_text_known_vectors(algo, expected):
    assert H.hash_text("abc", algo=algo) == expected


def test_crc32_known_vector():
    # zlib.crc32(b"abc") == 0x352441c2
    assert H.hash_text("abc", algo="crc32") == "352441c2"
    assert H.hash_text("abc", algo="crc32") == format(zlib.crc32(b"abc") & 0xFFFFFFFF, "08x")


def test_hash_file_matches_text(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("abc", encoding="utf-8")
    assert H.hash_file(str(p), "sha256") == KNOWN["sha256"]


def test_checksum_dir(tmp_path):
    (tmp_path / "a.txt").write_text("abc", encoding="utf-8")
    (tmp_path / "b.txt").write_text("abc", encoding="utf-8")
    result = H.checksum_dir(str(tmp_path), "sha256")
    assert result == {"a.txt": KNOWN["sha256"], "b.txt": KNOWN["sha256"]}


def test_unknown_algo_raises():
    with pytest.raises(TextKitError):
        H.hash_text("abc", algo="sha3")


def test_missing_file_raises():
    with pytest.raises(TextKitError):
        H.hash_file("/no/such/file", "md5")
