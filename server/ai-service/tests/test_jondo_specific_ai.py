"""Specific-profile bridge contracts; pure projection and actual driver custody."""
from copy import deepcopy
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from wakfu_ai.bridge import jondo_entry, jondo_snapshot
from test_jondo_bridge import Oracle, Runtime, Transport, reply, request_fixture


class SpecificAimProjectionTests(unittest.TestCase):
    def test_aims_are_bounded_empty_visible_and_do_not_change_source(self):
        actor = SimpleNamespace(
            id=-7, position=(0, 0, 0), physical_radius=0, hp=100, controlled=False
        )
        player = SimpleNamespace(
            id=7, position=(2, 0, 0), physical_radius=1, hp=100, controlled=True
        )
        cells = [(x, y, 0) for x in range(-3, 4) for y in range(-3, 4)]
        indices = {cell: index for index, cell in enumerate(cells)}
        before = deepcopy((vars(actor), vars(player), indices))
        spells = [dict(needsFreeCell=True, needsLineOfSight=True)]
        aims = jondo_snapshot.special_aim_cells(actor, indices, [actor, player], spells)
        self.assertLessEqual(len(aims), 16)
        self.assertEqual(len(aims), len(set(aims)))
        for index in aims:
            cell = cells[index]
            self.assertNotEqual(cell, actor.position)
            self.assertFalse(1 <= cell[0] <= 3 and -1 <= cell[1] <= 1)
        self.assertEqual(
            aims,
            jondo_snapshot.special_aim_cells(actor, indices, [actor, player], spells),
        )
        self.assertEqual((vars(actor), vars(player), indices), before)

    def test_aim_projection_requires_declared_free_cell_and_los(self):
        actor = SimpleNamespace(
            position=(0, 0, 0), physical_radius=0, hp=1, controlled=False
        )
        indices = {(0, 0, 0): 0, (1, 0, 0): 1}
        for spells in (
            [],
            [dict(needsFreeCell=False, needsLineOfSight=True)],
            [dict(needsFreeCell=True, needsLineOfSight=False)],
        ):
            self.assertEqual(
                jondo_snapshot.special_aim_cells(actor, indices, [actor], spells), []
            )

    def test_area_refresh_uses_private_rows_and_only_projects_live_visible_mechanics(
        self,
    ):
        actor = SimpleNamespace(physical_radius=1)
        area = dict(
            uid=1, reference=655, cell=(0, 0, 0), owner_id=-7, remaining_activations=-1
        )
        rows = {
            1: area,
            2: dict(area, uid=2, reference=999),
            3: dict(area, uid=3, remaining_activations=0),
            4: dict(area, uid=4, owner_id=-99),
            5: dict(area, uid=5, hidden=True),
            6: dict(area, uid=60),
            7: dict(area, uid=7, executing=True),
        }
        fight = SimpleNamespace(native_effect_areas=rows)
        original = deepcopy(rows)
        seen = []

        def refresh(current, private):
            self.assertIs(current, fight)
            self.assertIsNot(private, area)
            private["cell"] = (1, 0, 0)
            private["qa_refreshed"] = True
            seen.append(private)

        def contains(private, cell, radius):
            self.assertTrue(private["qa_refreshed"])
            self.assertEqual(radius, 1)
            return cell[0] in (1, 2)

        with patch(
            "wakfu_server.combat_area_authority.area_guards",
            return_value=dict(baG=False, baK=False, baF=True),
        ), patch(
            "wakfu_server.combat_effect_area_geometry.refresh_area_geometry",
            side_effect=refresh,
        ), patch(
            "wakfu_server.combat_effect_area_geometry.contains_area_actor",
            side_effect=contains,
        ):
            result = jondo_snapshot.mechanic_areas(
                fight, actor, {(0, 0, 0): 0, (1, 0, 0): 1, (2, 0, 0): 2}, hidden={-99}
            )
        self.assertEqual(
            result, [dict(reference=655, cell=1, cells=[1, 2], ownerId=-7)]
        )
        self.assertEqual(len(seen), 1)
        self.assertEqual(rows, original)

    def test_retired_or_unknown_geometry_does_not_become_an_aim(self):
        fight = SimpleNamespace(
            native_effect_areas={1: dict(uid=1, reference=1085, cell=(0, 0, 0))}
        )
        with patch(
            "wakfu_server.combat_area_authority.area_guards",
            return_value=dict(baG=True, baK=True, baF=False),
        ):
            self.assertEqual(
                jondo_snapshot.mechanic_areas(
                    fight, SimpleNamespace(physical_radius=0), {(0, 0, 0): 0}
                ),
                [],
            )
        with patch(
            "wakfu_server.combat_area_authority.area_guards",
            return_value=dict(baG=False, baK=False, baF=True),
        ), patch(
            "wakfu_server.combat_effect_area_geometry.refresh_area_geometry",
            side_effect=ValueError("missing geometry"),
        ):
            self.assertEqual(
                jondo_snapshot.mechanic_areas(
                    fight, SimpleNamespace(physical_radius=0), {(0, 0, 0): 0}
                ),
                [],
            )

    def test_nox_managed_flag_requires_both_exact_frozen_callbacks(self):
        callbacks = [
            dict(
                effect_reference=e,
                owner_reference=5664,
                owner_state=s,
                forbidden_state=f,
                timing="owned_boss_post_start",
                event_id=1005,
                channel=60,
            )
            for e, s, f in ((401544, 8978, 8979), (401749, 8979, 9031))
        ]
        policy = dict(
            policy="wakemu-nox-owned-boundaries-v4",
            map_id=1435,
            boss_reference=5664,
            monster_references=[5664],
            callbacks=callbacks,
        )
        fight = SimpleNamespace(native_encounter_table_listener_policy=policy)
        self.assertTrue(jondo_snapshot.nox_calendar_managed(fight))
        for field, value in [
            ("policy", "wakemu-nox-owned-boundaries-v3"),
            ("map_id", 1),
            ("boss_reference", 1),
        ]:
            altered = deepcopy(policy)
            altered[field] = value
            self.assertFalse(
                jondo_snapshot.nox_calendar_managed(
                    SimpleNamespace(native_encounter_table_listener_policy=altered)
                )
            )
        altered = deepcopy(policy)
        altered["callbacks"][1]["channel"] = 6
        self.assertFalse(
            jondo_snapshot.nox_calendar_managed(
                SimpleNamespace(native_encounter_table_listener_policy=altered)
            )
        )
        self.assertFalse(jondo_snapshot.nox_calendar_managed(SimpleNamespace()))


