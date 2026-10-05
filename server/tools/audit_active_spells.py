#!/usr/bin/env python3
"""Offline actual common cast entry: legal levels, innates, real terrain/LOS.

One catalog load. Outcomes distinguish effect execution from no-effect casts;
no result is a claim of complete spell/class gameplay or graphical validation.
"""
from pathlib import Path
import sys, json, random, struct, copy, csv, datetime, collections, argparse, traceback, hashlib
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_class_initialization as init
from wakfu_server.spells import SPELLS, encode_deck
from wakfu_server.combat_class_initialization import (
    BREEDS,
    plan,
    initialize_transaction,
)
from wakfu_server.combat_spell_transaction import prepare_spell_transaction
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_ordinary_authority import (
    OrdinaryActorAuthority,
    ordinary_cast_authority,
)
from wakfu_server.combat_los import authoritative_visible, static_visible
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.combat_arena_selection import bounded_arena
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_wire import arena as encode_arena, topology, decode_topology
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.combat_server_spell import server_runtime
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.spell_audit import catalog, states_catalog
from wakfu_server.monsters import owned_instance
from wakfu_server.health import maximum
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.paths import DATA_ROOT, PROJECT_ROOT


def target_candidates(definition, level, terrain, origin, *, spell_reference=None):
    minimum, maximum_range, _ = definition["levels"][level - 1]
    cells = []
    for cell in sorted(
        terrain["cells"],
        key=lambda c: (abs(c[0] - origin[0]) + abs(c[1] - origin[1]), c),
    ):
        dx, dy = cell[0] - origin[0], cell[1] - origin[1]
        if not minimum <= abs(dx) + abs(dy) <= maximum_range:
            continue
        if definition["linear"] and dx and dy:
            continue
        if definition["line_of_sight"]:
            try:
                if not static_visible(1134, origin, cell):
                    continue
            except ValueError:
                continue
        cells.append(cell)
    variants = []
    native_self_candidate = False
    if spell_reference is not None:
        from wakfu_server.combat_self_cast import catalog as self_cast_catalog

        policy = self_cast_catalog().get(str(spell_reference))
        if not isinstance(policy, dict):
            raise ValueError("Audit spell lacks native self-cast policy")
        # Generate candidate scenarios, not an authorization: the common cast
        # entry evaluates the actual conditional table in the initialized fight.
        native_self_candidate = policy["allowed"] or any(
            rule["allowed"] for rule in policy["conditional"]
        )
    if (minimum <= 0 <= maximum_range or native_self_candidate) and not definition[
        "free_cell"
    ]:
        # Exercise the real common-entry LOS gate; do not silently discard self
        # merely because the exported Sf ray reports false at this endpoint.
        variants.append(("self", origin))
    away = [c for c in cells if c != origin]
    if away and not definition["free_cell"]:
        variants.append(("enemy", away[0]))
    if away:
        variants.append(("empty_cell", away[0]))
    return variants


