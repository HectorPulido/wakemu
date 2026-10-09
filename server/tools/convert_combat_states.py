"""Convert offline native state definitions; does not claim runtime support."""
import base64
import json
import sys
import zipfile
from pathlib import Path

from convert_spell_effect_trees import read_effects


def convert(prefix, output):
    client = Path(__file__).resolve().parents[2] / "client/contents/i18n/i18n_es.jar"
    with zipfile.ZipFile(client) as archive:
        text = archive.read("texts_es.properties").decode("utf-8")
    translations = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.startswith(("content.8.", "content.9.")):
            translations[key] = value
    states = {}
    for line in Path(str(prefix) + "-states.tsv").read_text().splitlines():
        row = line.split("\t")
        metadata = {}
        if row[-1].startswith("metadata:"):
            metadata = json.loads(base64.b64decode(row.pop().removeprefix("metadata:")))
        if row[0] in states:
            raise ValueError(f"Duplicate native state {row[0]}")
        levels = []
        for value in row[4:]:
            duration, effects = value.split(":", 1)
            levels.append(dict(duration=int(duration), effects=json.loads(effects)))
        if len(levels) != 200:
            raise ValueError(f"Incomplete native state levels: {row[0]}")
        states[row[0]] = dict(
            name=translations.get(f"content.8.{row[0]}"),
            description=translations.get(f"content.9.{row[0]}"),
            maximum_level=int(row[1]),
            tick_at_turn_end=row[2] == "true",
            effect_ids=json.loads(row[3]),
            levels=levels,
        )
        states[row[0]].update(metadata)
    result = dict(
        source="ExportCombatStates.java: offline aNv, bbV/fyZ/fyW, native durations and level-filtered effects. Runtime conditions and triggers require interpretation.",
        states=states,
        effects=read_effects(str(prefix) + "-effects.tsv"),
        name_locale="es",
    )
    encoded = json.dumps(result, separators=(",", ":")).encode()
    Path(output).write_bytes(encoded)
    return result


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
