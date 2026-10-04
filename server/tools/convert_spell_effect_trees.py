"""Convert ExportSpellEffectTrees TSV output to reproducible structural metadata."""
import base64
import json
import sys
from pathlib import Path


def read_effects(path):
    effects = {}
    for line in Path(path).read_text().splitlines():
        row = line.split("\t")
        metadata = {}
        if row[-1].startswith("metadata:"):
            metadata = json.loads(base64.b64decode(row.pop().removeprefix("metadata:")))
        values = []
        parameters_by_level = []
        for value in row[9:]:
            if ":" in value:
                probability, parameters = value.split(":", 1)
                evaluated = json.loads(parameters)
                parameters_by_level.append(evaluated)
                values.append(
                    [probability, json.dumps(evaluated[0] if evaluated else None)]
                )
            else:
                values.append(value.split(","))
        effects[row[0]] = dict(
            effect_class=int(row[1]),
            variant=int(row[2]),
            minimum_level=int(row[3]),
            maximum_level=int(row[4]),
            criteria=base64.b64decode(row[5]).decode(),
            parameters=json.loads(row[6]),
            children=json.loads(row[7]),
            parameter_count=int(row[8]),
            probabilities=[float(x[0]) for x in values],
            parameter0_by_level=[json.loads(x[1]) for x in values],
        )
        if parameters_by_level:
            effects[row[0]]["parameters_by_level"] = parameters_by_level
        effects[row[0]].update(metadata)
    return effects


def convert(prefix, output):
    effects = read_effects(str(prefix) + "-effects.tsv")
    spells = {}
    for line in Path(str(prefix) + "-spells.tsv").read_text().splitlines():
        row = line.split("\t")
        levels = []
        for value in row[4:]:
            bounds, refs = value.split(":")
            levels.append([*map(int, bounds.split(",")), json.loads(refs)])
        spells[row[0]] = dict(
            line_of_sight=row[1] == "true",
            linear=row[2] == "true",
            free_cell=row[3] == "true",
            levels=levels,
        )
    result = dict(
        source="ExportSpellEffectTrees.java offline native fG(level), fyP, aKX, aNw, eVn. Structural metadata only: criteria and extra effects require native evaluation.",
        spells=spells,
        effects=effects,
    )
    Path(output).write_text(json.dumps(result, separators=(",", ":")))
    return result


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
