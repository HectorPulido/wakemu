"""Owned six-player Rushu counterplay, healing and native phase-one recipients."""
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
from random import Random
import struct
import time
import traceback
from unittest.mock import patch

from postgres_case import PostgresCase


RUSHU_HOLD_ACTUAL_CHECKPOINT = False
RUSHU_ACTUAL_CHECKPOINT = None
RUSHU_LOADED_IMPLEMENTATION_BINDER = None


def release_actual_checkpoint():
    global RUSHU_ACTUAL_CHECKPOINT
    checkpoint, RUSHU_ACTUAL_CHECKPOINT = RUSHU_ACTUAL_CHECKPOINT, None
    if checkpoint is not None:
        for function, args, kwargs in reversed(checkpoint["cleanups"]):
            function(*args, **kwargs)
        checkpoint["cleanups"] = []


def verify_actual_checkpoint():
    checkpoint = RUSHU_ACTUAL_CHECKPOINT
    if checkpoint is None:
        raise AssertionError("Missing retained Rushu encounter")
    return checkpoint["loaded_implementation_verifier"]()


class RushuNativePartyPhaseOneTests(PostgresCase):
    def test_normal_party_heals_and_rotates_native_nearest_recipient(self):
        self._run()

    def test_original_seed_program_initializes_qq_and_real_ap_pickup(self):
        self._run(seed_probe=True)

    def diagnose_native_party_admission(self):
        self._run(admission_only=True)

    def _run(self, *, admission_only=False, seed_probe=False):
        global RUSHU_ACTUAL_CHECKPOINT
        from native_paid_party_fixture import (
            NativeGear,
            NativePartyBuild,
            native_paid_party_fixture,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_damage_handler import NativeDamageHandler
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_event_replay import NativeEventReplay
        from wakfu_server.combat_healing_handler import NativeHealingHandler
        from wakfu_server.combat_encounter_roles import assigned_roles
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_orientation import apply as apply_orientation
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_rushu_scene_layout import reconstructed_scene
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from tools.combat_audit_turns import advance_actual_turn

        root = Path(__file__).resolve().parents[2]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = (
            root
            / f".runtime/ultimate-scenes-20261021/rushu-native-party-phase1-{stamp}.json"
        )
        journal = output.with_suffix(".boundaries.jsonl")
        facts = dict(
            status="pending",
            boundaries=[],
            casts=[],
            movements=[],
            healing=[],
            damage=[],
            native_vitality_changes=[],
            native_events=[],
            retirement_callbacks=[],
            phase_resource_changes=[],
        )
        started = time.monotonic()
        scene = reconstructed_scene(
            json.loads(
                (
                    Path(__file__).parent
                    / "fixtures/ultimate_encounter_scene_recipes.json"
                ).read_text()
            )["maps"]["1332"]
        )
        scene.update(reference=5306, level=230)
        references = (
            (20722, 3),
            (20723, 5),
            (20724, 13),
            (20725, 0),
            (20726, 12),
            (20727, 4),
            (20728, 7),
            (20729, 15),
            (20730, 8),
        )
        tank_gear = tuple(
            NativeGear(ref, slot, damage_mask=26) for ref, slot in references
        )
        # Water is chosen by the normal item-selection API. The ordinary Uhu
        # staff has fixed ranged mastery and occupies the offhand natively.
        healer_gear = tuple(
            NativeGear(29635, slot)
            if slot == 15
            else NativeGear(ref, slot, damage_mask=14)
            for ref, slot in references
        )
        tank_active = (
            6968,
            6969,
            6971,
            6972,
            6977,
            6978,
            6979,
            6980,
            6982,
            6983,
            6984,
            6986,
        )
        tank_passive = (6991, 6995, 6997, 7004, 7005)
        tank = NativePartyBuild(
            breed=1,
            level=230,
            active_spells=tank_active,
            passive_spells=(*tank_passive, 5144),
            aptitudes=((1, 48), (16, 10), (35, 1), (2, 1), (3, 1), (4, 1), (5, 1)),
            gear=tank_gear,
        )
        bulk_tank = NativePartyBuild(
            breed=1,
            level=230,
            active_spells=tank_active,
            passive_spells=(*tank_passive, 5145),
            aptitudes=tank.aptitudes,
            gear=tank_gear,
        )
        healer = NativePartyBuild(
            breed=7,
            level=230,
            active_spells=(
                625,
                627,
                638,
                779,
                780,
                781,
                782,
                1533,
                1534,
                1535,
                1538,
                7985,
            ),
            passive_spells=(1415, 1536, 5146, 7991, 7987, 4957),
            aptitudes=(
                (1, 48),
                (16, 10),
                (30, 40),
                (23, 18),
                (14, 58),
                (2, 1),
                (3, 1),
                (38, 1),
                (4, 1),
                (5, 1),
            ),
            gear=healer_gear,
        )
        positions = (
            (-39, 7, -4),
            (-39, 4, -4),
            (-39, 10, -4),
            (-38, 12, -4),
            (-37, 4, -4),
            (-37, 10, -4),
        )
        if seed_probe:
            positions = (positions[0], positions[2], positions[1], *positions[3:])
        rear = ((-38, 5, -4), (-40, 10, -4), (-39, 10, -4), (-40, 4, -4))
        healer_homes = ((-37, 5, -4), (-37, 9, -4))
        heal_hub = (-38, 7, -4) if seed_probe else (-37, 8, -4)
        cycle_end = (
            (-39, 4, -4),
            (-41, 12, -4),
            (-37, 7, -4),
            (-39, 11, -4),
            (-36, 9, -4),
            (-39, 8, -4),
        )
        from wakfu_server import combat_rushu_encounter_setup as rushu_setup

        original_setup = rushu_setup.install_rushu_encounter_setup

        def observe_setup(dispatcher, **kwargs):
            applied = original_setup(dispatcher, **kwargs)
            if applied:
                current = dispatcher.native_retention.fight
                rows = [
                    row
                    for row in current.native_effect_areas.values()
                    if row["reference"] in (1650, *range(1652, 1667))
                ]
                facts["original_seed_program_areas"] = [
                    dict(
                        reference=row["reference"],
                        cell=row["cell"],
                        states=[
                            (entry.reference, entry.level)
                            for entry in row["state_ledger"].entries
                        ],
                    )
                    for row in rows
                ]
                self.assertEqual(len(rows), 16)
                self.assertTrue(
                    all(
                        (7001, 1) in record["states"]
                        for record in facts["original_seed_program_areas"]
                    )
                )
                self.assertFalse(
                    any(
                        entry.reference == 7001
                        for actor in current.actors.values()
                        for entry in actor.state_ledger.entries
                    )
                )
            return applied

        original_damage, original_heal = (
            NativeDamageHandler.__call__,
            NativeHealingHandler.__call__,
        )
        original_execute = EffectDispatcher.execute
        original_event = NativeEventReplay.__call__

        def observe_event(replay, event, **kwargs):
            result = original_event(replay, event, **kwargs)
            if set(event.event_ids).intersection((1002, 1005, 1037, 2172, 2173)):
                facts["native_events"].append(
                    dict(
                        event_ids=event.event_ids,
                        manager=event.manager_actor_id,
                        table=replay.retention.fight.native_table_turn,
                        turn=replay.retention.fight.turn_id,
                    )
                )
            return result

        def observe_vitality(dispatcher, invocation, **kwargs):
            if seed_probe and invocation.reference in (318814, 318816, 318817):
                from wakfu_server.combat_state_managers import registered_area_pv

                current = dispatcher.native_retention.fight
                selected = current.actors.get(invocation.caster_id)
                if selected is None:
                    selected = registered_area_pv(current, invocation.caster_id)
                ledger = None if selected is None else selected.state_ledger
                facts.setdefault("pickup_level_source", []).append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        level=invocation.level,
                        context=invocation.native_context_hex,
                        caster_states=[]
                        if ledger is None
                        else [
                            (entry.reference, entry.level) for entry in ledger.entries
                        ],
                        ap_glyphs=[
                            dict(
                                uid=uid,
                                owner=row["owner_id"],
                                cell=row["cell"],
                                states=[
                                    (entry.reference, entry.level)
                                    for entry in row["state_ledger"].entries
                                ],
                            )
                            for uid, row in current.native_effect_areas.items()
                            if row["reference"] == 1650
                        ],
                    )
                )
            before = {
                identity: (actor.hp, actor.max_hp)
                for identity, actor in dispatcher.native_retention.fight.actors.items()
            }
            resource_before = (
                {
                    identity: dict(
                        mp=actor.mp,
                        current=actor.effect_stats.get(3),
                        maximum=actor.effect_maxima.get(3),
                    )
                    for identity, actor in dispatcher.native_retention.fight.actors.items()
                }
                if invocation.reference == 319412
                else None
            )
            result = original_execute(dispatcher, invocation, **kwargs)
            current = dispatcher.native_retention.fight
            if seed_probe and invocation.reference in (324631, 318818):
                facts.setdefault("native_pickup_removal", []).append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        result=result,
                        container=invocation.native_retained_container,
                        ground_uids=list(current.native_effect_areas),
                    )
                )
            if seed_probe and invocation.reference in (318817, 318947):
                facts.setdefault("seed_operand_caster_contract", []).append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        level=invocation.level,
                        result=result,
                        caster_is_registered_actor=invocation.caster_id
                        in current.actors,
                        table=current.native_table_turn,
                    )
                )
            if resource_before is not None:
                facts["phase_resource_changes"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        result=result,
                        table=current.native_table_turn,
                        before=resource_before,
                        after={
                            identity: dict(
                                mp=actor.mp,
                                current=actor.effect_stats.get(3),
                                maximum=actor.effect_maxima.get(3),
                            )
                            for identity, actor in current.actors.items()
                        },
                    )
                )
            if invocation.reference in (
                324322,
                324346,
                324351,
                324481,
                324482,
                324483,
                324809,
                324585,
                324594,
                324595,
                324601,
            ):
                facts["retirement_callbacks"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        level=invocation.level,
                        table=current.native_table_turn,
                        result=result,
                    )
                )
            changes = {
                identity: (
                    values,
                    (current.actors[identity].hp, current.actors[identity].max_hp),
                )
                for identity, values in before.items()
                if identity in current.actors
                and values
                != (current.actors[identity].hp, current.actors[identity].max_hp)
            }
            if changes:
                facts["native_vitality_changes"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        changes=changes,
                        result=result,
                    )
                )
            return result

        def observe_damage(handler, definition, values, invocation):
            actor = handler.fight.actors.get(invocation.target_id)
            before = None if actor is None else actor.hp
            before_scene = {
                identity: dict(
                    position=selected.position,
                    hp=selected.hp,
                    max_hp=selected.max_hp,
                    stats={
                        stat: selected.effect_stats.get(stat)
                        for stat in (
                            20,
                            21,
                            22,
                            23,
                            24,
                            27,
                            28,
                            29,
                            30,
                            31,
                            49,
                            97,
                            103,
                            104,
                            105,
                            106,
                        )
                    },
                    states=[
                        (entry.reference, entry.level)
                        for entry in selected.state_ledger.entries
                    ],
                )
                for identity, selected in handler.fight.actors.items()
                if selected.controlled or identity == -200
            }
            result = original_damage(handler, definition, values, invocation)
            facts["damage"].append(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    cell=invocation.cell,
                    before=before,
                    after=None if actor is None else actor.hp,
                    result=result,
                    table=handler.fight.native_table_turn,
                    before_scene=before_scene,
                )
            )
            return result

        def observe_heal(handler, definition, values, invocation):
            actor = handler.fight.actors.get(invocation.target_id)
            before = None if actor is None else actor.hp
            result = original_heal(handler, definition, values, invocation)
            facts["healing"].append(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    before=before,
                    after=None if actor is None else actor.hp,
                    result=result,
                    table=handler.fight.native_table_turn,
                )
            )
            return result

        rng = Random(0)
        admission_binding = None
        if RUSHU_HOLD_ACTUAL_CHECKPOINT:
            self.assertIsNone(RUSHU_ACTUAL_CHECKPOINT)
            self.assertTrue(callable(RUSHU_LOADED_IMPLEMENTATION_BINDER))
            admission_binding = RUSHU_LOADED_IMPLEMENTATION_BINDER(
                store=self.store, rng=rng, runtime_class=RuntimeMessages
            )
        try:
            with original_bootstrap_publication(), patch.object(
                rushu_setup, "install_rushu_encounter_setup", observe_setup
            ), patch.object(
                EffectDispatcher, "execute", observe_vitality
            ), patch.object(
                NativeDamageHandler, "__call__", observe_damage
            ), patch.object(
                NativeEventReplay, "__call__", observe_event
            ), patch.object(
                NativeHealingHandler, "__call__", observe_heal
            ):
                (
                    fight,
                    characters,
                    monsters,
                    decks,
                    resources,
                    generations,
                    premise,
                ) = native_paid_party_fixture(
                    self.store,
                    scene,
                    (tank, tank, bulk_tank, bulk_tank, healer, healer),
                    positions,
                    name_prefix="rushu-party",
                    encounter_layout=scene,
                    production_scene=True,
                    placement_directions=(5,) * 6,
                )
                identities = tuple(characters)
                tanks, healers = identities[:4], identities[4:]
                self.assertEqual(
                    (assigned_roles(fight).player_team, assigned_roles(fight).npc_team),
                    (1, 0),
                )
                self.assertEqual(
                    len({a.owner_id for a in fight.actors.values() if a.controlled}), 6
                )
                facts.update(
                    premise=premise,
                    identities=identities,
                    complete_builds=[
                        dict(
                            breed=build.breed,
                            level=build.level,
                            active_spells=build.active_spells,
                            passive_spells=build.passive_spells,
                        )
                        for build in (tank, tank, bulk_tank, bulk_tank, healer, healer)
                    ],
                    before_first1001={
                        identity: dict(
                            hp=fight.actors[identity].hp,
                            maximum_hp=fight.actors[identity].max_hp,
                            position=fight.actors[identity].position,
                            stats=dict(fight.actors[identity].effect_stats),
                            maxima=dict(fight.actors[identity].effect_maxima),
                            states=[
                                (entry.reference, entry.level)
                                for entry in fight.actors[identity].state_ledger.entries
                            ],
                        )
                        for identity in identities
                    },
                )
                for identity, character in characters.items():
                    actor = fight.actors[identity]
                    self.assertEqual(character["hp"], character["max_hp"])
                    self.assertGreater(actor.hp, 0)
                    self.assertLessEqual(actor.hp, actor.max_hp)
                    if (actor.hp, actor.max_hp) != (
                        character["hp"],
                        character["max_hp"],
                    ):
                        self.assertTrue(
                            any(
                                identity in row["changes"]
                                and row["changes"][identity][0][1]
                                == character["max_hp"]
                                for row in facts["native_vitality_changes"]
                            ),
                            "Post-Ready vitality differs without an observed native producer",
                        )
                if admission_only:
                    facts.update(
                        status="canonical_six_owner_admission_before_first1001",
                        boss_stats=dict(fight.actors[-200].effect_stats),
                    )
                    return
                common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
                first, first_deck = characters[identities[0]], decks[identities[0]]

                def serialize(actor, current):
                    if getattr(actor, "native_summon_source", None) is not None:
                        return registered_summon_stats(actor, current, 1332)
                    kwargs = dict(
                        wp_current=actor.effect_stats[4],
                        wp_maximum=actor.effect_maxima[4],
                        fight=current,
                    )
                    return (
                        actual_actor_stats(
                            characters[actor.id], actor, current.id, **kwargs
                        )
                        if actor.id in characters
                        else actual_monster_actor_stats(
                            monsters[actor.id], actor, current.id, **kwargs
                        )
                    )

                runtime = RuntimeMessages(
                    fight,
                    runtime_stats_serializer=serialize,
                    turn_start_provider=lambda current, **kwargs: prepare_server_turn_start(
                        first,
                        monsters,
                        current,
                        first_deck,
                        native_events=True,
                        area_callbacks=True,
                        **common,
                        **kwargs,
                    ),
                    turn_end_provider=lambda current, **kwargs: prepare_server_turn_end(
                        first, monsters, current, first_deck, **common, **kwargs
                    ),
                    expiration_runtime_factory=lambda *, action_id: server_runtime(
                        first,
                        monsters,
                        first_deck,
                        action_id=action_id,
                        critical=False,
                        **common,
                    )[0],
                )

                if RUSHU_HOLD_ACTUAL_CHECKPOINT:
                    self.rushu_live = dict(
                        runtime=runtime,
                        store=self.store,
                        rng=rng,
                        characters=characters,
                        monsters=monsters,
                        decks=decks,
                        identities=identities,
                        resources=resources,
                        generations=generations,
                        receipt=facts,
                        receipt_path=str(output),
                        fixture=self,
                        runtime_class=RuntimeMessages,
                        serialize=serialize,
                        common=common,
                        first=first,
                        first_deck=first_deck,
                    )
                    admission_binding(self.rushu_live)

                def visible(origin, target, current):
                    return authoritative_visible(
                        1332,
                        origin,
                        target,
                        current,
                        blocking_footprints={
                            a.id: footprint(a.position, a.physical_radius)
                            for a in current.actors.values()
                            if a.hp > 0
                        },
                    )

                def cast(identity, spell, target):
                    current, actor = runtime.fight, runtime.fight.actors[identity]
                    uid = (
                        spell
                        if spell in granted_spells(current, identity)
                        else (identity << 32) | spell
                    )
                    facts["pending_cast"] = dict(
                        actor=identity,
                        spell=spell,
                        target=target,
                        source=actor.position,
                        target_cell=current.actors[target].position,
                        ap=actor.ap,
                        wp=actor.effect_stats[4],
                    )
                    before_health = {
                        selected: current.actors[selected].hp for selected in identities
                    }
                    before_resources = dict(
                        ap=actor.ap, mp=actor.mp, wp=actor.effect_stats[4]
                    )
                    transaction = prepare_server_spell(
                        struct.pack(
                            ">qqiih", identity, uid, *current.actors[target].position
                        ),
                        characters[identity],
                        monsters,
                        current,
                        actor.owner_id,
                        decks[identity],
                        action_id=runtime.action_id + 1,
                        line_of_sight=visible,
                        critical=False,
                        **common,
                    )
                    commit_spell_transaction(
                        runtime, transaction, stats_serializer=serialize
                    )
                    facts["casts"].append(
                        dict(
                            actor=identity,
                            spell=spell,
                            target=target,
                            table=runtime.fight.native_table_turn,
                            costs=transaction.plan["costs"],
                            before_resources=before_resources,
                            after_resources=dict(
                                ap=runtime.fight.actors[identity].ap,
                                mp=runtime.fight.actors[identity].mp,
                                wp=runtime.fight.actors[identity].effect_stats[4],
                            ),
                            consumed_healing={
                                selected: runtime.fight.actors[selected].hp - hp
                                for selected, hp in before_health.items()
                                if runtime.fight.actors[selected].hp > hp
                            },
                        )
                    )
                    facts["pending_cast"] = None

                def movement_path(identity, target):
                    current, actor = runtime.fight, runtime.fight.actors[identity]
                    if actor.position == target:
                        return []
                    occupied = {
                        point
                        for other in current.actors.values()
                        if other.hp > 0 and other.id != identity
                        for point in footprint(other.position, other.physical_radius)
                    }
                    forbidden = (
                        {
                            tuple(row["cell"])[:2]
                            for row in current.native_effect_areas.values()
                            if row["reference"] in (1650, *range(1652, 1667))
                            and tuple(row["cell"]) != target
                        }
                        if seed_probe
                        else set()
                    )
                    previous, pending, adjacency = (
                        {actor.position: None},
                        deque((actor.position,)),
                        {},
                    )
                    for start, end in sorted(current.edges):
                        adjacency.setdefault(start, []).append(end)
                    while pending and target not in previous:
                        start = pending.popleft()
                        for end in adjacency.get(start, ()):
                            if (
                                end not in previous
                                and end[:2] not in occupied | forbidden
                            ):
                                previous[end] = start
                                pending.append(end)
                    self.assertIn(target, previous)
                    path, cursor = [], target
                    while previous[cursor] is not None:
                        path.append(cursor)
                        cursor = previous[cursor]
                    path.reverse()
                    return path

                def move(identity, target):
                    current, actor = runtime.fight, runtime.fight.actors[identity]
                    path = movement_path(identity, target)
                    if not path:
                        return
                    self.assertLessEqual(len(path), actor.mp)
                    old_mp = actor.mp
                    apply_client(
                        runtime,
                        actor.owner_id,
                        struct.pack(">q", identity)
                        + b"".join(struct.pack(">iih", *cell) for cell in path),
                        lambda selected: serialize(selected, runtime.fight),
                        runtime_stats_serializer=serialize,
                        area_provider=lambda candidate, **kwargs: prepare_area_movement(
                            characters[identity],
                            monsters,
                            candidate,
                            decks[identity],
                            **common,
                            **kwargs,
                        ),
                    )
                    self.assertEqual(
                        old_mp - runtime.fight.actors[identity].mp, len(path)
                    )
                    facts["movements"].append(
                        dict(actor=identity, path=path, cost_mp=len(path))
                    )

                runtime.turn_started()
                for boundary in range(10 if seed_probe else 36):
                    while runtime.awaiting_ack is not None:
                        runtime.acknowledge_turn(
                            struct.pack(">i", runtime.awaiting_ack)
                        )
                    current = runtime.fight
                    snapshot = dict(
                        table=current.native_table_turn,
                        turn=current.turn_id,
                        elapsed_seconds=round(time.monotonic() - started, 3),
                        phase=current.phase,
                        current=None if current.current is None else current.current.id,
                        ground_vestiges=[
                            dict(uid=uid, reference=row["reference"], cell=row["cell"])
                            for uid, row in current.native_effect_areas.items()
                            if row["reference"] in (1650, *range(1652, 1667))
                        ],
                        boss=dict(
                            position=current.actors[-200].position,
                            hp=current.actors[-200].hp,
                            stats=dict(current.actors[-200].effect_stats),
                            states=[
                                (entry.reference, entry.level)
                                for entry in current.actors[-200].state_ledger.entries
                            ],
                        ),
                        players={
                            identity: dict(
                                hp=current.actors[identity].hp,
                                ap=current.actors[identity].ap,
                                mp=current.actors[identity].mp,
                                wp=current.actors[identity].effect_stats[4],
                                position=current.actors[identity].position,
                                states=[
                                    (s.reference, s.level)
                                    for s in current.actors[
                                        identity
                                    ].state_ledger.entries
                                ],
                            )
                            for identity in identities
                        },
                    )
                    if (
                        not seed_probe
                        and current.current is not None
                        and current.current.id == -200
                    ):
                        from itertools import combinations

                        distances = [
                            abs(left.position[0] - right.position[0])
                            + abs(left.position[1] - right.position[1])
                            for left, right in combinations(
                                (current.actors[owner] for owner in identities), 2
                            )
                        ]
                        snapshot["minimum_player_pair_distance"] = min(distances)
                        boss_actor = current.actors[-200]
                        explosion_grade = next(
                            entry.level
                            for entry in boss_actor.state_ledger.entries
                            if entry.reference == 7024
                        )
                        snapshot["explosion_grade"] = explosion_grade
                        snapshot["minimum_player_boss_distance"] = min(
                            abs(
                                current.actors[owner].position[0]
                                - boss_actor.position[0]
                            )
                            + abs(
                                current.actors[owner].position[1]
                                - boss_actor.position[1]
                            )
                            for owner in identities
                        )
                        snapshot["minimum_player_ground_distance"] = min(
                            abs(current.actors[owner].position[0] - area["cell"][0])
                            + abs(current.actors[owner].position[1] - area["cell"][1])
                            for owner in identities
                            for area in snapshot["ground_vestiges"]
                        )
                    facts["boundaries"].append(snapshot)
                    journal.parent.mkdir(parents=True, exist_ok=True)
                    with journal.open("a") as stream:
                        stream.write(json.dumps(snapshot) + "\n")
                    if (
                        "minimum_player_pair_distance" in snapshot
                        and current.native_table_turn >= 2
                    ):
                        self.assertGreaterEqual(
                            snapshot["minimum_player_pair_distance"],
                            3,
                            "Saccage ring1–2 requires separated player centres",
                        )
                        self.assertGreater(
                            snapshot["minimum_player_boss_distance"],
                            5 + snapshot["explosion_grade"],
                            "Party entered the active Explosion ring",
                        )
                        if current.native_table_turn == 5:
                            self.assertGreaterEqual(
                                snapshot["minimum_player_ground_distance"],
                                4,
                                "Party entered a phase5 ground-vestige ring",
                            )
                    self.assertEqual(current.phase, "active")
                    self.assertTrue(
                        all(current.actors[identity].hp > 0 for identity in identities)
                    )
                    if (
                        current.native_table_turn >= 5
                        and current.current.id in identities
                    ):
                        break
                    identity = current.current.id
                    if seed_probe and facts.get("pickup") and identity == tanks[1]:
                        actor = current.actors[identity]
                        from wakfu_server.combat_global_pv_collections import (
                            global_area_order,
                        )

                        self.assertNotIn(
                            facts["pickup"]["area_uid"], current.native_effect_areas
                        )
                        self.assertNotIn(
                            facts["pickup"]["area_uid"], global_area_order(current)
                        )
                        self.assertFalse(
                            any(
                                entry.reference == 6998
                                for entry in current.actors[-200].state_ledger.entries
                            )
                        )
                        actual_grade = next(
                            entry.level
                            for entry in actor.state_ledger.entries
                            if entry.reference == 6998
                        )
                        self.assertEqual(actual_grade, 2)
                        self.assertEqual(
                            actor.effect_maxima[2],
                            facts["pickup"]["maximum_before"] + 2,
                        )
                        self.assertTrue(
                            any(
                                2173 in row["event_ids"]
                                for row in facts["native_events"]
                            )
                        )
                        authority = facts.get("seed_operand_caster_contract", ())
                        # The original844's computed SP1 must reach304 without
                        # replacing the owner caster with its Qq query operand.
                        applications = [
                            row
                            for row in authority
                            if row["reference"] == 318817 and row["target"] == identity
                        ]
                        self.assertTrue(applications, authority)
                        self.assertTrue(
                            all(
                                row["level"] == 1
                                and row["caster"] == -200
                                and row["caster_is_registered_actor"]
                                for row in applications
                            ),
                            applications,
                        )
                        # The later native held-state branch has no actor
                        # rebind. Its426 must therefore retain the real boss.
                        weapons = [
                            row for row in authority if row["reference"] == 318947
                        ]
                        self.assertTrue(weapons, authority)
                        self.assertTrue(
                            all(
                                row["caster"] == -200
                                and row["target"] == -200
                                and row["caster_is_registered_actor"]
                                for row in weapons
                            ),
                            weapons,
                        )
                        facts.update(
                            status="original_seed_qq7001_paid_ap_pickup_and_native_growth",
                            growth=dict(
                                table=current.native_table_turn,
                                actor=identity,
                                grade=actual_grade,
                                ap=actor.ap,
                                maximum=actor.effect_maxima[2],
                            ),
                            seed_manifest=current.native_encounter_area_seed_policy,
                        )
                        return
                    if seed_probe and identity == tanks[1]:
                        ap_area = next(
                            row
                            for row in current.native_effect_areas.values()
                            if row["reference"] == 1650
                        )
                        self.assertTrue(
                            any(
                                entry.reference == 7001 and entry.level == 1
                                for entry in ap_area["state_ledger"].entries
                            )
                        )
                        before_ap = current.actors[identity].ap
                        before_max = current.actors[identity].effect_maxima[2]
                        move(identity, tuple(ap_area["cell"]))
                        actor = runtime.fight.actors[identity]
                        actual_grade = next(
                            entry.level
                            for entry in actor.state_ledger.entries
                            if entry.reference == 6998
                        )
                        self.assertEqual(actual_grade, 1)
                        self.assertEqual(actor.ap - before_ap, 1)
                        self.assertEqual(actor.effect_maxima[2] - before_max, 1)
                        from wakfu_server.combat_global_pv_collections import (
                            global_area_order,
                        )

                        facts["pickup_removal"] = dict(
                            uid=ap_area["uid"],
                            absent_from_registered_areas=ap_area["uid"]
                            not in runtime.fight.native_effect_areas,
                            absent_from_global_area_order=ap_area["uid"]
                            not in global_area_order(runtime.fight),
                        )
                        self.assertTrue(
                            facts["pickup_removal"]["absent_from_registered_areas"]
                        )
                        self.assertTrue(
                            facts["pickup_removal"]["absent_from_global_area_order"]
                        )
                        facts["pickup"] = dict(
                            actor=identity,
                            area_uid=ap_area["uid"],
                            grade=actual_grade,
                            ap_before=before_ap,
                            ap_after=actor.ap,
                            maximum_before=before_max,
                            maximum_after=actor.effect_maxima[2],
                            position=actor.position,
                        )
                        # Ordinary owned defensive actions bridge the next boss
                        # start; its actual end publishes2173 and grows6998.
                        cast(identity, 7009, identity)
                        cast(identity, 6982, identity)
                        cast(identity, 6978, identity)
                        apply_orientation(
                            runtime, actor.owner_id, struct.pack(">qB", identity, 5)
                        )
                        advance_actual_turn(runtime)
                        continue
                    if identity in tanks:
                        index, active = (
                            tanks.index(identity),
                            current.native_table_turn - 1,
                        )
                        actor = current.actors[identity]
                        states = {s.reference for s in actor.state_ledger.entries}
                        if 6364 not in states:
                            cast(identity, 7009, identity)
                        if 6334 not in states and 6357 not in states:
                            cast(identity, 6978, identity)
                        if not seed_probe and current.native_table_turn >= 2:
                            if current.native_table_turn == 2 and index == 1:
                                cast(identity, 6982, identity)
                            move(identity, cycle_end[index])
                        elif (
                            not seed_probe
                            and current.native_table_turn == 1
                            and index == 1
                        ):
                            # Four paid steps now permit the separated six-step
                            # destination next turn without a Saccage neighbour.
                            move(identity, (-41, 6, -4))
                        elif current.native_table_turn == 4:
                            # The original prior-hit marker can exclude nearer
                            # tanks. Finish separated and outside ground circles.
                            move(identity, cycle_end[index])
                        elif index == active:
                            if current.native_table_turn < 3:
                                cast(identity, 6982, identity)
                            occupied = {
                                a.position
                                for a in runtime.fight.actors.values()
                                if a.id != identity and a.hp > 0
                            }
                            # Native feq may order the incoming tank before the
                            # previous tank. An adjacent free front slot keeps
                            # the rotation legal without altering that order.
                            front = (
                                positions[0]
                                if positions[0] not in occupied
                                else (-40, 7, -4)
                            )
                            move(identity, front)
                        elif index < active:
                            move(identity, rear[index])
                        elif (
                            seed_probe and index == 3 and current.native_table_turn == 1
                        ):
                            # One paid step now leaves a six-MP route into the
                            # free front slot when native order places tank4 first.
                            move(identity, (-38, 11, -4))
                        if current.native_table_turn == 3 and index in (2, 3):
                            # Native allied Inmune protects eligible healers for
                            # NPC4; each unused caster pays its ordinary cooldown.
                            cast(identity, 6982, healers[index - 2])
                        actor = runtime.fight.actors[identity]
                        apply_orientation(
                            runtime, actor.owner_id, struct.pack(">qB", identity, 5)
                        )
                    elif identity in healers:
                        home = (
                            cycle_end[identities.index(identity)]
                            if current.native_table_turn >= (4 if seed_probe else 2)
                            else healer_homes[healers.index(identity)]
                        )
                        move(identity, home)
                        actor = runtime.fight.actors[identity]
                        apply_orientation(
                            runtime, actor.owner_id, struct.pack(">qB", identity, 5)
                        )
                        used = {}
                        advanced = False
                        for _ in range(5):
                            current, actor = (
                                runtime.fight,
                                runtime.fight.actors[identity],
                            )
                            injured = sorted(
                                (
                                    current.actors[other]
                                    for other in identities
                                    if current.actors[other].hp
                                    < current.actors[other].max_hp
                                ),
                                key=lambda selected: (
                                    selected.hp / selected.max_hp,
                                    selected.id,
                                ),
                            )
                            choices = []
                            for target in injured:
                                distance = abs(
                                    actor.position[0] - target.position[0]
                                ) + abs(actor.position[1] - target.position[1])
                                if target.id == identity:
                                    if actor.ap >= 3 and not used.get((780, identity)):
                                        choices.append((780, target.id))
                                    continue
                                aligned = (
                                    actor.position[0] == target.position[0]
                                    or actor.position[1] == target.position[1]
                                )
                                # These are native range/usage prechecks, not a
                                # replacement for prepare_server_spell validation.
                                if (
                                    aligned
                                    and 1 <= distance <= 6
                                    and actor.ap >= 5
                                    and actor.effect_stats[4] >= 1
                                    and not used.get((625, identity))
                                ):
                                    choices.append((625, target.id))
                                elif (
                                    distance <= 5
                                    and actor.ap >= 3
                                    and used.get((779, target.id), 0) < 2
                                    and used.get((779, identity), 0) < 3
                                    and visible(
                                        actor.position, target.position, current
                                    )
                                ):
                                    choices.append((779, target.id))
                                elif (
                                    1 <= distance <= 7
                                    and actor.ap >= 2
                                    and used.get((1533, target.id), 0) < 3
                                    and visible(
                                        actor.position, target.position, current
                                    )
                                ):
                                    choices.append((1533, target.id))
                            if not choices:
                                # Advance only when the return trip is affordable;
                                # healers finish farther from the boss than tanks.
                                if (
                                    injured
                                    and actor.ap >= 2
                                    and not advanced
                                    and actor.mp
                                    >= 2 * len(movement_path(identity, heal_hub))
                                ):
                                    move(identity, heal_hub)
                                    advanced = True
                                    continue
                                break
                            spell, target = choices[0]
                            cast(identity, spell, target)
                            used[(spell, target)] = used.get((spell, target), 0) + 1
                            if spell in (625, 779) and target != identity:
                                used[(spell, identity)] = (
                                    used.get((spell, identity), 0) + 1
                                )
                        if advanced:
                            move(identity, home)
                        actor = runtime.fight.actors[identity]
                        apply_orientation(
                            runtime, actor.owner_id, struct.pack(">qB", identity, 5)
                        )
                    advance_actual_turn(runtime)

                current = runtime.fight
                self.assertGreaterEqual(current.native_table_turn, 5)
                self.assertTrue(
                    all(current.actors[identity].hp > 0 for identity in identities)
                )
                self.assertFalse(
                    any(
                        row["reference"] == 319300 and row["target"] in identities
                        for row in facts["damage"]
                    ),
                    "Separated party still entered an original Saccage ring",
                )
                consumed = sum(
                    sum(row["consumed_healing"].values()) for row in facts["casts"]
                )
                self.assertGreater(consumed, 0)
                water_rows = [
                    row
                    for row in facts["damage"]
                    if row["reference"] == 319215 and row["table"] == 3
                ]
                water_targets = {row["target"] for row in water_rows}
                water_grades = {
                    grade
                    for row in water_rows
                    for reference, grade in row["before_scene"][-200]["states"]
                    if reference == 7013
                }
                self.assertEqual(
                    len(water_grades),
                    1,
                    "Missing actual Grêle grade at damage selection",
                )
                expected_water_targets = min(len(identities), next(iter(water_grades)))
                curse_targets = {
                    row["target"]
                    for row in facts["damage"]
                    if row["reference"] == 319303 and row["table"] == 3
                }
                self.assertEqual(
                    len(water_targets),
                    expected_water_targets,
                    "Grêle recipients must match the actual native carrier grade",
                )
                facts["grade_recipient_contract"] = dict(
                    table=3,
                    state_reference=7013,
                    grade=next(iter(water_grades)),
                    actual_targets=sorted(water_targets),
                )
                self.assertTrue(
                    curse_targets
                    and any(
                        water != curse
                        for water in water_targets
                        for curse in curse_targets
                    ),
                    "All native recipients collapsed onto one PV",
                )
                retired = {
                    entry.reference: entry.level
                    for entry in current.actors[-200].state_ledger.entries
                    if entry.reference in (7013, 7017, 7018, 7024)
                }
                self.assertEqual(set(retired), {7013, 7017, 7018, 7024})
                self.assertTrue(
                    any(1037 in row["event_ids"] for row in facts["native_events"])
                )
                self.assertTrue(
                    any(
                        row["reference"] == 324351 and row["result"]
                        for row in facts["retirement_callbacks"]
                    )
                )
                self.assertTrue(
                    all(grade == 99 for grade in retired.values()),
                    "Cycle5 did not retire the four original powers through their native program",
                )
                active_next = {
                    entry.reference: entry.level
                    for entry in current.actors[-200].state_ledger.entries
                    if entry.reference in (6998, *range(7011, 7026))
                    and entry.level <= 10
                }
                self.assertEqual(
                    len(active_next),
                    4,
                    "Cycle end did not preserve the next four native powers",
                )
                self.assertFalse(set(active_next).intersection(retired))
                self.assertTrue(
                    any(
                        entry.reference == 7092 and entry.level == 4
                        for entry in current.actors[-200].state_ledger.entries
                    )
                )
                self.assertTrue(
                    any(
                        row["reference"] == 324481 and row["result"]
                        for row in facts["retirement_callbacks"]
                    )
                )
                facts.update(
                    status="normal_party_cycle5_retired_initial_and_preserved_next_four",
                    final_table=current.native_table_turn,
                    retired_initial_powers=retired,
                    active_next_powers=active_next,
                    consumed_healing=consumed,
                    frozen_turn_end_order=current.native_turn_end_order_policy,
                )
        except Exception as error:
            facts.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(limit=24),
            )
            raise
        finally:
            # Temporary observers have unwound before attesting live services.
            if RUSHU_HOLD_ACTUAL_CHECKPOINT and hasattr(self, "rushu_live"):
                RUSHU_ACTUAL_CHECKPOINT = self.rushu_live
                RUSHU_ACTUAL_CHECKPOINT["cleanups"], self._cleanups = self._cleanups, []
                facts["retained_live_objects_and_isolated_store"] = True
                facts["loaded_implementation_attestation"] = verify_actual_checkpoint()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")
