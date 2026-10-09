#!/usr/bin/env python3
"""M3: legal owned Cra beacon placement, arrow reaction and cleanup traces."""
import argparse
import json
import random
import struct
from pathlib import Path
import audit_active_spells as audit
from audit_class_summon_reactions import actor_summary, native_event_trace
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_cast import prepare_spell_cast
from wakfu_server.combat_spell_transaction import prepare_spell_transaction
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.spells import encode_deck


BEACONS = ((7793, 3798, 7781), (7792, 3799, 7780), (4807, 3800, 7779))
ARROWS = ((4810, "AIR"), (4816, "EARTH"), (4820, "FIRE"))


def observed_plain(value):
    """Serialize checkpoint facts without traversing live providers or Fight objects."""
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, dict):
        return {str(key): observed_plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [observed_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [observed_plain(item) for item in sorted(value)]
    return {"unserialized_type": type(value).__name__}


def casting_error(error):
    result = dict(reason=str(error), error_type=type(error).__name__)
    for name in (
        "native_casting_result",
        "native_casting_diagnostic",
        "cast_validation_code",
    ):
        if hasattr(error, name):
            result[name] = observed_plain(getattr(error, name))
    return result


def run(output, level, matrix, *, impact_critical=False):
    hashes = audit.init.source_hashes()
    source, enemy = (-8, -7, -1), (-13, -7, -1)
    terrain = audit.bounded_arena(audit.map_geometry(1134), source, [enemy], radius=12)
    deck = encode_deck([reference for reference, _ in ARROWS])
    rows = []
    for index, (beacon_spell, profile, initial_state) in enumerate(BEACONS):
        arrows = ARROWS if matrix else (ARROWS[index],)
        for arrow, element in arrows:
            character, creature, fight = audit.fixture(
                9,
                level,
                enemy,
                terrain,
                source,
                ready=False,
                monster_reference=5574,
                monster_level=133,
            )
            rng = random.Random(0)

            def initialize(preview, action_id):
                return prepare_server_initialization(
                    character,
                    {-7: creature},
                    preview,
                    3,
                    deck,
                    action_id=action_id,
                    rng=rng,
                    fight_start=True,
                )

            def stats(actor):
                if actor.controlled:
                    return actual_actor_stats(
                        character,
                        actor,
                        fight.id,
                        wp_current=actor.effect_stats[4],
                        wp_maximum=audit.BREEDS[9]["resources"]["WP"],
                    )
                return actual_monster_actor_stats(
                    creature,
                    actor,
                    fight.id,
                    wp_current=creature["wp"],
                    wp_maximum=creature["wp"],
                )

            row = dict(
                beacon_spell=beacon_spell,
                profile=profile,
                state=initial_state,
                arrow=arrow,
                element=element,
                caster_level=level,
                impact_critical=impact_critical,
                steps=[],
            )
            rows.append(row)

            def summon_summary(preview, actor):
                result = actor_summary(actor)
                source = getattr(actor, "native_summon_source", None)
                registration = getattr(preview, "native_summon_registrations", {}).get(
                    actor.id
                )
                authority = (
                    registration.get("authority")
                    if isinstance(registration, dict)
                    else None
                )
                status = None
                status_error = None
                if hasattr(preview, "native_global_pv_collections"):
                    try:
                        from wakfu_server.combat_global_pv_collections import (
                            global_fighter_guards,
                            global_fighter_registered,
                        )

                        status = dict(
                            registered=global_fighter_registered(preview, actor.id),
                            **global_fighter_guards(preview, actor.id),
                        )
                    except Exception as error:
                        status_error = f"{type(error).__name__}: {error}"
                slot = getattr(actor, "native_obstacle_id", None)
                qi_row = None
                slots = getattr(preview, "native_qi_slots", None)
                if (
                    isinstance(slots, list)
                    and type(slot) is int
                    and 0 <= slot < len(slots)
                ):
                    qi_row = slots[slot]
                result["lifecycle"] = dict(
                    source=dict(source) if isinstance(source, dict) else None,
                    registration=(
                        dict(
                            actor_id=registration.get("actor_id"),
                            caster_id=registration.get("caster_id"),
                            controller_id=registration.get("controller_id"),
                            authority=(
                                {
                                    key: authority.get(key)
                                    for key in (
                                        "is_summon",
                                        "is_player",
                                        "breed_id",
                                        "native_real_level",
                                        "native_controller_id",
                                        "native_summoned_from_symbiot",
                                    )
                                }
                                if isinstance(authority, dict)
                                else None
                            ),
                        )
                        if isinstance(registration, dict)
                        else None
                    ),
                    ko_time_current=(
                        actor.effect_stats.get(14)
                        if isinstance(getattr(actor, "effect_stats", None), dict)
                        else None
                    ),
                    global_status=status,
                    global_status_error=status_error,
                    qi_slot=slot,
                    qi_slot_row=qi_row,
                    retirement=dict(
                        getattr(preview, "native_summon_retirements", {}).get(
                            actor.id, {}
                        )
                    )
                    if isinstance(
                        getattr(preview, "native_summon_retirements", {}), dict
                    )
                    else None,
                    recent_lifecycle_events=[
                        dict(event)
                        for event in getattr(preview, "events", ())
                        if event.get("actor_id") == actor.id
                        and event.get("kind") in ("death", "summon_out_of_play")
                    ][-4:],
                )
                return result

            try:
                fight, runtime, ready_packets = prepare_ready(
                    fight,
                    3,
                    True,
                    initialize=initialize,
                    stats_serializer=stats,
                    effects_serializer=actor_effects,
                    turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                        character, {-7: creature}, preview, deck, rng=rng, **boundary
                    ),
                    turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                        character,
                        {-7: creature},
                        preview,
                        deck,
                        rng=rng,
                        native_events=True,
                        area_callbacks=True,
                        **boundary,
                    ),
                )
                row["ready_packets"] = len(ready_packets)

                def advance_owner(force=False):
                    boundaries = []
                    for tick in range(len(runtime.fight.order) + 2):
                        current = runtime.fight.current
                        if current.id == character["id"] and (not force or tick > 0):
                            break
                        packets = (
                            runtime.end_turn(
                                current.owner_id, current.id, current.turn_count
                            )
                            if current.controlled
                            else runtime.end_server_turn(
                                current.id, runtime.fight.turn_id
                            )
                        )
                        ack = runtime.awaiting_ack
                        if ack is not None:
                            packets += runtime.acknowledge_turn(struct.pack(">i", ack))
                        boundaries.append(
                            dict(actor=current.id, ack=ack, packets=len(packets))
                        )
                    return boundaries

                row["initial_turns"] = advance_owner()

                def spell_uid(actual, reference):
                    grant = granted_spells(actual, 7).get(reference)
                    if reference not in (r for r, _ in ARROWS) and grant is None:
                        raise ValueError(
                            "Required beacon action was not actually granted"
                        )
                    return grant["uid"] if grant else (7 << 32) | reference

                def los(origin, destination, preview):
                    return authoritative_visible(
                        preview.map_id,
                        origin,
                        destination,
                        preview,
                        blocking_footprints={
                            actor.id: {actor.position[:2]}
                            for actor in preview.actors.values()
                            if actor.hp > 0
                        },
                    )

                def request(reference, cell):
                    actual = runtime.fight
                    return struct.pack(">qqiih", 7, spell_uid(actual, reference), *cell)

                def legal(reference, cell):
                    actual = runtime.fight
                    factory, adapter = server_runtime(
                        character,
                        {-7: creature},
                        deck,
                        action_id=2,
                        critical=False,
                        rng=rng,
                    )
                    return prepare_spell_cast(
                        request(reference, cell),
                        character,
                        actual,
                        3,
                        deck,
                        wp=actual.actors[7].effect_stats[4],
                        line_of_sight=los,
                        conditional_context=lambda plan, preview: adapter.cast_condition(
                            preview, plan
                        ),
                    )

                def cast(reference, cell):
                    actual = runtime.fight
                    critical = (
                        impact_critical
                        if reference in (r for r, _ in ARROWS)
                        else False
                    )
                    records, events, activations = [], [], []
                    step = dict(
                        spell=reference,
                        cell=list(cell),
                        before=actor_summary(actual.actors[7]),
                        enemy_before=actor_summary(actual.actors[-7]),
                        summons_before=[
                            summon_summary(actual, actor)
                            for actor in actual.actors.values()
                            if getattr(actor, "native_summon_source", None)
                        ],
                    )
                    row["steps"].append(step)
                    factory, adapter = server_runtime(
                        character,
                        {-7: creature},
                        deck,
                        action_id=2,
                        critical=critical,
                        rng=rng,
                    )
                    observed = audit.observed(factory, records)
                    observed.transaction_rng = factory.transaction_rng
                    try:
                        with native_event_trace(events, activations):
                            transaction = prepare_spell_transaction(
                                request(reference, cell),
                                character,
                                actual,
                                3,
                                deck,
                                wp_current=actual.actors[7].effect_stats[4],
                                action_id=2,
                                line_of_sight=los,
                                runtime_factory=observed,
                                conditional_context=lambda plan, preview: adapter.cast_condition(
                                    preview, plan
                                ),
                                critical=critical,
                            )
                        runtime.fight = transaction.fight
                        step.update(
                            status="committed",
                            costs=transaction.plan["costs"],
                            enemy_after=actor_summary(transaction.fight.actors[-7]),
                            after=actor_summary(transaction.fight.actors[7]),
                            summons_after=[
                                summon_summary(transaction.fight, actor)
                                for actor in transaction.fight.actors.values()
                                if getattr(actor, "native_summon_source", None)
                            ],
                            packets=[opcode for opcode, body in transaction.packets],
                        )
                    except Exception as error:
                        step.update(status="rejected", **casting_error(error))
                    step.update(trace=records, events=events, activations=activations)
                    return step

                candidates = sorted(
                    (
                        cell
                        for cell in terrain["cells"]
                        if cell not in (source, enemy)
                        and cell[2] == source[2]
                        and (cell[0] == source[0] or cell[1] == source[1])
                        and 1 <= abs(cell[0] - enemy[0]) + abs(cell[1] - enemy[1]) <= 2
                    ),
                    key=lambda cell: (
                        abs(cell[0] - enemy[0]) + abs(cell[1] - enemy[1]),
                        cell,
                    ),
                )
                rejected = []
                selected = None
                for cell in candidates:
                    try:
                        legal(beacon_spell, cell)
                        # Qualify the arrow geometry before selecting placement.
                        legal(arrow, cell)
                        selected = cell
                        break
                    except Exception as error:
                        rejected.append(dict(cell=list(cell), **casting_error(error)))
                row["placement_candidates"] = rejected
                if selected is None:
                    raise ValueError(
                        "No legal near-enemy beacon placement in bounded native cells"
                    )
                created = cast(beacon_spell, selected)
                if created["status"] != "committed":
                    raise ValueError("Actual beacon creation failed")
                beacon = next(
                    actor
                    for actor in runtime.fight.actors.values()
                    if getattr(actor, "native_summon_source", {}).get("ref") == profile
                )
                row["beacon"] = summon_summary(runtime.fight, beacon)
                if not any(
                    state.reference == initial_state
                    for state in beacon.state_ledger.entries
                ):
                    raise ValueError("Original beacon initial state absent")
                try:
                    legal(arrow, beacon.position)
                except ValueError:
                    row["before_arrow_turns"] = advance_owner(force=True)
                    legal(arrow, beacon.position)
                reaction = cast(arrow, beacon.position)
                if reaction["status"] != "committed":
                    raise ValueError("Actual owner arrow failed")
                row["secondary_enemy_hp_delta"] = (
                    reaction["enemy_after"]["hp"] - reaction["enemy_before"]["hp"]
                )
                row["enemy_damage_observed"] = row["secondary_enemy_hp_delta"] < 0
                # Cleanup is a legal owned cast, not direct record deletion.
                try:
                    legal(6349, beacon.position)
                except ValueError:
                    row["before_cleanup_turns"] = advance_owner(force=True)
                    legal(6349, beacon.position)
                cleanup = cast(6349, beacon.position)
                row["cleanup_verified"] = cleanup["status"] == "committed" and (
                    beacon.id not in runtime.fight.actors
                    or runtime.fight.actors[beacon.id].hp <= 0
                )
                row["secondary_reaction_verified"] = False
                # A post-cleanup legal cast at the original cell distinguishes
                # beacon-dependent damage from ordinary arrow area damage.
                if row["cleanup_verified"]:
                    try:
                        legal(arrow, selected)
                    except ValueError:
                        row["before_control_turns"] = advance_owner(force=True)
                        legal(arrow, selected)
                    control = cast(arrow, selected)
                    if control["status"] != "committed":
                        raise ValueError("Actual post-cleanup control arrow failed")
                    row["post_cleanup_enemy_hp_delta"] = (
                        control["enemy_after"]["hp"] - control["enemy_before"]["hp"]
                    )
                    row["secondary_reaction_verified"] = (
                        row["enemy_damage_observed"]
                        and row["post_cleanup_enemy_hp_delta"] == 0
                    )
                row["old_cell_reusable"] = False
                if row["cleanup_verified"]:

                    def reuse_checkpoint():
                        actual = runtime.fight
                        return dict(
                            caster=actor_summary(actual.actors[7]),
                            summons=[
                                dict(
                                    summon_summary(actual, actor),
                                    characteristic_maps=observed_plain(
                                        {
                                            name: getattr(actor, name, None)
                                            for name in (
                                                "effect_stats",
                                                "effect_minima",
                                                "effect_maxima",
                                                "effect_base_minima",
                                                "effect_base_maxima",
                                                "effect_percentages",
                                                "effect_frozen",
                                            )
                                        }
                                    ),
                                )
                                for actor in actual.actors.values()
                                if getattr(actor, "native_summon_source", None)
                            ],
                            fight_records=observed_plain(
                                {
                                    name: getattr(actual, name, None)
                                    for name in (
                                        "native_qi_slots",
                                        "native_qi_touched_cells",
                                        "native_qi_byte_topology",
                                        "native_global_pv_collections",
                                        "native_summon_registrations",
                                        "native_summon_retirements",
                                        "native_retained_records",
                                    )
                                }
                            ),
                            lifecycle_events=observed_plain(
                                [
                                    event
                                    for event in actual.events
                                    if event.get("kind")
                                    in ("death", "summon_out_of_play")
                                ]
                            ),
                        )

                    row["reuse_preflights"] = []

                    def reuse_legal():
                        attempt = dict(
                            spell=beacon_spell,
                            cell=list(selected),
                            before=reuse_checkpoint(),
                        )
                        row["reuse_preflights"].append(attempt)
                        try:
                            plan = legal(beacon_spell, selected)
                            attempt.update(
                                status="accepted",
                                diagnostic=observed_plain(
                                    plan.get("native_casting_diagnostic")
                                ),
                            )
                            return plan
                        except Exception as error:
                            attempt.update(status="rejected", **casting_error(error))
                            raise

                    try:
                        reuse_legal()
                    except ValueError:
                        row["before_reuse_turns"] = advance_owner(force=True)
                        reuse_legal()
                    reused = cast(beacon_spell, selected)
                    row["old_cell_reusable"] = reused["status"] == "committed" and any(
                        actor.hp > 0
                        and actor.position == tuple(selected)
                        and getattr(actor, "native_summon_source", {}).get("ref")
                        == profile
                        for actor in runtime.fight.actors.values()
                    )
                row["status"] = (
                    "verified"
                    if row["secondary_reaction_verified"]
                    and row["cleanup_verified"]
                    and row["old_cell_reusable"]
                    else "reaction_or_cleanup_missing"
                )
            except Exception as error:
                row.update(status="rejected", **casting_error(error))
    output.write_text(
        json.dumps(
            dict(
                scope="M3 production Ready/legal owned casts; no client/service execution",
                rows=rows,
                source_hashes=hashes,
                sources_stable=hashes == audit.init.source_hashes(),
            ),
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            dict(
                output=str(output),
                statuses={
                    status: sum(r["status"] == status for r in rows)
                    for status in sorted({r["status"] for r in rows})
                },
                reactions_verified=sum(
                    row.get("secondary_reaction_verified") is True for row in rows
                ),
                cleanup_verified=sum(
                    row.get("cleanup_verified") is True for row in rows
                ),
                cells_reusable=sum(
                    row.get("old_cell_reusable") is True for row in rows
                ),
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--level", type=int, default=20)
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument(
        "--critical",
        action="store_true",
        help="Use the actual critical branch for the later arrow; beacon creation remains normal.",
    )
    args = parser.parse_args()
    run(args.output, args.level, args.matrix, impact_critical=args.critical)
