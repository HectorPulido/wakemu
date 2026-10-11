"""Read-only Ecaflip closure from one published PostgreSQL revision.

This inventories source dependencies, not functional coverage. No protocol-file
fallback, catalog publication, combat mutation, or service operation is used.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import os

import psycopg


BREED = 6
EFFECT_PATHS = (
    "spell-effect-trees.json",
    "granted-spell-effect-trees.json",
    "combat-state-definitions.json",
    "native-area-effect-trees.json",
)


def compact(effect):
    return dict(effect)


def reference_values(effect, index):
    """Use exported samples when available; preserve every declared level arm."""
    samples = effect.get("parameters_by_level", ())
    values = {int(row[index]) for row in samples if len(row) > index}
    if not values:
        pairs = effect.get("parameters", ())
        if len(pairs) > 2 * index + 1 and pairs[2 * index + 1] == 0:
            values.add(int(pairs[2 * index]))
    return values


def inventory(connection):
    revision = connection.execute(
        "SELECT a.revision FROM native_catalog_active a JOIN "
        "native_catalog_releases r USING(revision) WHERE a.id=1 AND r.complete"
    ).fetchone()[0]
    hashes = {}

    def document(path):
        raw, digest = connection.execute(
            "SELECT raw,sha256 FROM native_catalog_documents "
            "WHERE revision=%s AND path=%s",
            (revision, path),
        ).fetchone()
        raw = bytes(raw)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Catalog checksum mismatch: " + path)
        hashes[path] = digest
        return json.loads(raw)

    spells = [s for s in document("spells.json")["spells"] if s["breed"] in (BREED, -2)]
    innate = next(
        b
        for b in document("breed-innate-definitions.json")["breeds"]
        if b["breed"] == BREED
    )
    names = document("spell-names.json")
    zero = document("native-class-spell-level-zero.json")
    characteristic_registry = document("effect-characteristic-registry.json")["effects"]
    current_events = document("native-current-stat-events.json")["effects"]
    for path in EFFECT_PATHS:
        hashes[path] = connection.execute(
            "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (revision, path),
        ).fetchone()[0]

    cache = {}
    missing = set()

    def record(kind, identity):
        key = (kind, identity)
        if key in cache:
            return cache[key]
        collection = {
            "effect": "effects",
            "spell": "spells",
            "state": "states",
            "area": "areas",
        }[kind]
        paths = EFFECT_PATHS
        if kind == "state":
            paths = ("combat-state-definitions.json",)
        elif kind == "area":
            paths = ("native-effect-areas.json",)
            if paths[0] not in hashes:
                hashes[paths[0]] = connection.execute(
                    "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
                    (revision, paths[0]),
                ).fetchone()[0]
        rows = connection.execute(
            "SELECT path,payload FROM native_catalog_records WHERE revision=%s "
            "AND path=ANY(%s) AND collection=%s AND record_key=%s",
            (revision, list(paths), collection, str(identity)),
        ).fetchall()
        if not rows:
            missing.add(f"{kind}:{identity}")
            cache[key] = None
            return None
        # Match the shared merge identity rather than silently accepting drift.
        values = [row[1] for row in rows]
        for field in (
            "effect_class",
            "parameters",
            "children",
            "criteria",
            "target_masks",
        ):
            if kind == "effect" and any(
                v.get(field) != values[0].get(field) for v in values[1:]
            ):
                raise ValueError(f"Conflicting source {kind}:{identity}/{field}")
        result = dict(values[0], catalog_paths=sorted(row[0] for row in rows))
        cache[key] = result
        return result

    def closure(seeds):
        seen, pending = set(), list(seeds)
        while pending:
            key = pending.pop()
            if key in seen:
                continue
            seen.add(key)
            kind, identity = key
            row = record(kind, identity)
            if row is None:
                continue
            if kind == "spell":
                roots = {v for level in row.get("levels", ()) for v in level[2]}
                roots.update(zero.get("spells", {}).get(str(identity), [0, 0, []])[2])
                pending.extend(("effect", v) for v in roots)
            elif kind in ("state", "area"):
                pending.extend(("effect", v) for v in row.get("effect_ids", ()))
            else:
                pending.extend(("effect", v) for v in row.get("children", ()))
                family = row["effect_class"]
                target = {
                    304: ("state", 0),
                    321: ("state", 0),
                    421: ("effect", 0),
                    315: ("area", 0),
                    339: ("area", 0),
                    649: ("spell", 2),
                    426: ("spell", 0),
                }.get(family)
                if target:
                    pending.extend(
                        (target[0], v)
                        for v in reference_values(row, target[1])
                        if v > 0
                    )
        return seen

    rows = []
    for spell in spells:
        reached = closure([("spell", spell["id"])])
        rows.append(dict(spell, dependencies=sorted(f"{k}:{v}" for k, v in reached)))
    innate_nodes = closure([("state", s["reference"]) for s in innate["innate_states"]])
    summon_profiles = document("native-class-summon-abilities.json")["profiles"]
    summon_scope = {}
    while True:
        references = {
            v
            for (kind, _), effect in cache.items()
            if kind == "effect" and effect is not None and effect["effect_class"] == 307
            for v in reference_values(effect, 0)
            if v > 0
        }
        pending_profiles = references - {int(key) for key in summon_scope}
        if not pending_profiles:
            break
        for reference in sorted(pending_profiles):
            profile = summon_profiles.get(str(reference))
            if profile is None:
                missing.add(f"summon_profile:{reference}")
                summon_scope[str(reference)] = None
                continue
            summon_scope[str(reference)] = profile
            closure(
                [("spell", ability["reference"]) for ability in profile["abilities"]]
            )
    effects = {
        str(i): compact(v)
        for (k, i), v in cache.items()
        if k == "effect" and v is not None
    }
    states = {
        str(i): {
            k: v.get(k)
            for k in (
                "name",
                "description",
                "maximum_level",
                "effect_ids",
                "duration_base",
                "duration_per_level",
                "clock_actor",
                "tick_at_turn_end",
                "catalog_paths",
            )
        }
        for (kind, i), v in cache.items()
        if kind == "state" and v is not None
    }
    areas = {
        str(i): v for (kind, i), v in cache.items() if kind == "area" and v is not None
    }
    derived_spells = {
        str(i): dict(
            catalog_paths=v["catalog_paths"],
            root_effect_ids=sorted(
                {root for level in v.get("levels", ()) for root in level[2]}
            ),
            linear=v.get("linear"),
            free_cell=v.get("free_cell"),
            line_of_sight=v.get("line_of_sight"),
        )
        for (kind, i), v in cache.items()
        if kind == "spell" and v is not None and all(s["id"] != i for s in spells)
    }
    event_masks = {}
    for reference, effect in effects.items():
        for index, mask in enumerate(effect.get("target_masks", ())):
            for event in mask or ():
                event_masks.setdefault(str(event), []).append(
                    dict(
                        effect_reference=int(reference),
                        mask_index=index,
                        criteria=effect.get("criteria", ""),
                    )
                )
    families = {e["effect_class"] for e in effects.values()}
    return dict(
        schema="ecaflip-published-catalog-inventory-v1",
        revision=revision,
        source_sha256=hashes,
        breed=BREED,
        innate=innate,
        spells=rows,
        spell_names={
            str(s["id"]): s["name"]
            for s in names["spells"]
            if ("spell", s["id"]) in cache
        },
        derived_spells=derived_spells,
        effects=effects,
        states=states,
        areas=areas,
        summon_profiles=summon_scope,
        event_masks=event_masks,
        level_zero_spells={
            k: v
            for k, v in zero.get("spells", {}).items()
            if ("spell", int(k)) in cache
        },
        characteristic_bindings={
            k: v for k, v in characteristic_registry.items() if int(k) in families
        },
        intrinsic_current_stat_events={
            k: v for k, v in current_events.items() if int(k) in families
        },
        innate_dependencies=sorted(f"{k}:{v}" for k, v in innate_nodes),
        missing=sorted(missing),
        counts=dict(
            own_spells=sum(s["breed"] == BREED for s in spells),
            common_passives=sum(s["breed"] == -2 for s in spells),
            effects=len(effects),
            states=len(states),
            areas=len(areas),
            additional_referenced_spells=len(derived_spells),
            families=dict(
                sorted(Counter(e["effect_class"] for e in effects.values()).items())
            ),
        ),
        conditions=sorted(
            {
                name
                for e in effects.values()
                for name in re.findall(r"\b([A-Za-z_]\w*)\s*\(", e.get("criteria", ""))
            }
            - {"and", "or", "not", "if", "then", "else"}
        ),
        limitations=[
            "Structural closure is not runtime or client verification.",
            "All exported spell levels and state roots are included conservatively.",
            "Reference traversal covers apply-state, spell grants, nested casts and area constructors315/339; other reference families must be reviewed explicitly.",
            "Removal-only state references and condition-only references are preserved in expressions, not treated as executable roots.",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    password = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
    kwargs = dict(options="-c default_transaction_read_only=on")
    if password:
        kwargs["password"] = Path(password).read_text().strip()
    with psycopg.connect(os.environ["WAKFU_DATABASE_URL"], **kwargs) as connection:
        result = inventory(connection)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            dict(
                revision=result["revision"],
                counts=result["counts"],
                missing=result["missing"],
            )
        )
    )


if __name__ == "__main__":
    main()
