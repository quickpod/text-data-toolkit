# Text & Data Toolkit

A fast, **offline**, **100% open-source** text & data utility toolkit for Windows. Nothing is uploaded anywhere. Built entirely by AI with human testing and guidance, and published on [QuickOpen](https://quickopen.ai/projects/text-data-toolkit).

> **100% AI-built and open source.** Apache-2.0.

## What it does

Convert between JSON, CSV, XML and YAML; validate and pretty-print/minify; structural diff and merge; a live regex tester; hashing/checksums (MD5/SHA family/CRC32); base64/hex/URL encode-decode; JWT decode/inspect; and text transforms (case, encoding/EOL fixers, sort/dedupe lines, whitespace). Everything runs locally; nothing is uploaded.

## Install

Download **`TextDataToolkit-Setup.exe`** from the [QuickOpen page](https://quickopen.ai/projects/text-data-toolkit) or the [GitHub release](https://github.com/quickpod/text-data-toolkit/releases/latest) and double-click it. It installs per-user, adds Desktop and Start Menu shortcuts, and can optionally trust the QuickOpen Root CA. Authenticode-signed by the QuickOpen Code Signing CA — verify at [quickopen.ai/trust](https://quickopen.ai/trust).

## Run from source

```sh
pip install -r requirements.txt
python text_data_app.py          # GUI
python -m textkit --help    # CLI
```


## Features

- **Convert** between JSON, YAML, CSV and XML (all sensible pairings). JSON↔YAML is lossless; CSV and XML conversions are type-flattening — see the notes in `textkit/convert.py`.
- **Validate & format** — check JSON / YAML / XML / CSV, and pretty-print or minify any of them.
- **Diff** — a unified line diff of two texts, or a structural JSON diff that reports added / removed / changed paths.
- **Regex tester** — test a pattern with match spans, numbered and named groups (live highlighting in the GUI), plus find-and-replace.
- **Hash & checksum** — MD5, SHA-1, SHA-256, SHA-512 and CRC32 of text, a file, or every file in a directory. File hashing runs off the UI thread in the GUI.
- **Encode / decode** — base64, base32, hex and URL; EOL conversion (LF/CRLF/CR); best-effort encoding detection.
- **JWT decoder** — decode a token's header and payload (base64url + JSON). Decode only — **no signature verification**.
- **Text transforms** — case (upper/lower/title/snake/kebab/camel/pascal), trim/collapse whitespace, sort/dedupe/reverse lines, count, slugify and wrap.
- **Offline & pure-stdlib** — standard library plus PyYAML; a tkinter GUI with light/dark themes. Nothing is uploaded.

## CLI examples

```sh
# Convert (infer formats from --from/--to, or from file extensions)
echo '{"name":"Ada","langs":["py","c"]}' | python -m textkit convert --from json --to yaml
python -m textkit convert data.csv -o data.json          # inferred by extension

# Validate (non-zero exit on failure) and reformat
python -m textkit validate config.yaml --kind yaml
python -m textkit pretty --kind json data.json
python -m textkit minify --kind xml page.xml -o page.min.xml

# Diff: unified text diff, or structural JSON diff
python -m textkit diff old.txt new.txt
python -m textkit diff a.json b.json --json

# Regex: test matches, or substitute
echo 'ada@lovelace grace@hopper' | python -m textkit regex '(\w+)@(\w+)'
echo 'a1b22c333' | python -m textkit regex '\d+' --replace '#'

# Hash text, a file, or a whole directory
python -m textkit hash --text abc --algo sha256
python -m textkit hash ./archive.zip --algo sha512
python -m textkit hash --dir ./release --algo md5

# Encode / decode and JWT
python -m textkit encode --format base64 --text "hi there"
python -m textkit decode --format base64 --text aGkgdGhlcmU=
python -m textkit jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.sig

# Text transforms and counts
python -m textkit text snake --text "HelloWorldExample"
python -m textkit text sort --numeric input.txt
python -m textkit count README.md
```

Run `python -m textkit --help` (or `<command> --help`) for the full option list.

## License

Apache-2.0 — see [LICENSE](LICENSE). A 100% AI-built project published on QuickOpen.
