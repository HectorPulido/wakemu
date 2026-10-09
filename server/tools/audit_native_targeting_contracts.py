#!/usr/bin/env python3
"""Structural reachability audit of current area/selector contracts, not gameplay."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from wakfu_server.combat_effect_targets import area_offsets, native_selector_policy
from wakfu_server.combat_native_area_metadata import merge_native_point_areas
from wakfu_server.paths import DATA_ROOT, PROJECT_ROOT


def run():
    inputs = (
        DATA_ROOT / "spell-effect-trees.json",
        DATA_ROOT / "combat-state-definitions.json",
        DATA_ROOT / "native-point-areas.json",
        PROJECT_ROOT / "server/wakfu_server/combat/combat_effect_targets.py",
        PROJECT_ROOT / "server/wakfu_server/combat/combat_ordinary_authority.py",
        PROJECT_ROOT / "server/wakfu_server/combat/combat_area_geometry.py",
    )
    hashes = lambda: {
        str(p.relative_to(PROJECT_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in inputs
    }
    source_before = hashes()
    spells = json.loads((DATA_ROOT / "spell-effect-trees.json").read_text())
    with open(DATA_ROOT / "combat-state-definitions.json", "rt") as stream:
        states = json.load(stream)
    effects = dict(spells["effects"])
    conflicts = []
    for reference, definition in states["effects"].items():
        previous = effects.get(reference)
        if previous is not None and any(
            previous.get(k) != definition.get(k)
            for k in (
                "effect_class",
                "area_class",
                "area_native",
                "native_target_selector",
            )
        ):
            conflicts.append(reference)
        effects.setdefault(reference, definition)
    effects = merge_native_point_areas(effects)
    active = [
        s
        for s in json.loads((DATA_ROOT / "spells.json").read_text())["spells"]
        if s["kind"] == "active" and 1 <= s["breed"] <= 19 and s["breed"] != 17
    ]
    owners = defaultdict(set)
    unresolved_states = set()
    for spell in active:
        definition = spells["spells"].get(str(spell["id"]))
        if definition is None:
            continue
        roots = {
            r
            for row in definition["levels"][max(0, spell["unlock_level"] - 1) : 200]
            for r in row[2]
        }
        pending, seen = list(roots), set()
        while pending:
            reference = pending.pop()
            if reference in seen:
                continue
            seen.add(reference)
            effect = effects.get(str(reference))
            if effect is None:
                continue
            if effect.get("criteria", "").strip().lower() == "false":
                continue
            owners[str(reference)].add((spell["breed"], spell["id"]))
            pending.extend(effect.get("children") or ())
            raw = effect.get("parameters") or ()
            if effect["effect_class"] == 304 and len(raw) >= 2:
                if raw[1] != 0 or raw[0] != int(raw[0]):
                    unresolved_states.add(reference)
                    continue
                state = states["states"].get(str(int(raw[0])))
                if state is not None:
                    pending.extend(state["effect_ids"])
    rows, blockers = [], defaultdict(
        lambda: dict(references=[], spells=set(), breeds=set())
    )
    footprint_spells, footprint_breeds = set(), set()
    for reference, owned in owners.items():
        effect = effects[reference]
        reason = None
        try:
            policy = native_selector_policy(effect)
            area_offsets(effect, origin=(0, 0, 0), reference=(1, 0, 0), direction=1)
        except ValueError as error:
            reason = str(error)
        footprint = bool(
            reason is None
            and effect.get("native_target_selector") is not None
            and policy["in_area"]
            and effect.get("area_class") in ("anD", "anu", "anH", "anw", "any", "anx")
        )
        if footprint:
            footprint_spells.update(s for _, s in owned)
            footprint_breeds.update(b for b, _ in owned)
        if reason:
            block = blockers[reason]
            block["references"].append(int(reference))
            block["spells"].update(s for _, s in owned)
            block["breeds"].update(b for b, _ in owned)
        rows.append(
            dict(
                reference=int(reference),
                effect_class=effect["effect_class"],
                area_class=effect.get("area_class"),
                area_native=effect.get("area_native"),
                selector=effect.get("native_target_selector"),
                structural_blocker=reason,
                isotropic_footprint_route=footprint,
                possible_spells=sorted(s for _, s in owned),
                breeds=sorted({b for b, _ in owned}),
            )
        )
    with open(DATA_ROOT / "native-actor-characteristics.json", "rt") as stream:
        actors = json.load(stream)
    radii = Counter(row["physical_radius"] for row in actors["npc_profiles"].values())
    result = dict(
        scope="Potential active-spell/state graph, legal unlock..200; no condition evaluation, no gameplay/GUI PASS",
        limitations=[
            "State roots include all possible levels; dynamic304 references recorded separately",
            "Runtime explicit-PV routes may bypass area selection",
            "No claim every branch executes or cast succeeds",
        ],
        active_spell_count=len(active),
        possible_effect_count=len(rows),
        corrected_footprint_possible_spells=sorted(footprint_spells),
        corrected_footprint_breeds=sorted(footprint_breeds),
        npc_physical_radius_counts=dict(sorted(radii.items())),
        conflicting_definition_ids=conflicts,
        dynamic_state_references=sorted(unresolved_states),
        blockers={
            reason: {k: sorted(v) for k, v in block.items()}
            for reason, block in blockers.items()
        },
        source_sha256=source_before,
        sources_after=hashes(),
        rows=sorted(rows, key=lambda r: r["reference"]),
    )
    result["sources_stable"] = result["source_sha256"] == result["sources_after"]
    output = (
        PROJECT_ROOT
        / "docs/reports/combat-inventory/native-targeting-contract-audit.json"
    )
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in ("rows", "source_sha256", "corrected_footprint_possible_spells")
            },
            ensure_ascii=False,
        )
    )
    print("footprint_possible_spells", len(footprint_spells))
    return result


if __name__ == "__main__":
    run()
