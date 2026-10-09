import json, gzip, zipfile, collections, pathlib

P = pathlib.Path("server/protocol")


def load(n):
    return json.load(open(P / n))


base = load("spells.json")["spells"]
trees = load("spell-effect-trees.json")
granted = load("granted-spell-effect-trees.json")
states = load("combat-state-definitions.json")
areas = load("native-effect-areas.json")["areas"]
breeds = load("breed-innate-definitions.json")["breeds"]
effects = {**trees["effects"], **states["effects"], **granted["effects"]}
spells = {**trees["spells"], **granted["spells"]}
baseids = {s["id"] for s in base}
names = {}
with zipfile.ZipFile("client/contents/i18n/i18n_es.jar") as z:
    for line in z.read("texts_es.properties").decode("utf8").splitlines():
        if line.startswith("content.3.") and "=" in line:
            k, v = line.split("=", 1)
            try:
                names[int(k.split(".")[-1])] = v
            except ValueError:
                pass


def roots(s):
    return sorted(
        {
            r
            for l in s.get("levels", [])
            for r in (l[2] if isinstance(l, list) else l.get("effects", []))
        }
    ) or s.get("effect_ids", [])


found = {}
missing = set()
for breed in breeds:
    b = breed["breed"]
    sources = [
        ("spell", s["id"], roots(spells.get(str(s["id"]), {})))
        for s in base
        if s["breed"] == b
    ]
    sources += [
        (
            "innate_state",
            s["reference"],
            roots(states["states"].get(str(s["reference"]), {})),
        )
        for s in breed.get("innate_states", [])
    ]
    for kind, ref, rs in sources:
        q = collections.deque(
            (r, [{"kind": kind, "reference": ref}, {"kind": "effect", "reference": r}])
            for r in rs
        )
        seen = set()
        while q:
            eid, path = q.popleft()
            if eid in seen:
                continue
            seen.add(eid)
            e = effects.get(str(eid))
            if e is None:
                missing.add(eid)
                continue
            family = e["effect_class"]
            p = e.get("parameters", [])
            children = e.get("children", [])
            for c in children:
                q.append((c, path + [{"kind": "effect", "reference": c}]))
            if family in (304, 315, 649) and p:
                idx = 4 if family == 649 else 0
                if len(p) <= idx:
                    continue
                # Include all evaluated values from native export, rather than guessing changing refs.
                vals = {int(p[idx])}
                for row in e.get("parameters_by_level", []):
                    if isinstance(row, list) and len(row) > idx // 2:
                        vals.add(int(row[idx // 2]))
                for v in vals:
                    if family == 649:
                        if v not in baseids:
                            row = found.setdefault(
                                v,
                                {
                                    "id": v,
                                    "name": names.get(v),
                                    "inventory_row": False,
                                    "tree_exported": str(v) in spells,
                                    "links": [],
                                },
                            )
                            link = {
                                "breed": b,
                                "source_kind": kind,
                                "source_reference": ref,
                                "grant_effect": eid,
                                "grant_criteria": e.get("criteria"),
                                "path": path,
                            }
                            if not any(
                                l["breed"] == b
                                and l["source_kind"] == kind
                                and l["source_reference"] == ref
                                for l in row["links"]
                            ):
                                row["links"].append(link)
                        obj = spells.get(str(v), {})
                        label = "granted_spell"
                    elif family == 315:
                        obj = areas.get(str(v), {})
                        label = "effect_area"
                    else:
                        obj = states["states"].get(str(v), {})
                        label = "state"
                    for child in roots(obj):
                        q.append(
                            (
                                child,
                                path
                                + [
                                    {"kind": label, "reference": v},
                                    {"kind": "effect", "reference": child},
                                ],
                            )
                        )
report = {
    "scope": "Structural reachability from all 722 class spells and native class innate states; all exported levels, children, state304, area315 and grant649. Criteria not evaluated; no runtime/GUI success implied.",
    "native_sources": [
        "spells.json",
        "breed-innate-definitions.json",
        "spell-effect-trees.json",
        "combat-state-definitions.json",
        "native-effect-areas.json",
        "granted-spell-effect-trees.json",
        "client/contents/i18n/i18n_es.jar!texts_es.properties",
    ],
    "base_spell_count": len(base),
    "granted_catalog_count": len(granted["spells"]),
    "class_linked_extra_count": len(found),
    "extras": sorted(found.values(), key=lambda r: r["id"]),
    "unresolved_effect_references": sorted(missing),
    "limitations": [
        "Only explicitly exported reference values are followed; dynamically computed references are not guessed.",
        "649 class links do not establish ownership, unlock level, condition truth or successful implementation.",
        "Other spell replacement/transform producer families are not asserted complete.",
    ],
}
out = pathlib.Path("docs/reports/class-extra-spells-audit.json")
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print("extras", len(found), "unresolved", len(missing))
r = found.get(6065)
print(json.dumps(r, ensure_ascii=False))
print(
    "list",
    [
        (r["id"], r["name"], sorted({l["breed"] for l in r["links"]}))
        for r in report["extras"]
    ],
)