class NativeActionHistoryTests(unittest.TestCase):
    def test_history_contains_only_successfully_committed_actions(self):
        runtime = Runtime()
        runtime.fight.current.position = (0, 0, 0)
        oracle = Oracle(runtime)
        actions = [
            dict(type="cast", spellId=99, level=1, target=[1, 0, 0]),
            dict(type="cast", spellId=7, level=1, target=[1, 0, 0]),
            dict(type="end_turn"),
        ]

        def choose(request, count):
            return reply(
                request,
                actions[0] if count == 1 else actions[2],
                [actions[1]] if count == 1 else [],
            )

        transport = Transport(choose)
        with patch.object(jondo_entry, "build_snapshot", request_fixture):
            list(
                jondo_entry.run_prepared_turn(
                    runtime,
                    oracle,
                    object(),
                    transport,
                    deadline=time.monotonic() + 5,
                    max_actions=3,
                )
            )
        self.assertEqual(transport.requests[0]["native"]["turnActions"], [])
        history = transport.requests[-1]["native"]["turnActions"]
        self.assertEqual(history, [dict(type="cast", spellId=7, target=[1, 0, 0])])
        self.assertNotIn(99, [row.get("spellId") for row in history])

    def test_history_resets_for_a_new_driver_invocation(self):
        runtime = Runtime()
        runtime.fight.current.position = (0, 0, 0)
        oracle = Oracle(runtime)
        first = Transport(
            lambda request, count: reply(
                request, dict(type="cast", spellId=7, level=1, target=[1, 0, 0])
            )
        )
        with patch.object(jondo_entry, "build_snapshot", request_fixture):
            list(
                jondo_entry.run_prepared_turn(
                    runtime,
                    oracle,
                    object(),
                    first,
                    deadline=time.monotonic() + 5,
                    max_actions=1,
                )
            )
        runtime.awaiting_ack = None
        runtime.fight.turn_id = 2
        second = Transport(lambda request, count: reply(request, dict(type="end_turn")))
        with patch.object(jondo_entry, "build_snapshot", request_fixture):
            list(
                jondo_entry.run_prepared_turn(
                    runtime,
                    oracle,
                    object(),
                    second,
                    deadline=time.monotonic() + 5,
                    max_actions=1,
                )
            )
        self.assertEqual(second.requests[0]["native"]["turnActions"], [])