def fixture(
    breed,
    level,
    enemy_cell,
    terrain,
    origin,
    *,
    ready=True,
    monster_reference=5525,
    monster_level=1,
):
    resource = BREEDS[breed]["resources"]
    hp = maximum(breed, level)
    character = dict(
        id=7,
        account_id=3,
        name="Offline Audit",
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
    creature = owned_instance(
        monster_reference,
        monster_level,
        -7,
        map_id=1134,
        x=enemy_cell[0],
        y=enemy_cell[1],
        z=enemy_cell[2],
    )
    placement = {0: {origin}, 1: {enemy_cell}}
    own_arena = encode_arena(1134, 0, terrain["cells"], placement)
    # Use the real own bootstrap policy/table, not a fake empty obstacle set.
    decoded = decode_topology(topology(own_arena))
    if decoded["team_values"] != own_arena["team_values"]:
        raise AssertionError("Native QL table roundtrip differs")
    own_arena.update(
        validated_cells=terrain["cells"],
        valid_edges=terrain["edges"],
        placement_cells=placement,
    )
    fight, _ = create_placement(
        character,
        creature,
        own_arena,
        fight_id=10000 + breed * 100 + level,
        player_ap=resource["AP"],
        player_mp=resource["MP"],
        player_wp=resource["WP"],
        player_initiative=0,
        terrain_effect_id=46,
        terrain_instance_id=-300,
    )
    pc, npc = fight.actors[7], fight.actors[-7]
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
    pc.direction = 0
    npc.direction = 3
    fight.map_id = 1134
    fight.instance_id = 0
    if ready:
        fight.ready(3)
    return character, creature, fight


def observed(factory, records):
    def make(preview, container):
        dispatcher, packets = factory(preview, container)
        original_diagnose = dispatcher._diagnose

        def diagnose(invocation, **details):
            if details.get("status") == "skipped_condition":
                records.append(
                    (invocation.reference, "condition_false", details.get("criteria"))
                )
            return original_diagnose(invocation, **details)

        dispatcher._diagnose = diagnose
        original = dispatcher._execute

        def execute(invocation, *a, **kw):
            try:
                out = original(invocation, *a, **kw)
                records.append((invocation.reference, "returned", repr(out)))
                return out
            except Exception as error:
                if not hasattr(error, "audit_reference"):
                    error.audit_reference = invocation.reference
                    error.audit_level = invocation.level
                raise

        dispatcher._execute = execute
        apply_reference = dispatcher.native_state_handler.apply_reference

        def applying(effect, invocation, reference, level, **kw):
            try:
                return apply_reference(effect, invocation, reference, level, **kw)
            except Exception as error:
                if effect is None:
                    error.audit_innate_reference = reference
                raise

        dispatcher.native_state_handler.apply_reference = applying
        return dispatcher, packets

    return make


def run(
    limit=None,
    only_breed=None,
    cases=None,
    output_name="docs/reports/combat-inventory/active-cast-audit.json",
    max_cast_seconds=2.0,
    critical=False,
    sequence=False,
    monster_reference=5525,
    monster_level=1,
):
    if max_cast_seconds <= 0:
        raise ValueError("Cast time budget must be positive")
    if type(critical) is not bool:
        raise ValueError("Audit requires an explicit normal or critical branch")
    source_before = init.source_hashes()
    spells, states = catalog(), states_catalog()
    registry = json.loads(
        (DATA_ROOT / "effect-characteristic-registry.json").read_text()
    )
    timing = NativeEffectTimingProvider(states)
    geometry = map_geometry(1134)
    origin = (-8, -7, -1)
    seed = (-7, -7, -1)
    terrain = bounded_arena(geometry, origin, [seed], radius=12)
    active = sorted(
        (
            r
            for r in SPELLS.values()
            if r["kind"] == "active"
            and r["breed"] in BREEDS
            and (only_breed is None or r["breed"] == only_breed)
        ),
        key=lambda r: (r["breed"], r["id"]),
    )
    if cases is not None:
        selected = {(r["spell_id"], r["level"], r["variant"]) for r in cases}
        active = [r for r in active if any(k[0] == r["id"] for k in selected)]
    if limit is not None:
        active = active[:limit]
    rows = []
    shared = None
    for number, spell in enumerate(active, 1):
        definition = spells["spells"].get(str(spell["id"]))
        levels = (
            {max(1, spell["unlock_level"]), 200}
            if cases is None
            else {k[1] for k in selected if k[0] == spell["id"]}
        )
        for level in sorted(levels):
            if (
                type(level) is not int
                or not max(1, spell["unlock_level"]) <= level <= 200
            ):
                raise ValueError("Focused case requests an illegal character level")
            if level > 200:
                continue
            if cases is not None and not any(
                k[:2] == (spell["id"], level) for k in selected
            ):
                continue
            variants = (
                []
                if definition is None
                else target_candidates(
                    definition, level, terrain, origin, spell_reference=spell["id"]
                )
            )
            if not variants:
                rows.append(
                    dict(
                        breed=spell["breed"],
                        spell_id=spell["id"],
                        level=level,
                        variant="none",
                        status="no_verified_legal_target",
                        reason="No requested-range/LOS cell in exported arena",
                        gameplay_verified=False,
                        critical=critical,
                        rollback_preserved=True,
                        no_source_resource_spend=True,
                    )
                )
            for variant, cell in variants:
                if cases is not None and (spell["id"], level, variant) not in selected:
                    continue
                enemy_cell = (
                    cell
                    if variant == "enemy"
                    else next(
                        c for c in sorted(terrain["cells"]) if c not in (origin, cell)
                    )
                )
                character, creature, base = fixture(
                    spell["breed"],
                    level,
                    enemy_cell,
                    terrain,
                    origin,
                    monster_reference=monster_reference,
                    monster_level=monster_level,
                )
                deck = encode_deck([spell["id"]])
                rng = random.Random(0)
                authority = OrdinaryActorAuthority(
                    characters={7: character},
                    monsters={-7: creature},
                    decks={7: frozenset([spell["id"]])},
                    excluded_decks={7: frozenset()},
                )
                adapter = NativeServerRuntimeAdapter(
                    actor_authority=authority,
                    cast=ordinary_cast_authority(
                        actors=authority, timing=timing, rng=rng, critical=critical
                    ),
                )
                # Use the production factory, including its shared lottery,
                # relative probability and summon authorities. A manually
                # assembled factory falsely reports missing supported handlers.
                shared, adapter = server_runtime(
                    character,
                    {creature["id"]: creature},
                    deck,
                    action_id=1,
                    critical=critical,
                    rng=rng,
                )
                row = dict(
                    breed=spell["breed"],
                    spell_id=spell["id"],
                    level=level,
                    variant=variant,
                    cell=cell,
                    gameplay_verified=False,
                    critical=critical,
                    deck_active=[spell["id"]],
                    deck_passive=[],
                )
                records = []
                before = snapshot(base)
                stage = "initialization"
                cast_started = None
                try:
                    if sequence:
                        from wakfu_server.combat_server_spell import (
                            prepare_server_initialization,
                        )

                        source, init_packets = prepare_server_initialization(
                            character,
                            {creature["id"]: creature},
                            base,
                            3,
                            deck,
                            action_id=1,
                            rng=rng,
                            fight_start=True,
                        )
                    else:
                        source, init_packets = initialize_transaction(
                            base,
                            plan(character, deck, spells, states),
                            observed(shared, records),
                            states,
                            owner_id=3,
                        )
                    if snapshot(base) != before:
                        raise AssertionError("Initialization mutated source")
                    row["initialization_packets"] = len(init_packets)
                    row["innate_states"] = [
                        s.reference for s in source.actors[7].state_ledger.entries
                    ]
                    passed = []
                    while source.current is not None and source.current.id != 7:
                        passed.append(source.current.id)
                        source.end_server_turn(source.current.id, source.turn_id)
                    row["pre_cast_passed_server_turns"] = passed
                    before = snapshot(source)
                    stage = "cast"
                    cast_started = time.monotonic()
                    records.clear()

                    def los(a, b, preview):
                        return authoritative_visible(
                            1134,
                            a,
                            b,
                            preview,
                            blocking_footprints={
                                actor.id: {actor.position[:2]}
                                for actor in preview.actors.values()
                                if actor.hp > 0
                            },
                        )

                    body = struct.pack(">qqiih", 7, (7 << 32) | spell["id"], *cell)
                    result = prepare_spell_transaction(
                        body,
                        character,
                        source,
                        3,
                        deck,
                        wp_current=source.actors[7].effect_stats[4],
                        action_id=1,
                        line_of_sight=los,
                        runtime_factory=observed(shared, records),
                        critical=critical,
                        conditional_context=lambda request, preview: adapter.cast_condition(
                            preview, request
                        ),
                    )
                    expected = copy.deepcopy(source)
                    caster = expected.actors[7]
                    for name, key, stat in (("ap", "ap", 2), ("mp", "mp", 3)):
                        setattr(
                            caster,
                            name,
                            getattr(caster, name) - result.plan["costs"][key],
                        )
                        caster.effect_stats[stat] = getattr(caster, name)
                    caster.effect_stats[4] -= result.plan["costs"]["wp"]
                    actual_state = snapshot(result.fight)
                    expected_state = snapshot(expected)
                    changes = actual_state["actors"] != expected_state["actors"]
                    retention_changes = any(
                        actual_state.get(k) != expected_state.get(k)
                        for k in actual_state
                        if k.startswith(
                            ("owned_", "native_retained", "native_owned_group")
                        )
                    )
                    effect_packets = [op for op, _ in result.packets[2:]]
                    status = (
                        "actor_state_changed"
                        if changes
                        else "retention_changed"
                        if retention_changes
                        else "effect_packets_only"
                        if effect_packets
                        else "no_effect_observed"
                    )
                    row.update(
                        status=status,
                        costs=result.plan["costs"],
                        effect_packet_opcodes=effect_packets,
                        effect_events=list(result.events),
                        effect_outcomes=repr(result.outcomes),
                        executed_reference_count=len(records),
                        state_changed_beyond_costs=changes,
                    )
                    row["rollback_preserved"] = snapshot(source) == before
                    row["no_source_resource_spend"] = row["rollback_preserved"]
                    row["_first_cast_elapsed"] = time.monotonic() - cast_started
                    if sequence:
                        from audit_spell_sequence import audit_sequence
                        from wakfu_server.combat_cast import prepare_spell_cast
                        from wakfu_server.combat_server_spell import (
                            prepare_server_turn_end,
                        )

                        target_id = next(
                            (
                                a.id
                                for a in source.actors.values()
                                if a.position == cell and a.hp > 0
                            ),
                            None,
                        )

                        def preflight_second(current):
                            return prepare_spell_cast(
                                body,
                                character,
                                current,
                                3,
                                deck,
                                wp=current.actors[7].effect_stats[4],
                                line_of_sight=los,
                                conditional_context=lambda request, preview: adapter.cast_condition(
                                    preview, request
                                ),
                            )

                        def cast_second(current):
                            return prepare_spell_transaction(
                                body,
                                character,
                                current,
                                3,
                                deck,
                                wp_current=current.actors[7].effect_stats[4],
                                action_id=2,
                                line_of_sight=los,
                                runtime_factory=observed(shared, records),
                                critical=critical,
                                conditional_context=lambda request, preview: adapter.cast_condition(
                                    preview, request
                                ),
                            )

                        def finish_turn(current):
                            return prepare_server_turn_end(
                                character,
                                {creature["id"]: creature},
                                current,
                                deck,
                                actor_id=7,
                                action_id=3,
                                rng=rng,
                            )

                        def observe_second(current, transaction):
                            expected = copy.deepcopy(current)
                            actor = expected.actors[7]
                            for name, stat in (("ap", 2), ("mp", 3)):
                                setattr(
                                    actor,
                                    name,
                                    getattr(actor, name)
                                    - transaction.plan["costs"][name],
                                )
                                actor.effect_stats[stat] = getattr(actor, name)
                            actor.effect_stats[4] -= transaction.plan["costs"]["wp"]
                            actual_state, expected_state = snapshot(
                                transaction.fight
                            ), snapshot(expected)
                            if actual_state["actors"] != expected_state["actors"]:
                                return "actor_state_changed"
                            if any(
                                actual_state.get(k) != expected_state.get(k)
                                for k in actual_state
                                if k.startswith(
                                    ("owned_", "native_retained", "native_owned_group")
                                )
                            ):
                                return "retention_changed"
                            return (
                                "effect_packets_only"
                                if transaction.packets[2:]
                                else "no_effect_observed"
                            )

                        row["sequence"] = audit_sequence(
                            result,
                            actor_id=7,
                            owner_id=3,
                            preflight=preflight_second,
                            cast=cast_second,
                            turn_end=finish_turn,
                            rng=rng,
                            snapshot=snapshot,
                            target_id=target_id,
                            target_cell=cell,
                            observe=observe_second,
                        )
                except Exception as error:
                    ref = getattr(error, "audit_reference", None)
                    eff = shared.effects.get(str(ref)) if ref is not None else None
                    row.update(
                        status="initialization_blocked"
                        if stage == "initialization"
                        else "cast_rejected",
                        stage=stage,
                        error=type(error).__name__,
                        reason=str(error),
                        effect_reference=ref,
                        innate_reference=getattr(error, "audit_innate_reference", None),
                        effect_class=None if eff is None else eff["effect_class"],
                        native_criteria=None if eff is None else eff["criteria"],
                        source_trace=traceback.format_exc(),
                        executed_reference_count=len(records),
                    )
                    row["rollback_preserved"] = (
                        snapshot(base if stage == "initialization" else source)
                        == before
                    )
                    row["no_source_resource_spend"] = row["rollback_preserved"]
                false_conditions = [r for r in records if r[1] == "condition_false"]
                # Keep every skipped branch visible. A successful damage root
                # does not prove that a retained state or passive was activated.
                row["skipped_conditions"] = [
                    dict(
                        effect_reference=reference,
                        criteria=criteria,
                        effect_class=shared.effects.get(str(reference), {}).get(
                            "effect_class"
                        ),
                    )
                    for reference, _, criteria in false_conditions
                ]
                row["visited_effect_references"] = sorted({r[0] for r in records})
                row["cast_elapsed_seconds"] = row.pop(
                    "_first_cast_elapsed",
                    None if cast_started is None else time.monotonic() - cast_started,
                )
                row["max_cast_seconds"] = max_cast_seconds
                row["client_unblocked_verified"] = False
                from audit_spell_sequence import blocking_verdict

                row["blocking_verdict"] = blocking_verdict(row, max_cast_seconds)
                row["first_false_condition"] = (
                    None
                    if not false_conditions
                    else dict(
                        effect_reference=false_conditions[0][0],
                        criteria=false_conditions[0][2],
                        effect_class=shared.effects.get(
                            str(false_conditions[0][0]), {}
                        ).get("effect_class"),
                    )
                )
                if not row["rollback_preserved"]:
                    raise AssertionError("Audit mutated source fight")
                rows.append(row)
        if number % 10 == 0 or number == len(active):
            partial = (PROJECT_ROOT / output_name).with_suffix(".partial.json")
            partial.parent.mkdir(parents=True, exist_ok=True)
            partial.write_text(
                json.dumps(
                    dict(processed_definitions=number, rows=rows),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
            print(
                f"{number}/{len(active)} active definitions; {len(rows)} cases; "
                + str(dict(collections.Counter(r["status"] for r in rows))),
                flush=True,
            )
    after = init.source_hashes()
    return dict(
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope="Common offline request+innate initialization+explicit cast branch; no GUI or full gameplay claim",
        critical=critical,
        sequence_enabled=sequence,
        sequence_status_counts=dict(
            collections.Counter(
                step["stage"] + ":" + step["status"]
                for row in rows
                for step in row.get("sequence", {}).get("steps", ())
            )
        ),
        active_definitions=len(active),
        rows=rows,
        sources_before=source_before,
        sources_after=after,
        status_counts=dict(collections.Counter(r["status"] for r in rows)),
        provenance={
            name: hashlib.sha256((DATA_ROOT / name).read_bytes()).hexdigest()
            for name in (
                "spells.json",
                "spell-effect-trees.json",
                "combat-state-definitions.json.gz",
                "native-actor-characteristics.json.gz",
                "native-retained-effect-metadata.json",
                "breed-innate-definitions.json",
                "effect-characteristic-registry.json",
                "amakna-combat-los.json",
            )
        },
        sources_stable=source_before == after,
        terrain=dict(map_id=1134, origin=origin, cells=len(terrain["cells"])),
        opponent=dict(reference=monster_reference, level=monster_level),
        limitations=[
            "Bare own actors without equipped passives; legal native resources are not inflated",
            "Explicit seeded normal/critical branch; opponent statistics come from the selected native monster/level; injured targets/other states not explored",
            "Opt-in sequence preserves actual first-cast HP/AP/MP/WP and identifies changed preconditions separately",
            "Self variants satisfy range/occupancy; common entry still checks native exported LOS and can reject",
            "Native QL obstacle table comes from own arena+create_placement and topology roundtrip; not from walkability",
            "No-effect results distinguish conditional ineligibility from unsupported execution",
            "Earlier NPC turn is passed using ordinary FSM; no NPC action or turn-event replay is asserted",
            "Source rollback and no source spend do not mean cost-free committed no-effect casts",
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--breed", type=int)
    parser.add_argument("--from-report")
    parser.add_argument("--reason")
    parser.add_argument("--max-cast-seconds", type=float, default=2.0)
    parser.add_argument(
        "--sequence",
        action="store_true",
        help="Audit second cast with live resources and native turn-end boundary",
    )
    parser.add_argument("--monster-reference", type=int, default=5525)
    parser.add_argument("--monster-level", type=int, default=1)
    parser.add_argument(
        "--critical",
        action="store_true",
        help="Execute the critical branch, not a probability roll",
    )
    parser.add_argument(
        "--output", default="docs/reports/combat-inventory/active-cast-audit.json"
    )
    args = parser.parse_args()
    cases = None
    if args.from_report:
        cases = [
            r
            for r in json.loads(Path(args.from_report).read_text())["rows"]
            if args.reason is None or r.get("reason") == args.reason
        ]
    report = run(
        args.limit,
        args.breed,
        cases,
        args.output,
        args.max_cast_seconds,
        args.critical,
        args.sequence,
        args.monster_reference,
        args.monster_level,
    )
    path = PROJECT_ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    columns = (
        "breed",
        "spell_id",
        "level",
        "variant",
        "status",
        "effect_reference",
        "effect_class",
        "reason",
        "rollback_preserved",
        "no_source_resource_spend",
        "gameplay_verified",
    )
    with path.with_suffix(".csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["rows"])
    print("Report saved; source stability=" + str(report["sources_stable"]), flush=True)
