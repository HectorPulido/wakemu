import json, unittest
from pathlib import Path
from types import SimpleNamespace
from wakfu_server.combat_target_ordering import (
    order_native_targets,
    native_xy_distance,
    native_target_ordering,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_events import validate_group_registration_flags
from wakfu_server import native_catalog


class NativeTargetOrderingTests(unittest.TestCase):
    def test_native_faH_stable_sort_priority_and_signed_cap(self):
        rows = json.loads(
            native_catalog.read_text(
                Path(__file__).parents[1]
                / "protocol/native-target-ordering-fixture.json"
            )
        )
        self.assertEqual(len(rows), 12)
        for row in rows:
            actors = [
                SimpleNamespace(id=p[0], position=(p[1], p[2], 99))
                for p in row["actors"]
            ]
            effect = {"effect_class": 330, "native_effect_flags": row["flags"]}
            inv = EffectInvocation(123, 1, 7, None, tuple(row["cell"]) + (0,))
            result = order_native_targets(
                effect,
                inv,
                actors,
                metadata={
                    "123": dict(row, effect_class=330, native_effect_flags=row["flags"])
                },
            )
            self.assertEqual([a.id for a in result], row["ordered"])

    def test_exported_real_tromba_identity_and_no_cap(self):
        row = native_target_ordering()["370600"]
        self.assertEqual(
            row,
            {"effect_class": 330, "maximum_targets": -1, "native_effect_flags": [26]},
        )
        validate_group_registration_flags([26], active=True)
        inv = EffectInvocation(370600, 5, 7, 7, (2, 0, 0))
        actors = [
            SimpleNamespace(id=7, position=(0, 0, 0)),
            SimpleNamespace(id=8, position=(2, 0, 0)),
        ]
        result = order_native_targets(
            {"effect_class": 330, "native_effect_flags": [26]}, inv, actors
        )
        self.assertEqual([a.id for a in result], [7, 8])

    def test_unknown_identity_and_health_priority_are_not_ignored(self):
        inv = EffectInvocation(999999, 1, 7, None, (0, 0, 0))
        with self.assertRaisesRegex(ValueError, "identity"):
            order_native_targets(
                {"effect_class": 330, "native_effect_flags": [26]}, inv, (), metadata={}
            )
        with self.assertRaisesRegex(ValueError, "health-percent"):
            order_native_targets(
                {"effect_class": 330, "native_effect_flags": [8, 26]},
                inv,
                (),
                metadata={},
            )

    def test_java_coordinate_overflow_and_z_is_ignored(self):
        self.assertEqual(
            native_xy_distance((-(1 << 31), 0, 99), (0, 0, -99)), -(1 << 31)
        )
        self.assertEqual(native_xy_distance((0, 0, 99), (0, 0, -99)), 0)

    def test_native_hide_zone_flag_is_not_a_group_execution_blocker(self):
        validate_group_registration_flags([3, 17], active=True)
        with self.assertRaises(ValueError):
            validate_group_registration_flags([32], active=True)
