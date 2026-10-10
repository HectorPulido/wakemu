#!/usr/bin/env python3
"""Add Spanish names from the installed client to the catalog offline."""
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    archive = ROOT / "client/contents/i18n/i18n_es.jar"
    with zipfile.ZipFile(archive) as jar:
        text = jar.read("texts_es.properties").decode("utf-8")
    names = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.startswith("content.7."):
            names[int(key.removeprefix("content.7."))] = value
    path = ROOT / "server/protocol/monsters.json"
    data = json.loads(path.read_text())
    for monster in data["monsters"]:
        reference = monster["ref"]
        monster_name = names.get(reference)
        # Keep the human-readable name immediately after the reference.
        original = dict(monster)
        monster.clear()
        monster.update(ref=reference, name=monster_name)
        monster.update({k: v for k, v in original.items() if k not in ("ref", "name")})
    data["fields_evidence"][
        "name"
    ] = "blj.getName -> blj.DK -> aTF.a(7, ref); i18n_es.jar/texts_es.properties content.7.<ref>"
    data["name_locale"] = "es"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    missing = sum(m["name"] is None for m in data["monsters"])
    print(
        f"{len(data['monsters'])} monsters: {len(data['monsters'])-missing} Spanish names; {missing} untranslated (null)."
    )


if __name__ == "__main__":
    main()
