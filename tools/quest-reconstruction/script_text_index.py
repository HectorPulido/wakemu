#!/usr/bin/env python3
"""Extract client Lua scripts referencing quest text, and localized quest keys.

Literal references are evidence, including comments and unused code; they do not
establish that a script runs or that a server transition exists.
"""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PATTERN = re.compile(r"""["'](quest\.[A-Za-z0-9_.-]+)["']""")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime/quest-reconstruction/script-texts.json.gz",
    )
    args = parser.parse_args()
    archive = ROOT / "client/contents/scripts/scripts.jar"
    scripts = {}
    keys = set()
    with zipfile.ZipFile(archive) as z:
        for name in sorted(z.namelist()):
            if not name.endswith(".lua"):
                continue
            source = z.read(name).decode("utf-8", errors="replace")
            matches = [
                (n, m.group(1))
                for n, line in enumerate(source.splitlines(), 1)
                for m in PATTERN.finditer(line)
            ]
            if matches:
                scripts[name] = {
                    "source": source,
                    "references": [{"line": n, "key": key} for n, key in matches],
                }
                keys.update(key for _, key in matches)
    translations = {}
    hashes = {"scripts_sha256": digest(archive)}
    for lang in ("es", "en", "fr", "pt"):
        path = ROOT / f"client/contents/i18n/i18n_{lang}.jar"
        hashes[lang + "_sha256"] = digest(path)
        with zipfile.ZipFile(path) as z:
            lines = z.read(f"texts_{lang}.properties").decode("utf-8").splitlines()
        translations[lang] = dict(
            line.split("=", 1)
            for line in lines
            if line.startswith("quest.") and "=" in line
        )
    result = {
        "schema_version": 1,
        "provenance": hashes,
        "scripts": scripts,
        "translations": translations,
        "unresolved_literal_keys": {
            lang: sorted(keys - data.keys()) for lang, data in translations.items()
        },
        "note": "Literal matches include comments and cannot prove execution, NPC identity, or server transitions.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    print(
        f'{len(scripts)} scripts, {sum(len(s["references"]) for s in scripts.values())} references, {len(keys)} distinct keys; translations: '
        + str({k: len(v) for k, v in translations.items()})
    )
    print(
        "Unresolved keys: "
        + str({k: len(v) for k, v in result["unresolved_literal_keys"].items()})
    )


if __name__ == "__main__":
    main()
