"""Actual Eliotrope portal replacement through the native passive branch."""
import os
import unittest
import test_combat_eliotrope_runtime as runtime


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropePortalLifecycleRuntimeTests(unittest.TestCase):
    fixture = runtime.EliotropeRuntimeTests.fixture
    cast = runtime.EliotropeRuntimeTests.cast
    next_owned_turn = runtime.EliotropeRuntimeTests.next_owned_turn
    place_portal = runtime.EliotropeRuntimeTests.place_portal

    def test_portalivio_replaces_at_native_two_portal_limit(self):
        data = self.fixture(passives=(7206,))
        for index in range(2):
            tx = self.place_portal(
                data,
                near=data[2].actors[7 if index == 0 else -7].position,
                action_id=11 + index,
            )
            data = (*data[:2], tx.fight, *data[3:])
        before = {
            a["uid"]
            for a in data[2].native_effect_areas.values()
            if a.get("reference") == 823
        }
        self.assertEqual(len(before), 2)
        self.next_owned_turn(data)
        from unittest.mock import patch
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        selected = {
            145038,
            145048,
            346477,
            395958,
            145047,
            395962,
            395964,
            346478,
            346487,
            346488,
            346490,
        }
        calls, diagnostics, candidates = [], [], []
        from wakfu_server.combat_multiple_target_group import select_multiple_targets

        def multiple(values, population, **kwargs):
            population = tuple(population)
            tracked = any(item.reference == 346478 for item in population)
            if tracked or not population:
                candidates.append(
                    dict(
                        parameters=values["parameters"],
                        targets=[
                            (item.reference, item.target_id, item.cell)
                            for item in population
                        ],
                    )
                )
            condition = kwargs["condition"]

            def checked(item):
                result = condition(item)
                if item.reference == 346478:
                    candidates.append(
                        dict(
                            criterion_target=item.target_id,
                            cell=item.cell,
                            accepted=result,
                        )
                    )
                return result

            return select_multiple_targets(
                values, population, **dict(kwargs, condition=checked)
            )

        original = EffectDispatcher.execute

        def execute(dispatcher, invocation, **kwargs):
            result = original(dispatcher, invocation, **kwargs)
            if invocation.reference in selected and len(calls) < 256:
                calls.append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        cell=invocation.cell,
                        level=invocation.level,
                        criteria=dispatcher.effects[str(invocation.reference)].get(
                            "criteria"
                        ),
                        result=result,
                    )
                )
            return result

        def diagnostic(**row):
            if row.get("effect_reference") in selected and len(diagnostics) < 256:
                diagnostics.append(row)

        try:
            with patch.object(EffectDispatcher, "execute", execute), patch(
                "wakfu_server.combat_multiple_target_group.select_multiple_targets",
                multiple,
            ), combat_diagnostic_scope(diagnostic, limit=4096):
                tx = self.place_portal(
                    data, near=data[2].actors[7].position, action_id=20
                )
        except AssertionError as error:
            self.fail(
                str(
                    dict(
                        reason=str(error),
                        calls=calls,
                        diagnostics=diagnostics,
                        candidates=candidates,
                    )
                )
            )
        after = {
            a["uid"]
            for a in tx.fight.native_effect_areas.values()
            if a.get("reference") == 823
        }
        self.assertEqual(len(after), 2)
        self.assertEqual(len(after - before), 1)
        self.assertEqual(len(before - after), 1)
        self.assertEqual(
            {
                a["uid"]
                for a in data[2].native_effect_areas.values()
                if a.get("reference") == 823
            },
            before,
        )

    def test_actual_portal_checkpoint_preserves_owned_native_area(self):
        import json
        from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot

        data = self.fixture()
        tx = self.place_portal(data, near=data[2].actors[7].position, action_id=11)
        saved = snapshot(tx.fight)
        restored = Checkpoints._read_snapshot(json.loads(json.dumps(saved)))
        rows = {
            uid: row
            for uid, row in saved["native_effect_areas"].items()
            if row.get("reference") == 823
        }
        self.assertEqual(len(rows), 1)
        for uid, row in rows.items():
            self.assertEqual(restored["native_effect_areas"][uid], row)
            self.assertEqual(row["owner_id"], 7)
            self.assertEqual(row["native_type_id"], 19)

    def test_live_portal_rehydration_tracks_only_live_creators_after_recast(self):
        from wakfu_server.combat_spectator_snapshot import _retained_carrier_packets
        from wakfu_server.fight_checkpoint_store import snapshot
        from class_spell_eligible_targets import candidate_cells
        from unittest.mock import patch

        data = self.fixture()

        def place_bounded(current, *, near, action_id):
            cells, total = candidate_cells(current[2], 7, limit=4096)
            occupied = {
                actor.position for actor in current[2].actors.values() if actor.hp > 0
            }
            used = {
                tuple(area["cell"]) for area in current[2].native_effect_areas.values()
            }
            free = sorted(
                (cell for cell in cells if cell not in occupied | used),
                key=lambda cell: (
                    abs(cell[0] - near[0]) + abs(cell[1] - near[1]),
                    cell,
                ),
            )
            last_error = None
            for bound in (8, 16, 32):
                with patch(
                    "class_spell_eligible_targets.candidate_cells",
                    return_value=(tuple(free[:bound]), total),
                ):
                    try:
                        return self.place_portal(
                            current, near=near, action_id=action_id
                        )
                    except AssertionError as error:
                        last_error = error
                        if "eligible" not in str(
                            error
                        ) and "False is not true" not in str(error):
                            raise
            raise last_error or AssertionError("No bounded portal target qualified")

        first = place_bounded(data, near=data[2].actors[7].position, action_id=11)
        data = (*data[:2], first.fight, *data[3:])
        second = place_bounded(data, near=data[2].actors[-7].position, action_id=12)
        data = (*data[:2], second.fight, *data[3:])
        fight = data[2]
        before = snapshot(fight)
        live_uids = {
            area["uid"]
            for area in fight.native_effect_areas.values()
            if area.get("reference") == 823
        }
        self.assertEqual(len(live_uids), 2)

        rehydration = {}
        packets = _retained_carrier_packets(
            fight, action_id=30, area_rehydration=rehydration
        )
        self.assertIsInstance(packets, tuple)
        self.assertEqual(snapshot(fight), before)

        def actor_payload(current_fight, actor, session=None):
            from wakfu_server.breed_resources import live_wp
            from wakfu_server.combat_actor import (
                actual_actor_stats,
                actual_monster_actor_stats,
            )
            from wakfu_server.combat_remote_effects import active_actor_effects

            if actor.controlled:
                stats = actual_actor_stats(
                    data[0],
                    actor,
                    current_fight.id,
                    fight=current_fight,
                    wp_current=live_wp(current_fight, actor.id)[0],
                    wp_maximum=live_wp(current_fight, actor.id)[1],
                )
            else:
                current = live_wp(current_fight, actor.id)
                native_monster = dict(
                    data[1],
                    level=actor.effective_level,
                    x=actor.position[0],
                    y=actor.position[1],
                    z=actor.position[2],
                )
                stats = actual_monster_actor_stats(
                    native_monster,
                    actor,
                    current_fight.id,
                    fight=current_fight,
                    wp_current=current[0],
                    wp_maximum=current[1],
                )
            return stats, active_actor_effects(current_fight, actor.id)

        from types import SimpleNamespace
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_spectator_wire import decode_spectator_bootstrap
        from wakfu_server.combat_spectator_snapshot import current_snapshot
        from wakfu_server.combat_wire import decode_bootstrap
        from wakfu_server.combat_remote_effects import decode_remote_effects
        from wakfu_server.combat_effect_removal import _identity_fields
        import struct

        def check_bootstraps(current_fight, action_id, expected):
            qi = current_fight.native_qi_snapshot
            arena = dict(
                map_id=1134,
                instance_id=7,
                x=qi["x"],
                y=qi["y"],
                width=qi["width"],
                height=qi["height"],
                min_z=min(cell[2] for cell in current_fight.walkable),
                max_z=max(cell[2] for cell in current_fight.walkable),
                cell_masks=qi["cell_masks"],
                team_values=[],
            )
            shared = SimpleNamespace(
                map_id=1134,
                instance_id=0,
                is_duel=False,
                reconnect_remaining_turn_seconds=None,
                join_context=dict(
                    arena=arena,
                    terrain_effect_id=1,
                    terrain_instance_id=0,
                    leaders={0: 7, 1: -7},
                ),
                runtime=SimpleNamespace(
                    native_action_id=action_id,
                    turn_deadline=None,
                    awaiting_ack=None,
                    clock=lambda: 0,
                ),
            )
            source = snapshot(current_fight)
            spectator = decode_spectator_bootstrap(
                next(
                    payload
                    for opcode, payload in current_snapshot(
                        current_fight,
                        shared,
                        actor_payload=actor_payload,
                        deadline_ms=1,
                    )
                    if opcode == 12044
                )
            )
            owned = decode_bootstrap(
                next(
                    payload
                    for opcode, payload in owned_snapshot(
                        current_fight,
                        shared,
                        SimpleNamespace(account_id=3, character_id=7),
                        actor_payload=actor_payload,
                    )
                    if opcode == 12847
                )
            )
            missing_by_role = {}
            duplicate_by_role = {}
            for label, bootstrap in (("spectator", spectator), ("owned", owned)):
                portal_sections = []
                for section in bootstrap["myK"]:
                    if len(section) < struct.calcsize(">qqiihqhib"):
                        continue
                    reference, area_uid = struct.unpack_from(">qq", section)
                    if reference == 823:
                        portal_sections.append(area_uid)
                missing_by_role[label] = sorted(expected - set(portal_sections))
                duplicate_by_role[label] = sorted(
                    uid
                    for uid in set(portal_sections)
                    if portal_sections.count(uid) > 1
                )
                owner = next(
                    row for row in bootstrap["participants"] if row["actor_id"] == 7
                )
                effect_uids = {
                    area["effect_uid"]
                    for area in current_fight.native_effect_areas.values()
                    if area.get("reference") == 823
                }
                owner_effect_uids = {
                    _identity_fields(row.payload, integer_fields=(1,)).get(1)
                    for row in decode_remote_effects(owner["myF"])
                }
                self.assertTrue(
                    effect_uids.isdisjoint(owner_effect_uids),
                    f"{label} bootstrap illegally duplicated non-retained portal creators into myF",
                )
            self.assertEqual(
                {"missing": missing_by_role, "duplicates": duplicate_by_role},
                {
                    "missing": {"spectator": [], "owned": []},
                    "duplicates": {"spectator": [], "owned": []},
                },
                "actual portal areas must be projected once in each decoded myK bootstrap",
            )
            self.assertEqual(snapshot(current_fight), source)

        check_bootstraps(
            fight,
            30,
            {
                area["uid"]
                for area in fight.native_effect_areas.values()
                if area.get("reference") == 823
            },
        )
        self.assertEqual(snapshot(fight), before)

        # 4678 has a native per-turn use cap; remove one portal only after a
        # real owner turn boundary, preserving its ordinary cast guard.
        self.next_owned_turn(data)
        fight = data[2]

        retired_uid, cell = next(
            (uid, tuple(area["cell"]))
            for uid, area in fight.native_effect_areas.items()
            if area.get("reference") == 823
        )
        removed = self.cast(data, 4678, target=cell, action_id=13)
        self.assertNotIn(retired_uid, removed.fight.native_effect_areas)
        self.assertIn(retired_uid, fight.native_effect_areas)

        after_recast = snapshot(removed.fight)
        remaining = {
            area["uid"]
            for area in removed.fight.native_effect_areas.values()
            if area.get("reference") == 823
        }
        self.assertEqual(len(remaining), 1)
        remaining_portals = {
            area["uid"]
            for area in removed.fight.native_effect_areas.values()
            if area.get("reference") == 823
        }
        self.assertNotIn(
            retired_uid,
            remaining_portals,
        )
        self.assertEqual(
            remaining_portals,
            {
                area["uid"]
                for area in fight.native_effect_areas.values()
                if area.get("reference") == 823 and area["uid"] != retired_uid
            },
        )
        check_bootstraps(removed.fight, 31, remaining_portals)
        self.assertEqual(snapshot(removed.fight), after_recast)
