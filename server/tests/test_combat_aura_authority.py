"""faN areas project the registered owner instead of a frozen glyph cell."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_area import NativeEffectAreaHandler, native_effect_areas
from wakfu_server.combat_effect_area_geometry import contains_area_cell
from wakfu_server.combat_effect_area_queries import _rows, specific_area_count
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
from wakfu_server.combat_state_managers import registered_area_pv
from wakfu_server.combat_area_authority import area_guards
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext


class AuraAuthorityTests(unittest.TestCase):
    def setup_area(self):
        owner = SimpleNamespace(id=7, position=(0, 0, 0), direction=3)
        recipient = SimpleNamespace(id=8, position=(1, 0, 0))
        fight = SimpleNamespace(id=1, actors={7: owner, 8: recipient})
        packets, created = [], []
        ids = iter((101, 102))
        handler = NativeEffectAreaHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=lambda: next(ids),
            context=lambda *_: StatExecutionContext(
                True, True, None, False, b"\x08\x00"
            ),
            container=lambda _: ({"container_type": 1}, 50),
        )
        handler.on_created = created.append
        invocation = EffectInvocation(123, 1, 7, 7, (9, 9, 0))
        self.assertTrue(
            handler({"effect_class": 314}, {"parameters": [1527, 1]}, invocation)
        )
        return fight, owner, recipient, created[0]

    def test_fresh_aura_has_native_identity_and_owner_anchor(self):
        fight, owner, _, row = self.setup_area()
        self.assertEqual(row["native_area_contract"], "faN")
        self.assertEqual(row["cell"], owner.position)
        self.assertEqual(row["native_anchor_source"], "faN.bgZ")
        self.assertFalse(row["native_qq_bhi"])
        self.assertFalse(
            registered_area_pv(fight, row["uid"]).native_running_effect_manager
        )
        self.assertFalse(area_guards(fight, row["uid"])["baK"])
        self.assertNotIn("state_ledger", row)

    def test_queries_follow_changed_owner_coordinates(self):
        fight, owner, _, row = self.setup_area()
        self.assertTrue(contains_area_cell(_rows(fight)[0], (1, 0, 0)))
        owner.position = (5, 5, 2)
        updated = _rows(fight)[0]
        self.assertFalse(contains_area_cell(updated, (1, 0, 0)))
        self.assertTrue(contains_area_cell(updated, (6, 5, 2)))
        self.assertEqual(registered_area_pv(fight, row["uid"]).position, owner.position)
        self.assertEqual(
            specific_area_count(
                fight,
                source_id=7,
                center=(5, 5, 2),
                area_reference=1527,
                minimum=0,
                maximum=0,
            ),
            1,
        )

    def test_missing_anchor_is_unknown(self):
        fight, _, _, row = self.setup_area()
        row.pop("native_anchor_source")
        with self.assertRaises(ValueError):
            _rows(fight)

    def test_owner_entry_exit_skipped_but_other_recipient_delivered(self):
        fight, _, _, row = self.setup_area()
        runtime = NativeAreaEventRuntime(fight, None, definitions=native_effect_areas())
        calls = []
        runtime._activate = lambda r, d, t: calls.append(("entry", t.id)) or True
        runtime._exit = lambda r, t: calls.append(("exit", t.id)) or True
        self.assertEqual(
            runtime.event(10001, 7, from_cell=(9, 9, 0), to_cell=(1, 0, 0)), ()
        )
        self.assertEqual(
            runtime.event(10002, 7, from_cell=(1, 0, 0), to_cell=(9, 9, 0)), ()
        )
        self.assertEqual(calls, [])
        self.assertEqual(
            runtime.event(10001, 8, from_cell=(9, 9, 0), to_cell=(1, 0, 0)), (True,)
        )
        self.assertEqual(calls, [("entry", 8)])
