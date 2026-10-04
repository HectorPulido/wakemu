#!/usr/bin/env python3
"""Offline real common initialization for18 installed breeds; no socket/GUI.

One native catalog load, complete creation snapshots and the exact ordinary
server authority. Successful initialization is not a claim of gameplay support.
"""
from pathlib import Path
import sys, json, hashlib, random, traceback, datetime, csv, copy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.paths import DATA_ROOT, PROJECT_ROOT
from wakfu_server.combat_class_initialization import (
    BREEDS,
    plan,
    initialize_transaction,
)
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.combat_arena_selection import bounded_arena
from wakfu_server.combat_ordinary_authority import (
    OrdinaryActorAuthority,
    ordinary_cast_authority,
)
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.spells import available_spells, encode_deck
from wakfu_server.spell_audit import catalog, states_catalog
from wakfu_server.health import maximum
from wakfu_server.monsters import owned_instance
from wakfu_server.fight_checkpoint_store import snapshot


def source_hashes():
    root = Path(__file__).resolve().parents[1] / "wakfu_server/combat"
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.glob("*.py"))
    }


def run(cases=None, *, with_relative_probability=False):
    source_before = source_hashes()
    spells, states = catalog(), states_catalog()
    registry = json.loads(
        (DATA_ROOT / "effect-characteristic-registry.json").read_text()
    )
    timing = NativeEffectTimingProvider(states)
    geometry = map_geometry(1134)
    origin, target = next((tuple(a), tuple(b)) for a, b in geometry["edges"] if a != b)
    terrain = bounded_arena(geometry, origin, [target], radius=12)
    rows = []
    shared_factory = None
    if cases is None:
        cases = [
            dict(breed=breed, level=level)
            for breed in sorted(BREEDS)
            for level in (1, 200)
        ]
    for case in cases:
        breed, level = case["breed"], case["level"]
        definition = BREEDS[breed]
        resource = definition["resources"]
        hp = maximum(breed, level)
        character = dict(
            id=7,
            account_id=3,
            breed=breed,
            level=level,
            hp=hp,
            max_hp=hp,
            x=origin[0],
            y=origin[1],
            z=origin[2],
            map_id=1134,
            instance_id=0,
            builds={},
            inventory_items=[],
        )
        available = available_spells(breed, level)
        active = [s["id"] for s in available if s["kind"] == "active"][:3]
        passive = (
            ([s["id"] for s in available if s["kind"] == "passive"][:6])
            if level == 200
            else []
        )
        if "passive" in case:
            passive = list(case["passive"])
        deck = encode_deck(active, passive)
        creature = owned_instance(
            5525, 1, -7, map_id=1134, x=target[0], y=target[1], z=target[2]
        )
        player = Actor(
            7,
            0,
            origin,
            hp,
            resource["AP"],
            resource["MP"],
            0,
            level,
            3,
            True,
            max_hp=hp,
        )
        npc = Actor(
            -7,
            1,
            target,
            creature["hp"],
            creature["ap"],
            creature["mp"],
            creature["initiative"],
            1,
            max_hp=creature["max_hp"],
        )
        fight = Fight(
            10000 + breed * 100 + level,
            [player, npc],
            terrain["cells"],
            {0: {origin}, 1: {target}},
            terrain["edges"],
        )
        initialize_fight_snapshots(
            fight,
            characters={7: character},
            monsters={-7: creature},
            wp_resources={
                7: (resource["WP"], resource["WP"]),
                -7: (creature["wp"], creature["wp"]),
            },
            running_effects={7: (), -7: ()},
            initial_effect_uid=200,
        )
        player.direction = 0
        npc.direction = 3
        fight.map_id = 1134
        fight.instance_id = 0
        # Keep QI.V obstacle absence unknown: walkability does not prove it.
        fight.ready(3)
        before = snapshot(fight)
        authority = OrdinaryActorAuthority(
            characters={7: character},
            monsters={-7: creature},
            decks={7: frozenset(active + passive)},
            excluded_decks={7: frozenset()},
        )
        rng = random.Random(0)
        adapter = NativeServerRuntimeAdapter(
            actor_authority=authority,
            cast=ordinary_cast_authority(
                actors=authority, timing=timing, rng=rng, critical=False
            ),
        )
        if shared_factory is None:
            shared_factory = NativeEffectRuntimeFactory(
                effects=spells["effects"],
                state_catalog=states,
                characteristic_registry=registry,
                action_id=1,
                contexts=adapter.contexts(),
                displacement_authority=authority,
            )
        else:
            shared_factory.contexts = adapter.contexts()
            shared_factory.displacement_authority = authority

        if with_relative_probability:
            from wakfu_server.combat_relative_probability import RelativeGroupAuthority

            shared_factory.relative_group_children = RelativeGroupAuthority(
                effects=shared_factory.effects,
                actor_authority=authority,
                condition_context=adapter.condition,
                draw_integer=lambda n: rng.randint(1, n),
                draw_fraction=lambda fraction: rng.random() < fraction,
            )

        def observed_factory(preview, container):
            dispatcher, packets = shared_factory(preview, container)
            original = dispatcher._execute

            def execute(invocation, *args, **kwargs):
                try:
                    return original(invocation, *args, **kwargs)
                except Exception as error:
                    if not hasattr(error, "audit_reference"):
                        error.audit_reference = invocation.reference
                        error.audit_level = invocation.level
                        error.audit_container = copy.deepcopy(container)
                    raise

            dispatcher._execute = execute
            apply = dispatcher.native_state_handler.apply_reference

            def applying(effect, invocation, reference, state_level, **kwargs):
                try:
                    return apply(effect, invocation, reference, state_level, **kwargs)
                except Exception as error:
                    if effect is None:
                        error.audit_innate_reference = reference
                    raise

            dispatcher.native_state_handler.apply_reference = applying
            return dispatcher, packets

        row = dict(
            breed=breed,
            level=level,
            mode="innates" if level == 1 else "innates_and_first_six_owned_passives",
            native_resources=resource,
            active=active,
            passive=passive,
            gameplay_verified=False,
            actor_characteristic_count=len(player.effect_stats),
            authority="OrdinaryActorAuthority/ordinary_cast_authority",
            rollback_preserved=None,
        )
        row.update(
            {k: v for k, v in case.items() if k not in ("breed", "level", "passive")}
        )
        try:
            initial = plan(character, deck, spells, states)
            preview, packets = initialize_transaction(
                fight, initial, observed_factory, states, owner_id=3
            )
            row.update(
                status="initialized",
                packet_count=len(packets),
                retained_count=len(preview.native_retained_records),
                running_states=[
                    dict(reference=s.reference, level=s.level, protected=s.protected)
                    for s in preview.actors[7].state_ledger.entries
                ],
            )
        except Exception as error:
            ref = getattr(error, "audit_reference", None)
            effect = shared_factory.effects.get(str(ref)) if ref is not None else None
            row.update(
                status="blocked",
                error=type(error).__name__,
                reason=str(error),
                effect_reference=ref,
                effect_class=None if effect is None else effect["effect_class"],
                effect_level=getattr(error, "audit_level", None),
                innate_reference=getattr(error, "audit_innate_reference", None),
                container=getattr(error, "audit_container", None),
                native_criteria=None if effect is None else effect["criteria"],
                source_trace=traceback.format_exc(),
            )
        row["rollback_preserved"] = snapshot(fight) == before
        if not row["rollback_preserved"]:
            raise AssertionError("Audit mutated source fight")
        rows.append(row)
        print(
            f"breed={breed} level={level} {row['status']} {row.get('effect_reference')} {row.get('effect_class')} {row.get('reason','')}",
            flush=True,
        )
    return dict(
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope="Offline common initialization only; no events synthesized or client gameplay asserted",
        sources_before=source_before,
        sources_after=source_hashes(),
        sources_stable=source_before == source_hashes(),
        provenance={
            p: hashlib.sha256((DATA_ROOT / p).read_bytes()).hexdigest()
            for p in (
                "breed-innate-definitions.json",
                "native-actor-characteristics.json.gz",
                "spell-effect-trees.json",
                "combat-state-definitions.json.gz",
                "spells.json",
                "native-actor-properties.json",
                "native-retained-effect-metadata.json",
                "effect-characteristic-registry.json",
                "base-health.json",
            )
        },
        snapshot="initialize_fight_snapshots native complete PA; actual installed AP/MP/WP by breed",
        terrain=dict(
            map_id=1134,
            origin=origin,
            target=target,
            native_cells=len(terrain["cells"]),
        ),
        rows=rows,
    )


if __name__ == "__main__":
    result = run()
    directory = PROJECT_ROOT / "docs/reports/combat-inventory"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "class-initialization-audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    columns = (
        "breed",
        "level",
        "mode",
        "status",
        "effect_reference",
        "effect_class",
        "innate_reference",
        "reason",
        "rollback_preserved",
        "gameplay_verified",
    )
    with (directory / "class-initialization-audit.csv").open("w") as out:
        writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["rows"])
