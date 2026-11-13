#!/usr/bin/env python3
"""Index literal localized strings used by client Lua, retaining original context.

Lexical references include comments and do not establish execution or server behavior.
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
LITERAL = re.compile(r"""["']([^"'\r\n]+)["']""")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime/quest-reconstruction/script-localization.json.gz",
    )
    args = parser.parse_args()
    languages = {}
    hashes = {}
    for lang in ("en", "es", "fr", "pt"):
        path = ROOT / f"client/contents/i18n/i18n_{lang}.jar"
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        with zipfile.ZipFile(path) as archive:
            lines = (
                archive.read(f"texts_{lang}.properties").decode("utf-8").splitlines()
            )
        languages[lang] = dict(
            line.split("=", 1)
            for line in lines
            if "=" in line and not line.startswith(("#", "!"))
        )
    keys = set().union(*(set(values) for values in languages.values()))
    path = ROOT / "client/contents/scripts/scripts.jar"
    hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    scripts, found = {}, set()
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith(".lua"):
                continue
            source = archive.read(name).decode("utf-8", errors="replace")
            references = [
                {"line": number, "key": match.group(1)}
                for number, line in enumerate(source.splitlines(), 1)
                for match in LITERAL.finditer(line)
                if match.group(1) in keys
            ]
            if references:
                scripts[name] = {"references": references, "source": source}
                found.update(ref["key"] for ref in references)
    output = {
        "schema_version": 1,
        "source_sha256": hashes,
        "scripts": scripts,
        "translations": {
            lang: {key: values[key] for key in sorted(found) if key in values}
            for lang, values in languages.items()
        },
        "note": "Exact quoted literal matches, including comments; dynamic keys and nonliteral references are not resolved. Presence does not establish execution.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf8") as stream:
        json.dump(output, stream, ensure_ascii=False, separators=(",", ":"))
    nonquest = {key for key in found if not key.startswith("quest.")}
    print(
        f'{len(scripts)} scripts, {sum(len(v["references"]) for v in scripts.values())} references, {len(found)} unique keys, {len(nonquest)} outside quest.*'
    )
    print(
        "Most common non-quest key prefixes:",
        collections.Counter(k.split(".")[0] for k in nonquest).most_common(10),
    )


if __name__ == "__main__":
    main()
