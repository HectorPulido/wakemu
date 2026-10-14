"""Typed constructor-state dependencies, independent of owned spell execution."""
from collections import defaultdict


def build_initial_lifecycle_index(monsters, effects, states, spells, areas, supported):
    from build_monster_effect_work_queue import (
        dependency_namespace,
        predicate_signatures,
    )

    rows = []
    groups = {}
    for monster in monsters:
        for initial in monster.get("initial_states", []):
            state_id = str(initial["state_id"])
            start = ("state", state_id)
            todo = [(start, [start])]
            seen = set()
            while todo:
                (kind, identity), path = todo.pop()
                if (kind, identity) in seen:
                    continue
                seen.add((kind, identity))
                if kind != "effect":
                    table = {"state": states, "spell": spells, "area": areas}[kind]
                    if identity not in table:
                        rows.append(
                            {
                                "reference": monster["ref"],
                                "spell_id": None,
                                "initial_state": initial,
                                "path": path,
                                "missing_source_node": [kind, identity],
                            }
                        )
                    todo.extend(
                        (("effect", value), path + [("effect", value)])
                        for value in sorted(table.get(identity, ()))
                    )
                    continue
                effect = effects.get(identity)
                row = {
                    "reference": monster["ref"],
                    "spell_id": None,
                    "initial_state": initial,
                    "path": path,
                    "effect_id": int(identity),
                }
                if effect is None:
                    row["missing_source_node"] = [kind, identity]
                    rows.append(row)
                    continue
                family = effect["family"]
                row.update(
                    effect_family=family,
                    criterion=effect.get("criteria", ""),
                    registered=family in supported,
                    execution_proven=False,
                )
                rows.append(row)
                keys = [("family:" + str(family), None)]
                keys += [
                    ("predicate:" + signature, signature)
                    for _, signature in predicate_signatures(row["criterion"])
                ]
                for key, predicate in keys:
                    group = groups.setdefault(
                        key,
                        {
                            "block_id": "initial:" + key,
                            "spell_id": None,
                            "references": set(),
                            "effect_ids": set(),
                            "projected_affected_owned_spell_ids": set(),
                            "predicate_signature": predicate,
                            "execution_proven": False,
                            "owned_spell_impact_projection_only": True,
                        },
                    )
                    group["references"].add(monster["ref"])
                    group["effect_ids"].add(int(identity))
                    group["projected_affected_owned_spell_ids"].update(
                        ability["spell_id"] for ability in monster.get("abilities", [])
                    )
                todo.extend(
                    (("effect", value), path + [("effect", value)])
                    for value in sorted(effect["children"])
                )
                namespace = dependency_namespace(family)
                if namespace:
                    todo.extend(
                        ((namespace, value), path + [(namespace, value)])
                        for value in sorted(effect["references"])
                    )
    for group in groups.values():
        for field in ("references", "effect_ids", "projected_affected_owned_spell_ids"):
            group[field] = sorted(group[field])
        group["projected_unique_owned_spell_count"] = len(
            group["projected_affected_owned_spell_ids"]
        )
    ranked = sorted(
        groups.values(),
        key=lambda item: (
            -item["projected_unique_owned_spell_count"],
            item["block_id"],
        ),
    )
    return {
        "schema": "monster-initial-lifecycle-dependency-v1",
        "spell_id": None,
        "rows": rows,
        "dependency_groups": ranked,
        "registration_not_execution_proof": True,
        "owned_spell_impact_projection_only": True,
    }
