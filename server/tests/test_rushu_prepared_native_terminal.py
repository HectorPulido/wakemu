"""Persisted native230 defense, genuine player actions and original Rushu clock."""
from datetime import datetime, timezone
from collections import deque
import json
from pathlib import Path
from random import Random
import struct
import time
import traceback
from unittest.mock import patch

from postgres_case import PostgresCase


ROOT = Path(__file__).resolve().parents[2]
SAFE_CELL = (-39, 6, -4)


class RushuPreparedNativeTerminalTests(PostgresCase):
    def diagnose_native_geared_admission(self):
        self._run(terminal=False, admission_only=True)

    def test_reconstructed_player_role_picks_up_and_releases_original_vestige(self):
        self._run(terminal=False, pickup=True)

    def test_persisted_native_230_build_survives_original_phase20_component(self):
        self._run(terminal=False)

    def test_persisted_zero_score_build_reaches_original_table21_failure(self):
        self._run(terminal=True)

    def _run(self, *, terminal, pickup=False, admission_only=False):
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
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
        )
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_orientation import apply as apply_orientation
        from wakfu_server.combat_encounter_roles import assigned_roles
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_rushu_scene_layout import reconstructed_scene
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.combat_triggered_spell import native_triggered_spell_request
        from tools.combat_audit_turns import advance_actual_turn

        scene = reconstructed_scene(
            json.loads(
                (
                    Path(__file__).parent
                    / "fixtures/ultimate_encounter_scene_recipes.json"
                ).read_text()
            )["maps"]["1332"]
        )
        scene.update(reference=5306, level=230)
        # Native budgets: intelligence58 at230; one major35 is +50 resistance.
        # Ownership, XP, sheet validation and full healthy HP are persisted
        # through the normal isolated-store APIs before Actor construction.
        build = NativePartyBuild(
            breed=1,
            level=230,
            active_spells=(6972, 6982),
            aptitudes=((1, 58), (35, 1)),
            gear=tuple(
                NativeGear(ref, slot, damage_mask=26)
                for ref, slot in (
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
            ),
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = (
            ROOT
            / f".runtime/ultimate-scenes-20261021/rushu-prepared-native-{stamp}.json"
        )
        journal = output.with_suffix(".boundaries.jsonl")
        receipt = dict(
            status="pending",
            terminal=terminal,
            pickup=pickup,
            boundaries=[],
            payments=[],
            movements=[],
            orientations=[],
            native_callbacks=[],
            damage_calculations=[],
            hp_changes=[],
        )
        started = time.monotonic()
        selected = {
            324811,
            324812,
            324817,
            324818,
            319402,
            319410,
            319413,
            325750,
            324486,
            325500,
            324489,
            319070,
            319079,
            323843,
            324567,
        }
        original_execute = EffectDispatcher.execute
        original_calculate = NativeDamageHandler._calculate

        def observe(dispatcher, invocation, **kwargs):
            before = {
                identity: actor.hp
                for identity, actor in dispatcher.native_retention.fight.actors.items()
            }
            result = original_execute(dispatcher, invocation, **kwargs)
            after = dispatcher.native_retention.fight
            changed = {
                identity: (hp, after.actors[identity].hp)
                for identity, hp in before.items()
                if identity in after.actors and after.actors[identity].hp != hp
            }
            if changed:
                receipt["hp_changes"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        changes=changed,
                        result=result,
                        table=after.native_table_turn,
                        turn=after.turn_id,
                    )
                )
            if invocation.reference in selected:
                current = dispatcher.native_retention.fight
                receipt["native_callbacks"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        result=result,
                        table=current.native_table_turn,
                        turn=current.turn_id,
                    )
                )
            return result

        def observe_damage(handler, effect, invocation, **kwargs):
            result = original_calculate(handler, effect, invocation, **kwargs)
            context, interpreted, amount = result
            receipt["damage_calculations"].append(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    amount=amount,
                    context=None if context is None else vars(context),
                )
            )
            return result

        try:
            with original_bootstrap_publication(), patch.object(
                EffectDispatcher, "execute", observe
            ), patch.object(NativeDamageHandler, "_calculate", observe_damage):
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
                    (build,),
                    (scene["anchor"],),
                    name_prefix="rushu-prepared",
                    encounter_layout=scene,
                    production_scene=True,
                    placement_directions=(5,),
                )
                player_id = next(iter(characters))
                character, deck = characters[player_id], decks[player_id]
                actor = fight.actors[player_id]
                roles = assigned_roles(fight)
                self.assertEqual((roles.player_team, roles.npc_team), (1, 0))
                self.assertEqual((actor.team, fight.actors[-200].team), (1, 0))
                receipt["roles"] = fight.native_encounter_roles
                pickup_target = (
                    next(
                        tuple(row["cell"])
                        for row in fight.native_effect_areas.values()
                        if row["reference"] == 1666
                    )
                    if pickup
                    else None
                )
                self.assertEqual(
                    (character["hp"], character["max_hp"], actor.hp),
                    (actor.max_hp, actor.max_hp, actor.max_hp),
                )
                self.assertGreaterEqual(actor.max_hp, 7802)
                self.assertGreaterEqual(actor.effect_stats[27], 50)
                self.assertEqual(actor.direction, 5)
                self.assertEqual(character["level"], 230)
                self.assertEqual(len(premise["equipment"][player_id]), 9)
                receipt.update(
                    player_id=player_id,
                    premise=premise,
                    initial_hp=actor.hp,
                    initial_resistance=actor.effect_stats[27],
                )
                if admission_only:
                    receipt.update(
                        status="canonical_geared_admission_before_first1001",
                        actor_stats=dict(actor.effect_stats),
                        boss_stats=dict(fight.actors[-200].effect_stats),
                        actor_position=actor.position,
                        actor_direction=actor.direction,
                        boss_position=fight.actors[-200].position,
                        boss_states=[
                            (entry.reference, entry.level)
                            for entry in fight.actors[-200].state_ledger.entries
                        ],
                    )
                    return
                rng = Random(0)
                common = dict(player_characters=characters, deck_blobs=decks, rng=rng)

                def serialize(selected_actor, current):
                    if (
                        getattr(selected_actor, "native_summon_source", None)
                        is not None
                    ):
                        return registered_summon_stats(selected_actor, current, 1332)
                    values = dict(
                        wp_current=selected_actor.effect_stats[4],
                        wp_maximum=selected_actor.effect_maxima[4],
                        fight=current,
                    )
                    if selected_actor.id in characters:
                        return actual_actor_stats(
                            characters[selected_actor.id],
                            selected_actor,
                            current.id,
                            **values,
                        )
                    return actual_monster_actor_stats(
                        monsters[selected_actor.id],
                        selected_actor,
                        current.id,
                        **values,
                    )

                runtime = RuntimeMessages(
                    fight,
                    runtime_stats_serializer=serialize,
                    turn_start_provider=lambda current, **kwargs: prepare_server_turn_start(
                        character,
                        monsters,
                        current,
                        deck,
                        native_events=True,
                        area_callbacks=True,
                        **common,
                        **kwargs,
                    ),
                    turn_end_provider=lambda current, **kwargs: prepare_server_turn_end(
                        character, monsters, current, deck, **common, **kwargs
                    ),
                    expiration_runtime_factory=lambda *, action_id: server_runtime(
                        character,
                        monsters,
                        deck,
                        action_id=action_id,
                        critical=False,
                        **common,
                    )[0],
                )
                receipt["before_first_turn"] = dict(
                    phase=fight.phase,
                    table=fight.native_table_turn,
                    actors={
                        identity: dict(
                            hp=a.hp,
                            team=a.team,
                            position=a.position,
                            states=[
                                (entry.reference, entry.level)
                                for entry in a.state_ledger.entries
                            ],
                        )
                        for identity, a in fight.actors.items()
                    },
                )
                runtime.turn_started()
                self.assertEqual(
                    runtime.fight.phase,
                    "active",
                    "Original opening ended combat; inspect hp_changes and damage_calculations",
                )
                for boundary in range(8 if pickup else 44):
                    current = runtime.fight
                    while runtime.awaiting_ack is not None:
                        runtime.acknowledge_turn(
                            struct.pack(">i", runtime.awaiting_ack)
                        )
                    current = runtime.fight
                    actor, boss = current.actors[player_id], current.actors[-200]
                    counter = next(
                        (
                            entry.level
                            for entry in boss.state_ledger.entries
                            if entry.reference == 7092
                        ),
                        None,
                    )
                    facts = dict(
                        turn=current.turn_id,
                        table=current.native_table_turn,
                        elapsed_seconds=round(time.monotonic() - started, 3),
                        phase=current.phase,
                        current=None if current.current is None else current.current.id,
                        hp=actor.hp,
                        wp=actor.effect_stats[4],
                        position=actor.position,
                        direction=actor.direction,
                        resistance=actor.effect_stats[27],
                        boss_vestige_count=counter,
                        area_count=len(current.native_effect_areas),
                        lava_count=sum(
                            row["reference"] == 1235
                            for row in current.native_effect_areas.values()
                        ),
                    )
                    receipt["boundaries"].append(facts)
                    journal.parent.mkdir(parents=True, exist_ok=True)
                    with journal.open("a") as stream:
                        stream.write(json.dumps(facts) + "\n")
                    if current.phase != "active":
                        break
                    if not pickup:
                        self.assertNotIn(
                            7025,
                            {entry.reference for entry in actor.state_ledger.entries},
                        )
                    if current.current.id == player_id:
                        if pickup:
                            if not receipt["payments"]:
                                for spell, ap, wp in ((7009, 2, 1), (6982, 2, 0)):
                                    actor, current = (
                                        runtime.fight.actors[player_id],
                                        runtime.fight,
                                    )
                                    spell_uid = (
                                        spell
                                        if spell in granted_spells(current, player_id)
                                        else (player_id << 32) | spell
                                    )
                                    transaction = prepare_server_spell(
                                        struct.pack(
                                            ">qqiih",
                                            player_id,
                                            spell_uid,
                                            *actor.position,
                                        ),
                                        character,
                                        monsters,
                                        current,
                                        actor.owner_id,
                                        deck,
                                        action_id=runtime.action_id + 1,
                                        critical=False,
                                        line_of_sight=lambda origin, target, state: authoritative_visible(
                                            1332,
                                            origin,
                                            target,
                                            state,
                                            blocking_footprints={
                                                a.id: footprint(
                                                    a.position, a.physical_radius
                                                )
                                                for a in state.actors.values()
                                                if a.hp > 0
                                            },
                                        ),
                                        **common,
                                    )
                                    self.assertEqual(
                                        (
                                            transaction.plan["costs"]["ap"],
                                            transaction.plan["costs"]["wp"],
                                        ),
                                        (ap, wp),
                                    )
                                    commit_spell_transaction(
                                        runtime, transaction, stats_serializer=serialize
                                    )
                                    receipt["payments"].append(
                                        dict(
                                            spell=spell,
                                            table=runtime.fight.native_table_turn,
                                            costs=transaction.plan["costs"],
                                        )
                                    )
                                actor, current = (
                                    runtime.fight.actors[player_id],
                                    runtime.fight,
                                )
                                self.assertIn(
                                    6361,
                                    {
                                        entry.reference
                                        for entry in actor.state_ledger.entries
                                    },
                                )
                            if actor.position != pickup_target:
                                occupied = {
                                    point
                                    for other in current.actors.values()
                                    if other.id != player_id and other.hp > 0
                                    for point in footprint(
                                        other.position, other.physical_radius
                                    )
                                }
                                adjacency = {}
                                for start, end in sorted(current.edges):
                                    adjacency.setdefault(start, []).append(end)
                                previous, pending = {actor.position: None}, deque(
                                    (actor.position,)
                                )
                                while pending and pickup_target not in previous:
                                    start = pending.popleft()
                                    for end in adjacency.get(start, ()):
                                        if (
                                            end not in previous
                                            and end[:2] not in occupied
                                        ):
                                            previous[end] = start
                                            pending.append(end)
                                self.assertIn(pickup_target, previous)
                                path, cursor = [], pickup_target
                                while previous[cursor] is not None:
                                    path.append(cursor)
                                    cursor = previous[cursor]
                                path = list(reversed(path))[: actor.mp]
                                if path:
                                    old_mp = actor.mp
                                    apply_client(
                                        runtime,
                                        actor.owner_id,
                                        struct.pack(">q", player_id)
                                        + b"".join(
                                            struct.pack(">iih", *cell) for cell in path
                                        ),
                                        lambda selected_actor: serialize(
                                            selected_actor, runtime.fight
                                        ),
                                        runtime_stats_serializer=serialize,
                                        area_provider=lambda candidate, **kwargs: prepare_area_movement(
                                            character,
                                            monsters,
                                            candidate,
                                            deck,
                                            **common,
                                            **kwargs,
                                        ),
                                    )
                                    actor, current = (
                                        runtime.fight.actors[player_id],
                                        runtime.fight,
                                    )
                                    receipt["movements"].append(
                                        dict(path=path, cost_mp=old_mp - actor.mp)
                                    )
                            orientation = apply_orientation(
                                runtime,
                                actor.owner_id,
                                struct.pack(">qB", player_id, 5),
                            )
                            receipt["orientations"].append(
                                dict(
                                    table=current.native_table_turn,
                                    event=orientation["event"],
                                )
                            )
                            if actor.position != pickup_target:
                                advance_actual_turn(runtime)
                                continue
                            held = [
                                entry
                                for entry in actor.state_ledger.entries
                                if entry.reference == 7025 and entry.level <= 10
                            ]
                            self.assertTrue(held)
                            if held[0].level == 0:
                                # Native1055 rejects a zero initial amount. Let
                                # the real holder clock earn a positive grade.
                                advance_actual_turn(runtime)
                                continue
                            retained = native_retained_condition_effects(
                                current, player_id
                            )
                            self.assertIn(319070, {row[0] for row in retained})
                            self.assertIn(7271, granted_spells(current, player_id))
                            occupied = {
                                point
                                for other in current.actors.values()
                                if other.hp > 0
                                for point in footprint(
                                    other.position, other.physical_radius
                                )
                            }
                            columns = {
                                tuple(point)
                                for row in current.native_effect_areas.values()
                                for point in row.get("native_cells_xy", ())
                            }
                            destinations = sorted(
                                end
                                for start, end in current.edges
                                if start == actor.position
                                and end[:2] not in occupied
                                and end[:2] not in columns
                            )
                            self.assertTrue(destinations)
                            before = set(current.native_effect_areas)
                            transaction = prepare_server_spell(
                                struct.pack(
                                    ">qqiih", player_id, 7271, *destinations[0]
                                ),
                                character,
                                monsters,
                                current,
                                actor.owner_id,
                                deck,
                                action_id=runtime.action_id + 1,
                                critical=False,
                                line_of_sight=lambda origin, target, state: authoritative_visible(
                                    1332,
                                    origin,
                                    target,
                                    state,
                                    blocking_footprints={
                                        a.id: footprint(a.position, a.physical_radius)
                                        for a in state.actors.values()
                                        if a.hp > 0
                                    },
                                ),
                                **common,
                            )
                            commit_spell_transaction(
                                runtime, transaction, stats_serializer=serialize
                            )
                            current = runtime.fight
                            self.assertFalse(
                                any(
                                    entry.reference == 7025 and entry.level <= 10
                                    for entry in current.actors[
                                        player_id
                                    ].state_ledger.entries
                                )
                            )
                            added = [
                                row
                                for uid, row in current.native_effect_areas.items()
                                if uid not in before
                            ]
                            self.assertTrue(
                                any(row["reference"] == 1666 for row in added)
                            )
                            receipt.update(
                                status="actual_player1_pickup_and_original7271_release",
                                pickup_target=pickup_target,
                                retained_before_drop=retained,
                                drop_costs=transaction.plan["costs"],
                                added_areas=added,
                            )
                            return
                        # Only the bounded component spends early. The full
                        # clock reserves the WP and three-turn armor for19.
                        if (
                            not terminal or current.native_table_turn == 19
                        ) and not receipt["payments"]:
                            transaction = prepare_server_spell(
                                struct.pack(">qqiih", player_id, 7009, *actor.position),
                                character,
                                monsters,
                                current,
                                actor.owner_id,
                                deck,
                                action_id=runtime.action_id + 1,
                                critical=False,
                                line_of_sight=lambda origin, target, state: authoritative_visible(
                                    1332,
                                    origin,
                                    target,
                                    state,
                                    blocking_footprints={
                                        a.id: footprint(a.position, a.physical_radius)
                                        for a in state.actors.values()
                                        if a.hp > 0
                                    },
                                ),
                                **common,
                            )
                            self.assertEqual(
                                (
                                    transaction.plan["costs"]["ap"],
                                    transaction.plan["costs"]["wp"],
                                ),
                                (2, 1),
                            )
                            commit_spell_transaction(
                                runtime, transaction, stats_serializer=serialize
                            )
                            receipt["payments"].append(
                                dict(
                                    table=current.native_table_turn,
                                    costs=transaction.plan["costs"],
                                )
                            )
                            current, actor = (
                                runtime.fight,
                                runtime.fight.actors[player_id],
                            )
                        if actor.position != SAFE_CELL:
                            self.assertIn(
                                (tuple(actor.position), SAFE_CELL), current.edges
                            )
                            before_mp = actor.mp
                            apply_client(
                                runtime,
                                actor.owner_id,
                                struct.pack(">q", player_id)
                                + struct.pack(">iih", *SAFE_CELL),
                                lambda selected_actor: serialize(
                                    selected_actor, runtime.fight
                                ),
                                runtime_stats_serializer=serialize,
                                area_provider=lambda candidate, **kwargs: prepare_area_movement(
                                    character,
                                    monsters,
                                    candidate,
                                    deck,
                                    **common,
                                    **kwargs,
                                ),
                            )
                            actor = runtime.fight.actors[player_id]
                            self.assertEqual(before_mp - actor.mp, 1)
                            receipt["movements"].append(
                                dict(path=[SAFE_CELL], cost_mp=1)
                            )
                        orientation = apply_orientation(
                            runtime, actor.owner_id, struct.pack(">qB", player_id, 5)
                        )
                        receipt["orientations"].append(
                            dict(
                                table=runtime.fight.native_table_turn,
                                event=orientation["event"],
                            )
                        )
                        if not terminal:
                            current, actor = (
                                runtime.fight,
                                runtime.fight.actors[player_id],
                            )
                            self.assertEqual(counter, 4)
                            self.assertEqual(
                                actor.effect_stats[27],
                                receipt["initial_resistance"] + 150,
                            )
                            before_hp, before_table = (
                                actor.hp,
                                current.native_table_turn,
                            )
                            factory, _ = server_runtime(
                                character,
                                monsters,
                                deck,
                                action_id=runtime.action_id + 1,
                                critical=False,
                                **common,
                            )
                            dispatcher, _ = factory(
                                current,
                                {"native_retained_container": {"present": False}},
                            )
                            internal = dispatcher.handlers[426].native_wrapped_handler
                            effect = dispatcher.effects["324326"]
                            native = internal.authority(current, current.actors[-200])
                            request = native_triggered_spell_request(
                                effect["parameters"],
                                1,
                                caster_id=-200,
                                target_cell=current.actors[-200].position,
                                caster_is_native_fighter=native.targeting["is_eGj"],
                            )
                            with current.effect_resolution():
                                internal.executor(
                                    request,
                                    effect,
                                    EffectInvocation(
                                        324326,
                                        1,
                                        -200,
                                        -200,
                                        current.actors[-200].position,
                                        native_retained_container={"present": False},
                                    ),
                                )
                            self.assertEqual(current.native_table_turn, before_table)
                            self.assertGreater(current.actors[player_id].hp, 0)
                            self.assertLess(current.actors[player_id].hp, before_hp)
                            self.assertTrue(
                                any(
                                    row["reference"] == 325743
                                    and row["target"] == player_id
                                    for row in receipt["damage_calculations"]
                                )
                            )
                            receipt.update(
                                status="persisted_native_230_defense_survives_original7295_component",
                                final_hp=current.actors[player_id].hp,
                            )
                            return
                    advance_actual_turn(runtime)
                self.assertTrue(terminal)
                from wakfu_server.maps.boss_score_runtime import staged_score
                from wakfu_server.combat_encounter_roles import assigned_roles

                current = runtime.fight
                self.assertEqual(staged_score(current), 0)
                self.assertEqual(
                    (current.phase, current.winner),
                    ("finished", assigned_roles(current).npc_team),
                )
                self.assertGreaterEqual(current.native_table_turn, 21)
                self.assertFalse(
                    any(
                        entry.reference == 7110
                        for entry in current.actors[-200].state_ledger.entries
                    )
                )
                self.assertTrue(
                    any(
                        row["reference"] == 325500 and row["result"]
                        for row in receipt["native_callbacks"]
                    )
                )
                self.assertFalse(
                    any(
                        row["reference"] == 324818 and row["result"]
                        for row in receipt["native_callbacks"]
                    )
                )
                for reference in (319402, 319410, 319413, 325750):
                    self.assertTrue(
                        any(
                            row["reference"] == reference and row["result"]
                            for row in receipt["native_callbacks"]
                        ),
                        reference,
                    )
                self.assertTrue(
                    any(
                        row["lava_count"]
                        for row in receipt["boundaries"]
                        if row["table"] >= 15
                    )
                )
                self.assertEqual(receipt["payments"][0]["table"], 19)
                receipt.update(
                    status="persisted_zero_score_build_reaches_original_table21_failure",
                    final_table=current.native_table_turn,
                    final_hp=current.actors[player_id].hp,
                )
        except Exception as error:
            receipt.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(limit=24),
            )
            raise
        finally:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
