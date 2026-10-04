#!/usr/bin/env python3
"""Extract a separate Spanish spell/class-name catalogue, offline."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    archive = ROOT / "client/contents/i18n/i18n_es.jar"
    spells_path = ROOT / "server/protocol/spells.json"
    spells_bytes = spells_path.read_bytes()
    spells = json.loads(spells_bytes)["spells"]
    with zipfile.ZipFile(archive) as jar:
        text = jar.read("texts_es.properties").decode("utf-8")
    translations = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            translations[key] = value
    names = [
        dict(
            id=row["id"],
            name=translations.get(f"content.3.{row['id']}"),
            breed=row["breed"],
        )
        for row in spells
    ]
    breeds = sorted({row["breed"] for row in spells})
    data = dict(
        locale="es",
        source="Installed client/contents/i18n/i18n_es.jar!/texts_es.properties",
        fields_evidence={
            "spell_name": "bPK.getName -> aTF.a(3, d()); content.3.<id>",
            "class_name": "Native translation keys breed.<id>",
        },
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        spells_catalog_sha256=hashlib.sha256(spells_bytes).hexdigest(),
        spells=names,
        classes=[
            dict(breed=breed, name=translations.get(f"breed.{breed}"))
            for breed in breeds
        ],
        missing_spell_ids=[row["id"] for row in names if row["name"] is None],
        missing_class_ids=[
            breed for breed in breeds if f"breed.{breed}" not in translations
        ],
    )
    (ROOT / "server/protocol/spell-names.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    )
    assert spells_path.read_bytes() == spells_bytes
    print(
        f"{len(names)-len(data['missing_spell_ids'])}/{len(names)} spells; "
        f"{len(breeds)-len(data['missing_class_ids'])}/{len(breeds)} classes; "
        f"missing spells={data['missing_spell_ids']}; classes={data['missing_class_ids']}"
    )


if __name__ == "__main__":
    main()
