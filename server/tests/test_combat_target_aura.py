import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_area import NativeEffectAreaHandler, native_effect_areas
from wakfu_server.combat_target_aura import (
    NativeTargetAuraHandler,
    target_aura_additional,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_execution_context import constructed_execution_context
from wakfu_server.wire import proto_fields


class TargetAuraTests(unittest.TestCase):
    def test_additional_contains_only_original_ij21_identity(self):
        self.assertEqual(dict(proto_fields(target_aura_additional(56))), {168: 56})

    def test_shared_constructor_uses_target_anchor_direction_level_and_notification_order(
        self,
    ):
        fight = SimpleNamespace(
            id=12,
            phase="active",
            actors={
                8: SimpleNamespace(position=(0, 0, 0), direction=7),
                7: SimpleNamespace(position=(2, 3, 0), direction=2),
            },
            native_effect_areas={},
        )
        packets, order = [], []
        identities = iter((55, 56))
        handler = NativeEffectAreaHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: next(identities),
            context=lambda effect, invocation: StatExecutionContext(
                True, True, None, True, b""
            ),
            container=lambda invocation: ({"container_type": 1}, 777),
            area_affiliation=lambda preview, identity: identity,
        )
        handler.on_created = lambda row: order.append(
            ("created", row["uid"], len(packets))
        )
        retention = SimpleNamespace(
            register_applied_target_aura=lambda effect, invocation, uid: order.append(
                ("register", uid)
            )
        )
        aura = NativeTargetAuraHandler(handler, retention, rng=lambda: 0.5)
        aura.event_lifecycle = SimpleNamespace(
            phase=lambda effect, invocation, **kwargs: order.append(
                ("phase", kwargs["channel"])
            )
        )
        invocation = EffectInvocation(
            100,
            17,
            8,
            7,
            (4, 5, 0),
            native_context_hex=constructed_execution_context().payload().hex(),
        )
        # Original prototype data is used; source eYJ ignores extra parameters.
        self.assertEqual(native_effect_areas()["1059"]["type"], "AURA")
        self.assertTrue(
            aura(
                dict(
                    effect_class=338,
                    parameters=[1059.0, 0.0, 999.0, 0.0],
                    target_masks=[None] * 7,
                ),
                dict(parameters=[1059, 999]),
                invocation,
            )
        )
        row = fight.native_effect_areas[56]
        self.assertEqual(
            (row["owner_id"], row["native_anchor_id"], row["direction"], row["level"]),
            (7, 7, 2, 17),
        )
        self.assertEqual(row["cell"], (2, 3, 0))
        self.assertFalse(row["keep_after"])
        self.assertEqual(
            order,
            [
                ("phase", 1),
                ("phase", 2),
                ("register", 55),
                ("created", 56, 1),
                ("phase", 3),
                ("phase", 4),
            ],
        )
        payload = dict(proto_fields(packets[0][1][18:]))
        self.assertEqual(payload[32], 1059)
        self.assertEqual(dict(proto_fields(payload[66])), {168: 56})
        self.assertEqual(fight.native_owned_area_effects[55]["target_id"], 7)
        self.assertEqual(aura.prepared, {})
