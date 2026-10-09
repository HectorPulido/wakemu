"""Retained class 314 areas keep actor-target and caster-manager identities."""
import unittest
import struct
from types import SimpleNamespace

from wakfu_server.combat_effect_area import NativeEffectAreaHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_retained_effects import (
    NativeRetainedEffectView,
    NativeRetainedRemoval,
    RetainedEffect,
    register_owned_removals,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.wire import proto_fields


class RetainedArea314Tests(unittest.TestCase):
    def exercise_retained_area(self, target_id):
        caster = SimpleNamespace(
            id=7,
            position=(0, 0, 0),
            direction=3,
            state_ledger=SimpleNamespace(entries=()),
        )
        target = SimpleNamespace(
            id=8, position=(1, 0, 0), state_ledger=SimpleNamespace(entries=())
        )
        fight = SimpleNamespace(
            id=1,
            actors={7: caster, 8: target},
            native_effect_areas={},
            native_owned_area_effects={},
            native_retired_area_managers={},
            native_retained_records={},
            owned_stat_effects={},
            state_wire_payloads={},
            native_owned_group_effects={},
        )
        packets = []
        allocated = iter((101, 102))
        handler = NativeEffectAreaHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=lambda: next(allocated),
            context=lambda *_: StatExecutionContext(
                True, True, None, True, b"\x08\x00"
            ),
            container=lambda _: ({"container_type": 1}, 50),
        )
        # The aura prototype has native child effects; this focused test only
        # verifies area identity/retention and supplies an explicit callback.
        handler.on_created = lambda _row: None
        invocation = EffectInvocation(123, 1, 7, target_id, (0, 0, 0))

        self.assertTrue(
            handler({"effect_class": 314}, {"parameters": [1527, 1]}, invocation)
        )
        area = fight.native_effect_areas[101]
        retained = fight.native_owned_area_effects[102]
        self.assertEqual(area["target_id"], target_id)
        self.assertEqual(retained["target_id"], target_id)
        self.assertEqual(retained["caster_id"], 7)
        self.assertEqual(retained["effect_class"], 314)
        self.assertEqual(packets[0][0], 13497)

        entry = RetainedEffect(
            102, target_id, 314, 123, manager_id=7, container_present=False
        )
        view = NativeRetainedEffectView(
            fight, [entry], population_verified_complete=True
        )
        removal = NativeRetainedRemoval(view)
        outbox = []
        register_owned_removals(
            removal,
            stat_handler=SimpleNamespace(fight=fight),
            packets=outbox,
            action_id=3,
        )
        removal.remove([102])

        self.assertEqual(fight.native_effect_areas, {})
        self.assertEqual(fight.native_owned_area_effects, {})
        self.assertEqual(outbox[0][0], 13560)
        payload = outbox[0][1]
        self.assertEqual(struct.unpack(">iiiih", payload[:18])[3], 314)
        body_fields = tuple(proto_fields(payload[18:-16]))
        if target_id is None:
            self.assertNotIn(56, dict(body_fields))
            self.assertEqual(dict(body_fields)[42], b"\x08\x00\x10\x00\x18\x00")
        else:
            self.assertEqual(dict(body_fields).get(56), target_id, repr(body_fields))
        self.assertEqual(struct.unpack(">qq", payload[-16:]), (7, 102))
        if target_id is not None:
            self.assertEqual(target.id, target_id)

    def test_actor_target_retention_and_removal_keep_manager_caster(self):
        self.exercise_retained_area(8)

    def test_cell_target_retention_preserves_cell_and_manager(self):
        self.exercise_retained_area(None)


if __name__ == "__main__":
    unittest.main()
