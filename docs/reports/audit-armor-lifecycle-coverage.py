import json, gzip, collections
from pathlib import Path

p = Path("server/protocol")


def load(name):
    with (
        gzip.open(p / name, "rt") if name.endswith(".gz") else (p / name).open()
    ) as stream:
        return json.load(stream)


tree = load("spell-effect-trees.json")
state = load("combat-state-definitions.json.gz")
grant = load("granted-spell-effect-trees.json.gz")
areas = load("native-effect-areas.json")["areas"]
base = load("spells.json")["spells"]
innates = load("breed-innate-definitions.json")["breeds"]
effects = {**tree["effects"], **state["effects"], **grant["effects"]}
spells = {**tree["spells"], **grant["spells"]}


def roots(obj):
    return sorted(
        {
            r
            for row in obj.get("levels", [])
            for r in (row[2] if isinstance(row, list) else row.get("effects", []))
        }
    ) or obj.get("effect_ids", [])


sources = [
    dict(
        kind=s["kind"],
        reference=s["id"],
        breed=s["breed"],
        roots=roots(spells.get(str(s["id"]), {})),
    )
    for s in base
]
sources += [
    dict(
        kind="innate",
        reference=s["reference"],
        breed=b["breed"],
        roots=roots(state["states"].get(str(s["reference"]), {})),
    )
    for b in innates
    for s in b.get("innate_states", [])
]
rows = []
missing = set()
for source in sources:
    queue = collections.deque(source["roots"])
    seen = set()
    armor = set()
    while queue:
        identity = queue.popleft()
        if identity in seen:
            continue
        seen.add(identity)
        definition = effects.get(str(identity))
        if definition is None:
            missing.add(identity)
            continue
        if definition["effect_class"] == 1013:
            armor.add(identity)
        queue.extend(definition.get("children", []))
        family = definition["effect_class"]
        params = definition.get("parameters", [])
        if family not in (304, 315, 649) or not params:
            continue
        index = 4 if family == 649 else 0
        if len(params) <= index:
            continue
        values = {int(params[index])}
        values.update(
            int(row[index // 2])
            for row in definition.get("parameters_by_level", [])
            if isinstance(row, list) and len(row) > index // 2
        )
        for reference in values:
            obj = (
                spells if family == 649 else areas if family == 315 else state["states"]
            ).get(str(reference), {})
            queue.extend(roots(obj))
    if armor:
        rows.append(
            {k: v for k, v in source.items() if k != "roots"}
            | dict(armor_effects=sorted(armor))
        )
report = dict(
    scope="Structural closure across native class spells and innates, state304/area315/grant649; no criterion evaluation or runtime support claim",
    counts=dict(
        sources_with_armor=len(rows),
        by_kind=dict(collections.Counter(r["kind"] for r in rows)),
        breeds=sorted({r["breed"] for r in rows}),
        unique_armor_effects=len({e for r in rows for e in r["armor_effects"]}),
    ),
    rows=rows,
    unresolved_effect_references=sorted(missing),
)
Path("docs/reports/armor-lifecycle-structural-coverage.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
)
print(report["counts"], flush=True)
