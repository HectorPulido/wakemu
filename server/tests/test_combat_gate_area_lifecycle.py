import unittest
from types import SimpleNamespace

from wakfu_server.combat_area_authority import area_guards
from wakfu_server.combat_effect_area import NativeEffectAreaHandler, native_effect_areas
from wakfu_server.combat_effect_area_queries import _rows, team_area_count
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_gate_conditions import has_valid_gate_for_tp
from wakfu_server.combat_state_managers import registered_area_pv, state_manager
from wakfu_server.combat_stat_handler import StatExecutionContext


class NativeGateAreaLifecycleTests(unittest.TestCase):
    def create(self, reference=823, affiliation=0):
        actor = SimpleNamespace(
            id=7, position=(0, 0, 0), direction=0, team=0, native_fight_affiliation=0
        )
        fight = SimpleNamespace(id=77, actors={7: actor}, native_effect_areas={})
        allocated = []
        packets = []

        def allocate():
            uid = 901 + len(allocated)
            allocated.append(uid)
            return uid

        handler = NativeEffectAreaHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=allocate,
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            container=lambda invocation: (dict(container_type=None), None),
            area_affiliation=(
                None if affiliation is None else lambda *args: affiliation
            ),
        )
        handler.on_created = lambda row: None
        return fight, handler, allocated, packets

    def invoke(self, handler, reference):
        return handler(
            {"effect_class": 315},
            {"parameters": [reference]},
            EffectInvocation(100, 1, 7, None, (2, 3, 0)),
        )

    def test_native_gate_prototypes_have_fixed_pv_and_null_qf(self):
        for reference in (823, 2131):
            with self.subTest(reference=reference):
                self.assertEqual(
                    native_effect_areas()[str(reference)]["native_class"], "bcS"
                )
                fight, handler, allocated, packets = self.create(reference)
                self.assertTrue(self.invoke(handler, reference))
                row = fight.native_effect_areas[901]
                self.assertEqual(row["native_area_contract"], "faX")
                self.assertEqual(
                    (row["native_type_id"], row["native_obstacle_id"]), (19, -1)
                )
                self.assertNotIn("state_ledger", row)
                self.assertIsNone(state_manager(fight, 901))
                fight.actors[7].position = (10, 10, 0)
                fight.actors[7].native_fight_affiliation = 1
                self.assertEqual(_rows(fight)[0]["cell"], (2, 3, 0))
                pv = registered_area_pv(fight, 901)
                self.assertEqual(
                    (pv.position, pv.native_fight_affiliation), ((2, 3, 0), 0)
                )
                self.assertEqual(
                    area_guards(fight, 901), dict(baG=False, baK=False, baF=True)
                )
                self.assertEqual(len(packets), 1)

    def test_gate_queries_use_captured_affiliation_and_explicit_occupancy(self):
        fight, handler, _, _ = self.create()
        self.invoke(handler, 823)
        fight.actors[7].native_fight_affiliation = 1
        args = dict(
            caster_id=9, caster_affiliation=0, center=(2, 3, 0), minimum=0, maximum=1
        )
        self.assertTrue(
            has_valid_gate_for_tp(
                _rows(fight), cell_affiliations=lambda *args: frozenset(), **args
            )
        )
        self.assertFalse(
            has_valid_gate_for_tp(
                _rows(fight), cell_affiliations=lambda *args: frozenset({0}), **args
            )
        )
        self.assertEqual(
            team_area_count(
                fight, source_id=7, center=(2, 3, 0), area_type=19, minimum=0, maximum=1
            ),
            0,
        )
        fight.actors[9] = SimpleNamespace(team=0, native_fight_affiliation=0)
        self.assertEqual(
            team_area_count(
                fight, source_id=9, center=(2, 3, 0), area_type=19, minimum=0, maximum=1
            ),
            1,
        )

    def test_missing_or_invalid_affiliation_rejects_before_uid_and_packets(self):
        for affiliation in (None, True, 128, -129, "0"):
            with self.subTest(affiliation=affiliation):
                fight, handler, allocated, packets = self.create(
                    affiliation=affiliation
                )
                with self.assertRaisesRegex(ValueError, "affiliation"):
                    self.invoke(handler, 823)
                self.assertEqual(
                    (allocated, packets, fight.native_effect_areas), ([], [], {})
                )

    def test_gate_snapshot_missing_capture_provenance_remains_unknown(self):
        fight, handler, _, _ = self.create()
        self.invoke(handler, 823)
        del fight.native_effect_areas[901]["native_fight_affiliation_source"]
        with self.assertRaisesRegex(ValueError, "bcM authority"):
            _rows(fight)
