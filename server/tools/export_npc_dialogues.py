#!/usr/bin/env python3
"""Export installed native dialogues and scenario evidence without client changes."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_catalog(nodes, scripts_archive, languages):
    """Preserve choices and scripts; never infer server transitions from IDs."""
    translations = {}
    for language, archive in languages.items():
        with zipfile.ZipFile(archive) as source:
            lines = (
                source.read(f"texts_{language}.properties").decode("utf-8").splitlines()
            )
        translations[language] = dict(
            line.split("=", 1)
            for line in lines
            if "=" in line
            and line.startswith(
                ("content.75.", "content.76.", "content.159.", "content.7.")
            )
        )
    scripts = {}
    with zipfile.ZipFile(scripts_archive) as source:
        for name in sorted(source.namelist()):
            if name.endswith(".lua") and name.startswith(
                ("interactiveDialogs/", "scenario/")
            ):
                text = source.read(name).decode("utf-8")
                scripts[name] = {
                    "source": text,
                    "functions": re.findall(r"\bfunction\s+([\w.:]+)\s*\(", text),
                    "quest_calls": re.findall(
                        r"UI\.(?:activateFollowAchievement|followAchievement|openRewardsDialog)\s*\([^\n]*",
                        text,
                    ),
                    "dialogue_calls": re.findall(
                        r"(?:\w+\.)?(?:startInteractiveDialog|displayDialog|showDialog)\s*\([^\n]*",
                        text,
                    ),
                }
    return {
        "schema_version": 1,
        "nodes": nodes,
        "translations": translations,
        "scripts": scripts,
        "availability": {
            "dialogue_transitions": "Absent from aKO/aKP. Choice order/ID is not a target node.",
            "npc_placements": "Not established by dialogue nodes or dialogue audio scripts.",
            "quests": "Scenario client source preserved; server objectives/rewards not accredited.",
            "execution": "Lua is evidence only and must never be executed by the server.",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "server/protocol/npc-dialogues.json.gz"
    )
    args = parser.parse_args()
    java_source = ROOT / "sniffer/java/ExportNpcDialogues.java"
    classes = ROOT / ".runtime/local/classes"
    classes.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        native = Path(temporary) / "nodes.json"
        subprocess.run(
            [
                "javac",
                "-proc:none",
                "-cp",
                "client/lib/*",
                "-d",
                str(classes),
                str(java_source),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [
                "java",
                "-cp",
                f"{classes}:client/lib/*",
                "ExportNpcDialogues",
                str(native),
            ],
            cwd=ROOT,
            check=True,
        )
        native_data = json.loads(native.read_text())
        nodes = native_data["nodes"]
    scripts = ROOT / "client/contents/scripts/scripts.jar"
    languages = {
        language: ROOT / f"client/contents/i18n/i18n_{language}.jar"
        for language in ("en", "es", "fr", "pt")
    }
    catalog = extract_catalog(nodes, scripts, languages)
    catalog["speakers"] = native_data["speakers"]
    catalog["provenance"] = {
        "client_jar_sha256": sha256(ROOT / "client/lib/wakfu-client.jar"),
        "exporter_sha256": sha256(java_source),
        "scripts_sha256": sha256(scripts),
        "languages_sha256": {key: sha256(value) for key, value in languages.items()},
        "binary_archives_sha256": {
            path.name: sha256(path)
            for path in sorted((ROOT / "client/contents/bdata").glob("*.jar"))
        },
    }
    payload = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress(payload, mtime=0))
    print(
        json.dumps(
            {
                "output": str(args.output),
                "nodes": len(nodes),
                "choices": sum(len(node["choices"]) for node in nodes),
                "scripts": len(catalog["scripts"]),
                "translations": {
                    key: len(value) for key, value in catalog["translations"].items()
                },
                "bytes": args.output.stat().st_size,
            }
        )
    )


if __name__ == "__main__":
    main()
