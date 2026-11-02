"""Paid Crow counterplay through actual Jondo ground/mount terminal victory.

The ordinary six-player builds and initial approach positions are explicit
fixture premises, not an original-level competitive balance claim.
No armor/state/HP/MP grant or fabricated platform connection is performed.
"""
from collections import deque
from datetime import datetime, timezone
from dataclasses import replace
import json
from pathlib import Path
from random import Random
import struct
from unittest.mock import patch

from postgres_case import PostgresCase

ROOT = Path(__file__).resolve().parents[2]


class CrowPaidJondoTerminalTests(PostgresCase):
    def qualify_geared_first_paid_corbac_damage_and_source_budget(self):
        self._use_native_geared_build = True
        self._preview_damage_budget = True
        self._first_paid_max_casts = 2
        self.qualify_first_actual_paid_corbac_damage()
        receipt = self._first_paid_receipt
        normal, critical = receipt["damage_previews"]
        self.assertEqual((normal["critical"], critical["critical"]), (False, True))
        self.assert_geared_source_budget(receipt)
        self.assertEqual(receipt["attempts"][-1]["after_hp"], 0)
        self.assertIn(7330, receipt["first_paid_actor_states"])
        self.assertIn("7504", receipt["first_paid_granted_spells"])

    def assert_geared_source_budget(self, receipt):
        ordinary = receipt["damage_previews"][0]
        damage, cost = ordinary["calculated"], ordinary["costs"]["ap"]
        self.assertGreater(damage, 0)
        self.assertGreater(cost, 0)
        hp = receipt["attempts"][0]["before_hp"]
        hits = (hp + damage - 1) // damage
        wave = receipt["first_wave_hp"] // hp
        self.assertEqual(wave * hp, receipt["first_wave_hp"])
        limits = ordinary["native_usage"]
        capacities = [
            min(ap // cost, limits["per_turn"])
            if limits["per_turn"] > 0
            else ap // cost
            for ap in receipt["first_paid_party_ap"].values()
        ]
        # Native per-target and per-turn caps constrain every subset of this
        # equal-HP wave; no damage/state/resource is granted by this forecast.
        for targets in range(1, wave + 1):
            capacity = sum(
                min(value, targets * limits["per_target"])
                if limits["per_target"] > 0
                else value
                for value in capacities
            )
            self.assertGreaterEqual(capacity, targets * hits)

    def qualify_first_actual_paid_corbac_damage(self):
        self.diagnose_first_actual_paid_corbac_cast()
        receipt = self._first_paid_receipt
        self.assertGreaterEqual(len(receipt["attempts"]), 1)
        self.assertLessEqual(
            len(receipt["attempts"]), getattr(self, "_first_paid_max_casts", 1)
        )
        for attempt in receipt["attempts"]:
            self.assertLess(attempt["after_hp"], attempt["before_hp"])
            self.assertTrue(
                any(
                    row["caster"] == attempt["actor"]
                    and row["target"] == attempt["target"]
                    and row.get("probe_phase", "actual") == "actual"
                    and row["amount"] is not None
                    and row["amount"] > 0
                    for row in receipt["damage_calculations"]
                )
            )

    def diagnose_first_actual_paid_corbac_cast(self):
        self._first_cast_diagnostic_only = True
        self.test_paid_jondo_native_terminal()

    def test_paid_jondo_native_terminal(self):
        from native_paid_party_fixture import (
            NativePartyBuild,
            NativeGear,
            native_paid_party_fixture,
            native_endgame_iop_build,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from wakfu_server.combat_crow_steel_scene_layout import reconstructed_crow_scene
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_casting_los import native_casting_ray
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from tools.combat_audit_turns import advance_actual_turn

        scene = reconstructed_crow_scene(
            json.loads(
                (ROOT / ".runtime/ultimate-scenes-20261021/map-363.json").read_text()
            )
        )
        scene.update(reference=1988, level=110)
        # Existing main-board cells shorten approach only; all movement after
        # admission still uses the native directed graph and ordinary MP.
        scene["party_placement_cells"] = (
            (-6, -13, 88),
            (-9, -10, 88),
            (-3, -10, 88),
            (-8, -7, 88),
            (-4, -7, 88),
            (-6, -9, 88),
        )
        scene["anchor"] = scene["party_placement_cells"][0]
        gear = tuple(
            NativeGear(ref, slot)
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
        )
        build = NativePartyBuild(
            breed=9,
            level=200,
            active_spells=(4769, 4813, 4810),
            aptitudes=(
                (1, 40),
                (16, 10),
                (26, 40),
                (23, 10),
                (12, 49),
                (2, 1),
                (3, 1),
                (8, 1),
            ),
            gear=gear,
        )
        if getattr(
            self,
            "_use_native_geared_build",
            not getattr(self, "_first_cast_diagnostic_only", False),
        ):
            build = replace(
                native_endgame_iop_build(), breed=9, active_spells=(4769, 4813, 4810)
            )
        receipt = dict(
            status="pending",
            paid_hits=[],
            movements=[],
            boundaries=[],
            damage_calculations=[],
            attempts=[],
            resolution=[],
            damage_previews=[],
            counterspells=[],
            sources=[],
            rejected=[],
            initial_position_premise="bounded_native_main_board_approach",
            phase_lifecycle=[],
        )
        output = ROOT / (
            ".runtime/ultimate-scenes-20261021/crow-paid-jondo-terminal-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            + ".json"
        )
        last_checkpoint = None

        def actor_facts(actor):
            source = getattr(actor, "native_summon_source", None)
            counts = getattr(actor, "native_fight_property_counts", None)
            return dict(
                id=actor.id,
                ref=(source or monsters.get(actor.id, {})).get("ref"),
                hp=actor.hp,
                ap=actor.ap,
                mp=actor.mp,
                team=actor.team,
                position=actor.position,
                states=[entry.reference for entry in actor.state_ledger.entries],
                property_counts=None if counts is None else dict(counts),
            )

        def checkpoint(stage):
            nonlocal last_checkpoint
            marker = (stage, runtime.fight.native_table_turn)
            if marker == last_checkpoint:
                return
            last_checkpoint = marker
            receipt["progress"] = dict(
                stage=stage,
                turn=runtime.fight.turn_id,
                table=runtime.fight.native_table_turn,
                actors=[actor_facts(actor) for actor in runtime.fight.actors.values()],
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")

        original_execute = EffectDispatcher.execute
        from wakfu_server.combat_damage_handler import NativeDamageHandler

        original_calculate = NativeDamageHandler._calculate
        from wakfu_server.combat_effect_resolver import NativeEffectResolver

        original_resolve = NativeEffectResolver.__call__

        def observe_resolution(resolver, effect, invocation):
            if invocation.reference not in (
                351279,
                351285,
                351286,
                351287,
                348916,
                348918,
                350102,
            ):
                return original_resolve(resolver, effect, invocation)
            row = dict(
                reference=invocation.reference,
                caster=invocation.caster_id,
                target=invocation.target_id,
                cell=invocation.cell,
            )
            original_context, original_actors = resolver.context, resolver.actors

            def context(*args, **kwargs):
                result = original_context(*args, **kwargs)
                row["context"] = vars(result)
                return result

            def actors(*args, **kwargs):
                result = tuple(original_actors(*args, **kwargs))
                row["candidates"] = [
                    dict(
                        id=actor.id,
                        position=actor.position,
                        team=getattr(actor, "team", None),
                        affiliation=getattr(actor, "native_fight_affiliation", None),
                    )
                    for actor in result
                ]
                return result

            with patch.object(resolver, "context", context), patch.object(
                resolver, "actors", actors
            ):
                result = original_resolve(resolver, effect, invocation)
            row["selected"] = [
                dict(target=selected.target_id, cell=selected.cell)
                for selected in result
            ]
            receipt["resolution"].append(row)
            return result

        def observe_calculation(handler, effect, invocation, **kwargs):
            result = original_calculate(handler, effect, invocation, **kwargs)
            if invocation.caster_id > 0 and len(receipt["damage_calculations"]) < 64:
                context, interpreted, amount = result
                receipt["damage_calculations"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        cell=invocation.cell,
                        probe_phase=getattr(self, "_probe_phase", "actual"),
                        family=effect["effect_class"],
                        amount=amount,
                        context=None if context is None else vars(context),
                        interpreted=interpreted,
                    )
                )
            return result

        phase_sources = frozenset(
            (
                332565,
                332543,
                332567,
                332548,
                332725,
                332928,
                332963,
                332740,
                332730,
                335762,
                332745,
            )
        )

        def phase_facts(fight):
            boss = fight.actors.get(-200)
            return dict(
                turn=fight.turn_id,
                table=fight.native_table_turn,
                current=None if fight.current is None else fight.current.id,
                boss_hp=None if boss is None else boss.hp,
                boss_states=[]
                if boss is None
                else [entry.reference for entry in boss.state_ledger.entries],
                boss_properties={}
                if boss is None
                else dict(boss.native_fight_property_counts),
                children=[
                    dict(
                        id=actor.id,
                        hp=actor.hp,
                        reference=actor.native_summon_source["ref"],
                    )
                    for actor in fight.actors.values()
                    if getattr(actor, "native_summon_source", None) is not None
                ],
            )

        def observe(dispatcher, invocation, **kwargs):
            fight = dispatcher.native_retention.fight
            before = (
                phase_facts(fight) if invocation.reference in phase_sources else None
            )
            if before is not None:
                caster = fight.actors.get(invocation.caster_id)
                before["caster"] = (
                    None
                    if caster is None
                    else dict(
                        id=caster.id,
                        hp=caster.hp,
                        states=[
                            entry.reference for entry in caster.state_ledger.entries
                        ],
                    )
                )
            result = original_execute(dispatcher, invocation, **kwargs)
            if before is not None:
                receipt["phase_lifecycle"].append(
                    dict(
                        reference=invocation.reference,
                        result=bool(result),
                        before=before,
                        after=phase_facts(fight),
                    )
                )
            if invocation.reference in (
                332481,
                332589,
                332581,
                332735,
                332736,
                332738,
                332928,
                332963,
                351279,
                351280,
                351285,
                351286,
                351287,
                348916,
                348917,
                348918,
                350102,
                350738,
            ):
                receipt["sources"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        cell=invocation.cell,
                        result=bool(result),
                    )
                )
            return result

        try:
            with original_bootstrap_publication(), patch.object(
                EffectDispatcher, "execute", observe
            ), patch.object(
                NativeDamageHandler, "_calculate", observe_calculation
            ), patch.object(
                NativeEffectResolver, "__call__", observe_resolution
            ):
                (
                    fight,
                    characters,
                    monsters,
                    decks,
                    resources,
                    _,
                    premise,
                ) = native_paid_party_fixture(
                    self.store,
                    scene,
                    (build,) * 6,
                    scene["party_placement_cells"],
                    name_prefix="crow-paid-counter",
                    encounter_layout=scene,
                )
                receipt["build_premise"] = premise
                self.assertEqual(
                    (fight.actors[-200].hp, fight.actors[-200].max_hp), (8000, 8000)
                )
                first, rng = next(iter(characters)), Random(0)
                common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
                planning_authority = server_runtime(
                    characters[first],
                    monsters,
                    decks[first],
                    action_id=1,
                    critical=False,
                    **common,
                )[1].actor_authority

                def stats(actor, current):
                    if getattr(actor, "native_summon_source", None) is not None:
                        return registered_summon_stats(actor, current, 363)
                    values = dict(
                        wp_current=actor.effect_stats[4],
                        wp_maximum=actor.effect_maxima[4],
                        fight=current,
                    )
                    if actor.id in characters:
                        return actual_actor_stats(
                            characters[actor.id], actor, current.id, **values
                        )
                    return actual_monster_actor_stats(
                        monsters[actor.id], actor, current.id, **values
                    )

                runtime = RuntimeMessages(
                    fight,
                    runtime_stats_serializer=stats,
                    turn_start_provider=lambda phase, **kw: prepare_server_turn_start(
                        characters[first],
                        monsters,
                        phase,
                        decks[first],
                        native_events=True,
                        area_callbacks=True,
                        **common,
                        **kw,
                    ),
                    turn_end_provider=lambda phase, **kw: prepare_server_turn_end(
                        characters[first], monsters, phase, decks[first], **common, **kw
                    ),
                    expiration_runtime_factory=lambda *, action_id: server_runtime(
                        characters[first],
                        monsters,
                        decks[first],
                        action_id=action_id,
                        critical=False,
                        **common,
                    )[0],
                )

                def visible(origin, target, current):
                    return authoritative_visible(
                        363,
                        origin,
                        target,
                        current,
                        blocking_footprints={
                            actor.id: footprint(actor.position, actor.physical_radius)
                            for actor in current.actors.values()
                            if actor.hp > 0
                        },
                    )

                def approach(identity, target_actor, minimum, maximum, require_los):
                    current, actor = runtime.fight, runtime.fight.actors[identity]
                    target = target_actor.position
                    target_cells = tuple(
                        (x, y, target[2])
                        for x, y in footprint(target, target_actor.physical_radius)
                    )
                    occupied = set().union(
                        *(
                            footprint(other.position, other.physical_radius)
                            for other in current.actors.values()
                            if other.hp > 0 and other.id != identity
                        )
                    )
                    outgoing = {}
                    for start, end in current.edges:
                        outgoing.setdefault(start, []).append(end)
                    queue, seen, choices = (
                        deque([(actor.position, ())]),
                        {actor.position},
                        [],
                    )
                    while queue:
                        cell, path = queue.popleft()
                        # Original fcr's coordinate overload plans a ray without
                        # pretending the actor has already moved to that cell.
                        for target_cell in target_cells:
                            distance = abs(cell[0] - target_cell[0]) + abs(
                                cell[1] - target_cell[1]
                            )
                            legal = minimum <= distance <= maximum and (
                                not require_los
                                or native_casting_ray(
                                    current,
                                    planning_authority,
                                    363,
                                    cell,
                                    target_cell,
                                    source_height=actor.native_los_height,
                                    target_height=target_actor.native_los_height,
                                    ignored_slots=(
                                        *current.native_qi_visibility_ignored_slots,
                                        actor.native_obstacle_id,
                                    ),
                                )
                            )
                            gap = max(minimum - distance, distance - maximum, 0)
                            choices.append(
                                (not legal, gap, len(path), cell, target_cell, path)
                            )
                        if any(not choice[0] for choice in choices):
                            # BFS reached a shortest legal casting position.
                            break
                        # Plan to a genuinely castable cell across the native
                        # board, then pay only this turn's available MP. Local
                        # range-only ties otherwise strand actors behind LOS.
                        for end in sorted(outgoing.get(cell, ())):
                            if end not in seen and end[:2] not in occupied:
                                seen.add(end)
                                queue.append((end, (*path, end)))
                    chosen = min(choices)
                    full_path = chosen[-1]
                    path = full_path[: actor.mp]
                    if path:
                        origin, mp = actor.position, actor.mp
                        apply_client(
                            runtime,
                            actor.owner_id,
                            struct.pack(">q", identity)
                            + b"".join(struct.pack(">iih", *cell) for cell in path),
                            lambda selected: stats(selected, runtime.fight),
                            runtime_stats_serializer=stats,
                            area_provider=lambda candidate, **kw: prepare_area_movement(
                                characters[first],
                                monsters,
                                candidate,
                                decks[first],
                                **common,
                                **kw,
                            ),
                        )
                        receipt["movements"].append(
                            dict(
                                actor=identity,
                                origin=origin,
                                path=path,
                                before_mp=mp,
                                after_mp=runtime.fight.actors[identity].mp,
                            )
                        )
                    return (
                        None if chosen[0] or len(full_path) > len(path) else chosen[-2]
                    )

                def advance_encounter():
                    """Actual player END or actual Jondo-owned NPC turn and ACK."""
                    if runtime.fight.current.controlled:
                        advance_actual_turn(runtime)
                        return
                    import time
                    import uuid
                    from wakfu_ai.native.native_oracle import NativeOracle
                    from wakfu_ai.native.native_stats import NativeStats
                    from wakfu_ai.transport.framed import FramedClient
                    from wakfu_ai.transport.endpoint import tcp_address
                    from wakfu_ai.bridge.jondo_entry import run_prepared_turn

                    actor = runtime.fight.current
                    original_turn = runtime.fight.turn_id
                    if not getattr(runtime, "tactical_encounter_id", None):
                        runtime.tactical_encounter_id = uuid.uuid4().hex
                    oracle = NativeOracle(
                        runtime,
                        characters=characters,
                        monsters=monsters,
                        decks=decks,
                        excluded_decks={
                            identity: frozenset() for identity in characters
                        },
                        viewer_id=first,
                        flags=dict(
                            native_area_callbacks=True, native_start_events=True
                        ),
                    )
                    serializer = NativeStats(
                        characters=characters,
                        monsters=monsters,
                        fight_id=runtime.fight.id,
                        map_id=scene["map_id"],
                    )
                    channel = FramedClient(
                        *tcp_address("tcp://ai-jondo:8091"), timeout=20
                    )
                    source = getattr(actor, "native_summon_source", None)
                    row = dict(
                        actor=actor.id,
                        reference=source["ref"]
                        if source
                        else monsters[actor.id]["ref"],
                        turn=original_turn,
                        table=runtime.fight.native_table_turn,
                        hp_before=actor.hp,
                        before=actor_facts(actor),
                        actions=[],
                    )
                    receipt.setdefault("actual_jondo_turns", []).append(row)
                    try:
                        for packets, diagnostic in run_prepared_turn(
                            runtime,
                            oracle,
                            serializer,
                            channel,
                            deadline=time.monotonic() + 20,
                            max_actions=12,
                        ):
                            row["actions"].append(
                                dict(action=diagnostic["action"], packets=len(packets))
                            )
                    except Exception as error:
                        row["error"] = dict(
                            type=type(error).__name__, message=str(error)
                        )
                        raise
                    finally:
                        channel.close()
                    for _ in range(32):
                        if runtime.awaiting_ack is None:
                            break
                        runtime.acknowledge_turn(
                            struct.pack(">i", runtime.awaiting_ack)
                        )
                    self.assertIsNone(runtime.awaiting_ack)
                    self.assertFalse(runtime.pending)
                    row.update(
                        hp_after=runtime.fight.actors[actor.id].hp,
                        after=actor_facts(runtime.fight.actors[actor.id]),
                        resulting_turn=runtime.fight.turn_id,
                        resulting_phase=runtime.fight.phase,
                    )
                    self.assertTrue(
                        runtime.fight.phase == "finished"
                        or runtime.fight.turn_id != original_turn,
                        "Actual Jondo turn did not finish through native END/ACK",
                    )

                def finish_paid_terminal(ground_id):
                    """Continue this exact earned runtime through paid native KOs."""
                    receipt["terminal_actions"] = []
                    receipt["terminal_boundaries"] = []
                    receipt["mount_death_windows"] = []
                    player_team = runtime.fight.actors[first].team

                    def reference_of(actor):
                        source = getattr(actor, "native_summon_source", None)
                        return (
                            source["ref"]
                            if source
                            else monsters.get(actor.id, {}).get("ref")
                        )

                    last_table = None
                    last_progress = None
                    stagnant_tables = 0
                    for step in range(240):
                        for _ in range(32):
                            if runtime.awaiting_ack is None:
                                break
                            runtime.acknowledge_turn(
                                struct.pack(">i", runtime.awaiting_ack)
                            )
                        current = runtime.fight
                        checkpoint("terminal")
                        receipt["terminal_boundaries"].append(
                            dict(
                                step=step,
                                phase=current.phase,
                                turn=current.turn_id,
                                table=current.native_table_turn,
                                current=None
                                if current.current is None
                                else current.current.id,
                                enemies=[
                                    actor_facts(actor)
                                    for actor in current.actors.values()
                                    if actor.team != player_team and actor.hp > 0
                                ],
                                players=[
                                    actor_facts(current.actors[identity])
                                    for identity in characters
                                ],
                            )
                        )
                        if current.native_table_turn != last_table:
                            signature = (
                                tuple(
                                    (actor.id, actor.hp)
                                    for actor in current.actors.values()
                                    if actor.team != player_team and actor.hp > 0
                                ),
                                tuple(
                                    (identity, current.actors[identity].position)
                                    for identity in characters
                                ),
                            )
                            stagnant_tables = (
                                stagnant_tables + 1 if signature == last_progress else 0
                            )
                            last_progress, last_table = (
                                signature,
                                current.native_table_turn,
                            )
                            self.assertLess(
                                stagnant_tables,
                                4,
                                "No enemy HP or paid approach progress for four complete terminal tables",
                            )
                        if current.phase == "finished":
                            self.assertEqual(current.winner, player_team)
                            self.assertTrue(receipt["mount_death_windows"])
                            self.assertTrue(
                                any(
                                    row["target_ref"] == 1989 and row["after_hp"] == 0
                                    for row in receipt["terminal_actions"]
                                )
                            )
                            self.assertTrue(
                                any(
                                    row["target_ref"] == 5356 and row["after_hp"] == 0
                                    for row in receipt["terminal_actions"]
                                )
                            )
                            self.assertEqual(current.actors[ground_id].hp, 0)
                            receipt["terminal"] = dict(
                                phase=current.phase,
                                winner=current.winner,
                                ground_hp=current.actors[ground_id].hp,
                                players={
                                    identity: current.actors[identity].hp
                                    for identity in characters
                                },
                            )
                            return
                        self.assertEqual(current.phase, "active")
                        identity = current.current.id
                        if identity in characters:
                            for _ in range(12):
                                current, actor = (
                                    runtime.fight,
                                    runtime.fight.actors[identity],
                                )
                                if (
                                    current.phase != "active"
                                    or actor.hp <= 0
                                    or actor.ap < 1
                                ):
                                    break
                                enemies = [
                                    other
                                    for other in current.actors.values()
                                    if other.team != player_team and other.hp > 0
                                ]
                                if not enemies:
                                    break
                                mounts = [
                                    other
                                    for other in enemies
                                    if reference_of(other) == 5356
                                ]
                                ground = current.actors[ground_id]
                                targets = mounts or (
                                    [ground] if ground.hp > 0 else enemies
                                )
                                target = min(
                                    targets,
                                    key=lambda other: (
                                        abs(actor.position[0] - other.position[0])
                                        + abs(actor.position[1] - other.position[1]),
                                        other.id,
                                    ),
                                )
                                if any(
                                    entry.reference == 7373
                                    for entry in target.state_ledger.entries
                                ):
                                    if 7504 in granted_spells(current, identity):
                                        reference, minimum, maximum, los = (
                                            7504,
                                            1,
                                            4,
                                            False,
                                        )
                                    else:
                                        corbacs = [
                                            other
                                            for other in enemies
                                            if reference_of(other) == 1802
                                        ]
                                        if not corbacs:
                                            break
                                        target = min(
                                            corbacs,
                                            key=lambda other: (
                                                abs(
                                                    actor.position[0]
                                                    - other.position[0]
                                                )
                                                + abs(
                                                    actor.position[1]
                                                    - other.position[1]
                                                ),
                                                other.id,
                                            ),
                                        )
                                        reference, minimum, maximum, los = (
                                            4813,
                                            4,
                                            9,
                                            True,
                                        )
                                else:
                                    distance = abs(
                                        actor.position[0] - target.position[0]
                                    ) + abs(actor.position[1] - target.position[1])
                                    reference, minimum, maximum = (
                                        (4769, 2, 5) if distance < 4 else (4813, 4, 9)
                                    )
                                    los = True
                                if reference != 7504 and actor.ap < 2:
                                    break
                                target_cell = approach(
                                    identity, target, minimum, maximum, los
                                )
                                if target_cell is None:
                                    break
                                current, actor = (
                                    runtime.fight,
                                    runtime.fight.actors[identity],
                                )
                                hp, ap = current.actors[target.id].hp, actor.ap
                                granted = granted_spells(current, identity)
                                spell_uid = (
                                    granted[reference]["uid"]
                                    if reference in granted
                                    else (identity << 32) | reference
                                )
                                try:
                                    tx = prepare_server_spell(
                                        struct.pack(
                                            ">qqiih", identity, spell_uid, *target_cell
                                        ),
                                        characters[identity],
                                        monsters,
                                        current,
                                        actor.owner_id,
                                        decks[identity],
                                        action_id=runtime.action_id + 1,
                                        critical=None,
                                        line_of_sight=visible,
                                        **common,
                                    )
                                except ValueError as error:
                                    receipt["rejected"].append(
                                        dict(
                                            stage="terminal",
                                            actor=identity,
                                            spell=reference,
                                            target=target.id,
                                            reason=str(error),
                                        )
                                    )
                                    break
                                self.assertGreater(tx.plan["costs"]["ap"], 0)
                                commit_spell_transaction(
                                    runtime, tx, stats_serializer=stats
                                )
                                after = runtime.fight.actors[target.id].hp
                                receipt["terminal_actions"].append(
                                    dict(
                                        actor=identity,
                                        spell=reference,
                                        target=target.id,
                                        target_ref=reference_of(target),
                                        before_hp=hp,
                                        after_hp=after,
                                        before_ap=ap,
                                        after_ap=runtime.fight.actors[identity].ap,
                                        costs=tx.plan["costs"],
                                    )
                                )
                                if reference != 7504:
                                    self.assertLess(
                                        after,
                                        hp,
                                        "Legal terminal damage made no progress",
                                    )
                                if reference_of(target) == 5356 and after == 0:
                                    ground = runtime.fight.actors[ground_id]
                                    ground_states = [
                                        entry.reference
                                        for entry in ground.state_ledger.entries
                                    ]
                                    self.assertGreater(ground.hp, 0)
                                    self.assertIn(7334, ground_states)
                                    receipt["mount_death_windows"].append(
                                        dict(
                                            turn=runtime.fight.turn_id,
                                            table=runtime.fight.native_table_turn,
                                            mount=target.id,
                                            ground=ground_id,
                                            ground_hp=ground.hp,
                                            ground_states=ground_states,
                                        )
                                    )
                                if runtime.fight.phase != "active":
                                    break
                        if runtime.fight.phase == "active":
                            advance_encounter()
                    self.fail(
                        (
                            "Paid Crow terminal budget exhausted",
                            receipt["terminal_boundaries"][-3:],
                            receipt["terminal_actions"][-5:],
                            receipt["rejected"][-5:],
                        )
                    )

                runtime.turn_started()
                # Actual AI and its living corbacs add owned boundaries. The
                # earned1HP transition still needs original own-END1037 hide
                # and then own-START1001; do not stop at the last paid hit.
                # The existing table14 and128-paid-hit guards remain intact.
                for boundary in range(192):
                    for _ in range(32):
                        token = runtime.awaiting_ack
                        if token is None:
                            break
                        runtime.acknowledge_turn(struct.pack(">i", token))
                    else:
                        self.fail("Bounded actual ACK chain exhausted")
                    current = runtime.fight
                    checkpoint("initial_counterplay")
                    born = [
                        actor
                        for actor in current.actors.values()
                        if actor.hp > 0
                        and (getattr(actor, "native_summon_source", None) or {}).get(
                            "ref"
                        )
                        == 1989
                    ]
                    boss = current.actors[-200]
                    receipt["boundaries"].append(
                        dict(
                            turn=current.turn_id,
                            table=getattr(current, "native_table_turn", None),
                            boss_hp=boss.hp,
                            armor=any(
                                entry.reference == 7327
                                for entry in boss.state_ledger.entries
                            ),
                            phase=current.phase,
                            hidden=552
                            in {entry.reference for entry in boss.state_ledger.entries},
                            properties=dict(boss.native_fight_property_counts),
                            actor=None
                            if current.current is None
                            else current.current.id,
                        )
                    )
                    if born:
                        self.assertEqual(
                            boss.hp,
                            0,
                            "Ground profile appeared before initial Crow retirement completed",
                        )
                        self.assertTrue(receipt["counterspells"])
                        self.assertTrue(
                            any(
                                row["target_ref"] == 1802 and row["after_hp"] == 0
                                for row in receipt["paid_hits"]
                            )
                        )
                        self.assertTrue(
                            any(
                                row["target_ref"] == 1988
                                for row in receipt["paid_hits"]
                            )
                        )
                        for reference in (332589, 332581, 332738, 332928, 332963):
                            self.assertTrue(
                                any(
                                    row["reference"] == reference and row["result"]
                                    for row in receipt["sources"]
                                ),
                                reference,
                            )
                        hidden = [
                            row
                            for row in receipt["boundaries"]
                            if row["hidden"] and row["boss_hp"] > 1
                        ]
                        self.assertTrue(
                            hidden,
                            "Paid armor removal must permit the original own-end hide",
                        )
                        self.assertTrue(
                            any(
                                not row["hidden"]
                                and row["boss_hp"] > 1
                                and row["turn"] > hidden[0]["turn"]
                                for row in receipt["boundaries"]
                            ),
                            "Original own-start reveal must precede earned lethal phase",
                        )
                        for reference in (332565, 332543, 332567, 332548):
                            self.assertTrue(
                                any(
                                    row["reference"] == reference and row["result"]
                                    for row in receipt["phase_lifecycle"]
                                ),
                                reference,
                            )
                        transitions = [
                            row
                            for row in receipt["phase_lifecycle"]
                            if row["reference"] == 332725 and row["result"]
                        ]
                        self.assertTrue(
                            transitions,
                            "Ground birth requires the original conditional native426",
                        )
                        self.assertTrue(
                            all(row["before"]["boss_hp"] == 1 for row in transitions)
                        )
                        self.assertTrue(
                            any(
                                row["target_ref"] == 1988 and row["after_hp"] == 1
                                for row in receipt["paid_hits"]
                            )
                        )
                        self.assertEqual(current.phase, "active")
                        self.assertEqual(len(born), 1)
                        self.assertGreater(born[0].hp, 0)
                        self.assertEqual(
                            (born[0].native_controller_id, born[0].native_master_id),
                            (born[0].id, born[0].id),
                        )
                        receipt["earned_ground_actor"] = dict(
                            id=born[0].id,
                            hp=born[0].hp,
                            source=born[0].native_summon_source,
                            registration=current.native_summon_registrations[
                                born[0].id
                            ],
                        )
                        ground_id = born[0].id
                        for _ in range(2 * (len(runtime.fight.actors) + 4)):
                            self.assertEqual(runtime.fight.phase, "active")
                            if runtime.fight.current.id == ground_id:
                                break
                            advance_encounter()
                        self.assertEqual(runtime.fight.current.id, ground_id)
                        self.assertGreater(runtime.fight.current.hp, 0)
                        self.assertNotIn(
                            7334,
                            {
                                entry.reference
                                for entry in runtime.fight.current.state_ledger.entries
                            },
                        )
                        self.assertFalse(
                            any(
                                actor.hp > 0
                                and (
                                    getattr(actor, "native_summon_source", None) or {}
                                ).get("ref")
                                == 5356
                                for actor in runtime.fight.actors.values()
                            )
                        )
                        # The actual ground AI may cast its owned7509 before
                        # END. Otherwise7332/332739 queues it via332740; that
                        # callback correctly skips when5356 already exists.
                        advance_encounter()
                        mounts = [
                            actor
                            for actor in runtime.fight.actors.values()
                            if actor.hp > 0
                            and (
                                getattr(actor, "native_summon_source", None) or {}
                            ).get("ref")
                            == 5356
                        ]
                        self.assertEqual(len(mounts), 1)
                        mount_triggers = [
                            row
                            for row in receipt["phase_lifecycle"]
                            if row["reference"] == 332740 and row["result"]
                        ]
                        owned_mount_casts = [
                            row
                            for row in receipt["actual_jondo_turns"]
                            if row["actor"] == ground_id
                            and any(
                                entry["action"].get("spellId") == 7509
                                for entry in row["actions"]
                            )
                        ]
                        self.assertTrue(
                            mount_triggers or owned_mount_casts,
                            "Mount requires its actual callback or owned ground AI cast",
                        )
                        self.assertTrue(
                            all(
                                row["before"]["caster"]["id"] == ground_id
                                and row["before"]["caster"]["hp"] > 0
                                and 7334 not in row["before"]["caster"]["states"]
                                for row in mount_triggers
                            )
                        )
                        self.assertTrue(
                            any(
                                row["reference"] == 332730
                                and row["result"]
                                and row["before"]["caster"]["id"] == ground_id
                                and row["before"]["caster"]["hp"] > 0
                                and 7334 not in row["before"]["caster"]["states"]
                                for row in receipt["phase_lifecycle"]
                            )
                        )
                        receipt["earned_mount"] = dict(
                            id=mounts[0].id,
                            hp=mounts[0].hp,
                            source=mounts[0].native_summon_source,
                            registration=runtime.fight.native_summon_registrations[
                                mounts[0].id
                            ],
                        )
                        receipt.update(
                            status="paid_hide_reveal_ground_and_native_mount_qualified",
                            born=[actor.id for actor in born],
                        )
                        self.assertEqual(runtime.fight.walkable, scene["cells"])
                        self.assertEqual(runtime.fight.edges, scene["edges"])
                        finish_paid_terminal(ground_id)
                        receipt[
                            "status"
                        ] = "paid_jondo_native_crow_terminal_victory_qualified"
                        receipt[
                            "qualification_scope"
                        ] = "Same earned initial/ground/mount native runtime with real Jondo turns for every ordinary and registered NPC, normal paid player actions and native callbacks; ordinary geared level245 party fixture premise, not original-level balance qualification."
                        return
                    self.assertGreater(
                        boss.hp, 0, "Initial Crow retired without an actual1989 birth"
                    )
                    if (
                        current.phase != "active"
                        or current.current is None
                        or getattr(current, "native_table_turn", 1) > 14
                    ):
                        break
                    identity = current.current.id
                    if identity in characters:
                        for _ in range(8):
                            current = runtime.fight
                            actor, boss = current.actors[identity], current.actors[-200]
                            if actor.ap < 1 or actor.hp <= 0 or boss.hp <= 1:
                                break
                            # During legitimate552 invulnerability, clear the
                            # actual corbacs rather than abandoning every turn.
                            hidden = any(
                                entry.reference == 552
                                for entry in boss.state_ledger.entries
                            )
                            # Deliberately pass after the first genuinely earned
                            # counterspell until the original hide/reveal cycle
                            # completes. No state, damage, resources or event is
                            # synthesized to make that prerequisite happen.
                            if receipt["counterspells"] and not any(
                                row["reference"] == 332548 and row["result"]
                                for row in receipt["phase_lifecycle"]
                            ):
                                break
                            armor = any(
                                entry.reference == 7327
                                for entry in boss.state_ledger.entries
                            )
                            empowered = any(
                                entry.reference == 7330
                                for entry in actor.state_ledger.entries
                            )
                            if armor and empowered and not hidden:
                                self.assertIn(7504, granted_spells(current, identity))
                                target, reference, minimum, maximum, los = (
                                    boss,
                                    7504,
                                    1,
                                    4,
                                    False,
                                )
                            else:
                                corbacs = [
                                    other
                                    for other in current.actors.values()
                                    if other.hp > 0
                                    and (
                                        getattr(other, "native_summon_source", None)
                                        or {}
                                    ).get("ref")
                                    == 1802
                                ]
                                if (armor or hidden) and not corbacs:
                                    approach(identity, boss, 4, 9, True)
                                    break
                                target = (
                                    min(
                                        corbacs,
                                        key=lambda other: (
                                            abs(other.position[0] - actor.position[0])
                                            + abs(
                                                other.position[1] - actor.position[1]
                                            ),
                                            other.id,
                                        ),
                                    )
                                    if armor or hidden
                                    else boss
                                )
                                distance = abs(
                                    target.position[0] - actor.position[0]
                                ) + abs(target.position[1] - actor.position[1])
                                reference, minimum, maximum = (
                                    (4769, 2, 5) if distance < 4 else (4813, 4, 9)
                                )
                                los = True
                                if actor.ap < 2:
                                    break
                            target_cell = approach(
                                identity, target, minimum, maximum, los
                            )
                            if target_cell is None:
                                break
                            current = runtime.fight
                            hp, ap = (
                                current.actors[target.id].hp,
                                current.actors[identity].ap,
                            )
                            spell_uid = (
                                granted_spells(current, identity)[reference]["uid"]
                                if reference == 7504
                                else (identity << 32) | reference
                            )
                            body = struct.pack(
                                ">qqiih", identity, spell_uid, *target_cell
                            )

                            def prepare(critical):
                                return prepare_server_spell(
                                    body,
                                    characters[identity],
                                    monsters,
                                    current,
                                    characters[identity]["account_id"],
                                    decks[identity],
                                    action_id=runtime.action_id + 1,
                                    critical=critical,
                                    **common,
                                    line_of_sight=visible,
                                )

                            if (
                                getattr(self, "_preview_damage_budget", False)
                                and not receipt["damage_previews"]
                            ):
                                receipt["first_paid_party_ap"] = {
                                    str(member): current.actors[member].ap
                                    for member in characters
                                }
                                receipt["first_wave_hp"] = sum(
                                    other.hp
                                    for other in current.actors.values()
                                    if other.hp > 0
                                    and (
                                        getattr(other, "native_summon_source", None)
                                        or {}
                                    ).get("ref")
                                    == 1802
                                )
                                baseline, rng_before = snapshot(current), rng.getstate()
                                try:
                                    for critical in (False, True):
                                        rng.setstate(rng_before)
                                        self._probe_phase = (
                                            "critical_preview"
                                            if critical
                                            else "ordinary_preview"
                                        )
                                        start = len(receipt["damage_calculations"])
                                        preview = prepare(critical)
                                        calculated = sum(
                                            row["amount"] or 0
                                            for row in receipt["damage_calculations"][
                                                start:
                                            ]
                                            if row["caster"] == identity
                                            and row["target"] == target.id
                                        )
                                        receipt["damage_previews"].append(
                                            dict(
                                                critical=critical,
                                                calculated=calculated,
                                                before_hp=hp,
                                                after_hp=preview.fight.actors[
                                                    target.id
                                                ].hp,
                                                costs=preview.plan["costs"],
                                                native_usage=preview.plan[
                                                    "native_usage"
                                                ],
                                            )
                                        )
                                        self.assertEqual(
                                            snapshot(current),
                                            baseline,
                                            "Discarded source preview changed live fight",
                                        )
                                finally:
                                    rng.setstate(rng_before)
                                    self._probe_phase = "actual"
                            try:
                                tx = prepare(None)
                            except ValueError as error:
                                receipt["rejected"].append(
                                    dict(
                                        actor=identity,
                                        spell=reference,
                                        target=target.id,
                                        reason=str(error),
                                    )
                                )
                                break
                            self.assertGreater(tx.plan["costs"]["ap"], 0)
                            self.assertEqual(tx.plan["target_id"], target.id)
                            receipt["attempts"].append(
                                dict(
                                    actor=identity,
                                    spell=reference,
                                    target=target.id,
                                    target_cell=target_cell,
                                    critical=tx.plan.get("critical_decision"),
                                    before_hp=hp,
                                    after_hp=tx.fight.actors[target.id].hp,
                                    before_ap=ap,
                                    after_ap=tx.fight.actors[identity].ap,
                                    costs=tx.plan["costs"],
                                    outcomes=tx.outcomes,
                                    events=tx.events,
                                )
                            )
                            self.assertEqual(
                                tx.fight.actors[identity].ap,
                                ap - tx.plan["costs"]["ap"],
                            )
                            commit_spell_transaction(
                                runtime, tx, stats_serializer=stats
                            )
                            if getattr(self, "_first_cast_diagnostic_only", False) and (
                                runtime.fight.actors[target.id].hp == 0
                                or len(receipt["attempts"])
                                >= getattr(self, "_first_paid_max_casts", 1)
                            ):
                                receipt["first_paid_actor_states"] = [
                                    entry.reference
                                    for entry in runtime.fight.actors[
                                        identity
                                    ].state_ledger.entries
                                ]
                                receipt["first_paid_granted_spells"] = {
                                    str(ref): entry
                                    for ref, entry in granted_spells(
                                        runtime.fight, identity
                                    ).items()
                                }
                                receipt[
                                    "status"
                                ] = "first_actual_paid_corbac_cast_observed_only"
                                return
                            if reference == 7504:
                                self.assertFalse(
                                    any(
                                        entry.reference == 7327
                                        for entry in runtime.fight.actors[
                                            -200
                                        ].state_ledger.entries
                                    )
                                )
                                receipt["counterspells"].append(
                                    dict(actor=identity, paid_ap=tx.plan["costs"]["ap"])
                                )
                            else:
                                after = runtime.fight.actors[target.id].hp
                                self.assertLess(
                                    after, hp, "Paid damage made no progress"
                                )
                                receipt["paid_hits"].append(
                                    dict(
                                        actor=identity,
                                        spell=reference,
                                        target=target.id,
                                        target_ref=1802 if target.id != -200 else 1988,
                                        before_hp=hp,
                                        after_hp=after,
                                        cost=tx.plan["costs"]["ap"],
                                    )
                                )
                                self.assertLess(
                                    len(receipt["paid_hits"]),
                                    128,
                                    "Bounded paid-hit budget exhausted",
                                )
                    advance_encounter()
                self.fail(
                    (
                        "Native Crow counterplay budget exhausted",
                        receipt["boundaries"][-4:],
                        receipt["paid_hits"][-4:],
                    )
                )
        except Exception as error:
            receipt.update(
                status="failed", error_type=type(error).__name__, error=str(error)
            )
            raise
        finally:
            if "runtime" in locals():
                receipt["final_actor_facts"] = [
                    actor_facts(actor) for actor in runtime.fight.actors.values()
                ]
            self._first_paid_receipt = receipt
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
