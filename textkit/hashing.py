"""Hashing and checksums: MD5, SHA-1/256/512 and CRC32."""

from __future__ import annotations

import hashlib
import os
import zlib

from .errors import TextKitError

ALGOS = ("md5", "sha1", "sha256", "sha512", "crc32")
_CHUNK = 1 << 20  # 1 MiB


def _normalise(algo):
    algo = (algo or "").lower().replace("-", "")
    if algo not in ALGOS:
        raise TextKitError(f"unknown algorithm {algo!r}; choose from {list(ALGOS)}")
    return algo


def hash_bytes(data, algo="sha256"):
    """Hex digest of raw *bytes* using *algo*."""
    algo = _normalise(algo)
    if algo == "crc32":
        return format(zlib.crc32(data) & 0xFFFFFFFF, "08x")
    h = hashlib.new(algo)
    h.update(data)
    return h.hexdigest()


def hash_text(text, algo="sha256", encoding="utf-8"):
    """Hex digest of *text* (encoded with *encoding*) using *algo*."""
    return hash_bytes(text.encode(encoding), algo)


def hash_file(path, algo="sha256"):
    """Hex digest of the file at *path*, read in chunks."""
    algo = _normalise(algo)
    if not os.path.isfile(path):
        raise TextKitError(f"file not found: {path}")
    try:
        if algo == "crc32":
            crc = 0
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(_CHUNK), b""):
                    crc = zlib.crc32(chunk, crc)
            return format(crc & 0xFFFFFFFF, "08x")
        h = hashlib.new(algo)
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(_CHUNK), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError as exc:
        raise TextKitError(f"could not read {path!r}: {exc}") from exc


def checksum_dir(path, algo="sha256"):
    """Return ``{relative_path: digest}`` for every file under *path*."""
    algo = _normalise(algo)
    if not os.path.isdir(path):
        raise TextKitError(f"not a directory: {path}")
    result = {}
    for root, _dirs, files in os.walk(path):
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, path).replace(os.sep, "/")
            result[rel] = hash_file(full, algo)
    return result


__all__ = ["ALGOS", "hash_bytes", "hash_text", "hash_file", "checksum_dir"]
