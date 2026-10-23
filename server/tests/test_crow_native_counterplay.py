"""Paid Crow counterplay from native full HP to a real ground-profile birth.

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


class CrowNativeCounterplayTests(PostgresCase):
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
        self.test_paid_corbac_counterspell_and_damage_produce_actual_ground_crow()

    def test_paid_corbac_counterspell_and_damage_produce_actual_ground_crow(self):
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
        )
        output = ROOT / (
            ".runtime/ultimate-scenes-20261021/crow-native-counterplay-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            + ".json"
        )
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

        def observe(dispatcher, invocation, **kwargs):
            result = original_execute(dispatcher, invocation, **kwargs)
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
                    **common
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
                        **kw
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
                        **common
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
                        if len(path) >= actor.mp:
                            continue
                        for end in sorted(outgoing.get(cell, ())):
                            if end not in seen and end[:2] not in occupied:
                                seen.add(end)
                                queue.append((end, (*path, end)))
                    chosen = min(choices)
                    path = chosen[-1]
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
                                **kw
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
                    return None if chosen[0] else chosen[-2]

                runtime.turn_started()
                for boundary in range(112):
                    for _ in range(32):
                        token = runtime.awaiting_ack
                        if token is None:
                            break
                        runtime.acknowledge_turn(struct.pack(">i", token))
                    else:
                        self.fail("Bounded actual ACK chain exhausted")
                    current = runtime.fight
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
                        receipt.update(
                            status="actual_ground_crow_born_after_paid_native_counterplay",
                            born=[actor.id for actor in born],
                        )
                        self.assertEqual(current.walkable, scene["cells"])
                        self.assertEqual(current.edges, scene["edges"])
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
                            armor = any(
                                entry.reference == 7327
                                for entry in boss.state_ledger.entries
                            )
                            empowered = any(
                                entry.reference == 7330
                                for entry in actor.state_ledger.entries
                            )
                            if armor and empowered:
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
                                if armor and not corbacs:
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
                                    if armor
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
                                    line_of_sight=visible
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
                    advance_actual_turn(runtime)
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
            self._first_paid_receipt = receipt
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
