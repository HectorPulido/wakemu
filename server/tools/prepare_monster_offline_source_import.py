"""Append sealed NPC source books to an offline candidate; never publish or export."""
from copy import deepcopy

from prepare_monster_spell_activation import merge_records


def prepare_source_import(
    base_npc,
    trees,
    states,
    casting,
    roots,
    inventory,
    references,
    *,
    positive_actor_levels_only=False,
):
    """Return exact source additions and explicit admission blockers.

    The result deliberately preserves the original activation policy. The caller
    must validate dependency catalogs and execution before enabling references.
    """
    selected = sorted(set(references))
    additions = {kind: {} for kind in ("spells", "effects")}
    root_additions = {}
    rows = []
    for reference in selected:
        native = inventory[reference]
        blockers = []
        if native["min_level"] == 0 and not positive_actor_levels_only:
            blockers.append("unsupported_native_zero_level_activation")
        elif (
            not 0 <= native["min_level"] <= native["max_level"]
            or native["max_level"] < 1
        ):
            blockers.append("invalid_native_level_interval")
        deps = native["dependencies"]
        if (
            deps["missing_definitions"]
            or native["missing_casting_tables"]
            or native["missing_casting_root_metadata"]
        ):
            blockers.append("native_input_incomplete")
        spell_ids = list(map(str, deps["spell_ids"]))
        effect_ids = list(map(str, deps["effect_ids"]))
        state_ids = list(map(str, deps["state_ids"]))
        if any(
            key not in trees["spells"] or key not in casting["spells"]
            for key in spell_ids
        ):
            blockers.append("native_spell_or_casting_input_missing")
        if any(key not in states["states"] for key in state_ids):
            blockers.append("native_state_input_missing")
        missing_effects = [
            key
            for key in effect_ids
            if key not in trees["effects"] and key not in states["effects"]
        ]
        if missing_effects:
            blockers.append("native_effect_input_missing")
        rows.append(
            dict(
                ref=reference,
                min_level=native["min_level"],
                max_level=native["max_level"],
                validation_min_level=max(1, native["min_level"]),
                blockers=blockers,
                spell_ids=deps["spell_ids"],
                state_ids=deps["state_ids"],
                effect_ids=deps["effect_ids"],
                ownership_changed=False,
            )
        )
        if blockers:
            continue
        for key in spell_ids:
            additions["spells"][key] = deepcopy(trees["spells"][key])
            root_ids = {
                str(effect)
                for level in casting["spells"][key]["levels"]
                for effect in level[2]
            }
            root_ids.update(
                map(str, casting["spells"][key].get("level_zero_roots", []))
            )
            for root in root_ids:
                if root not in roots["roots"]:
                    raise ValueError("Missing original casting root: " + root)
                root_additions[root] = deepcopy(roots["roots"][root])
        for key in effect_ids:
            sources = [
                table[key]
                for table in (trees["effects"], states["effects"])
                if key in table
            ]
            chosen = sources[0]
            for other in sources[1:]:
                merge_records({key: chosen}, {key: other}, effects=True)
            additions["effects"][key] = deepcopy(chosen)
    npc = dict(base_npc)
    for kind in additions:
        npc[kind] = merge_records(
            base_npc[kind], additions[kind], effects=kind == "effects"
        )
    return npc, root_additions, rows
