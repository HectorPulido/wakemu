"""Original faJ descending HP comparator and exact native group admission."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_target_health_ordering import (
    NativeHealthOperand as HP,
    compare_native_health_descending,
    health_operand_for_pv,
)
from wakfu_server.combat_target_ordering import order_native_targets
from wakfu_server.combat_native_events import validate_group_registration_flags
from wakfu_server.combat_health_ordering_authority import CONTRACT
import test_combat_health_ordering_integration as integration_fixture


class DescendingHealthOrderingTests(unittest.TestCase):
    def native_rows(self):
        return json.loads(
            (
                Path(__file__).with_name("fixtures")
                / "native_descending_health_ordering_authority.json"
            ).read_text()
        )["rows"]

    def test_faJ_absence_asymmetry_float32_ties_and_java_special_values(self):
        compare = compare_native_health_descending
        self.assertEqual(compare(HP(False), HP(True, 1, 2)), 1)
        self.assertEqual(compare(HP(True, 1, 2), HP(False)), -1)
        self.assertEqual(compare(HP(False), HP(False)), 1)
        self.assertEqual(compare(HP(True, 1, 2), HP(True, 2, 4)), 0)
        self.assertEqual(
            compare(HP(True, 16777217, 16777216), HP(True, 16777216, 16777217)), 0
        )
        self.assertEqual(compare(HP(True, 0, 0), HP(True, 1, 0)), -1)
        self.assertEqual(compare(HP(True, -1, 0), HP(True, 1, 0)), 1)
        self.assertEqual(compare(HP(True, 0, -1), HP(True, 0, 1)), 1)
        with self.assertRaises(ValueError):
            compare(object(), HP(False))

    def test_health_precedence_stable_ties_and_native_signed_cap(self):
        actors = [SimpleNamespace(id=i, position=(i, 0, 0)) for i in (1, 2, 3, 4)]
        operands = {
            1: HP(True, 10, 100),
            2: HP(True, 75, 100),
            3: HP(True, 150, 200),
            4: HP(False),
        }
        for flags, contract, expected in (
            ([25], CONTRACT, [2, 3]),
            ([25, 14, 26], CONTRACT, [2, 3]),
            ([8, 25, 14, 26], "faI.PV.a.sgC.PA.aYS.aYU.float32.asc.v1", [1, 2]),
        ):
            effect = dict(effect_class=345, native_effect_flags=flags)
            row = dict(effect, maximum_targets=2, ordering_contract=contract)
            inv = SimpleNamespace(reference=123, cell=(1000, 0, 0))
            with self.subTest(flags=flags):
                result = order_native_targets(
                    effect,
                    inv,
                    actors,
                    metadata={"123": row},
                    health_operand=lambda actor: operands[actor.id],
                )
                self.assertEqual([actor.id for actor in result], expected)
                row["maximum_targets"] = -1
                self.assertEqual(
                    len(
                        order_native_targets(
                            effect,
                            inv,
                            actors,
                            metadata={"123": row},
                            health_operand=lambda actor: operands[actor.id],
                        )
                    ),
                    4,
                )

    def test_actual_325710_health_sort_precedes_single_filtered_native_choice(self):
        from wakfu_server.combat_multiple_target_group import select_multiple_targets

        builder = integration_fixture.HealthOrderingIntegrationTests()
        actors = (
            builder.actor(1, 10, 100),
            builder.actor(2, 80, 100),
            builder.actor(3, 70, 100),
        )
        fight = SimpleNamespace(actors={actor.id: actor for actor in actors})
        rows = self.native_rows()
        self.assertEqual(len(rows), 9)
        effect = dict(effect_class=345, native_effect_flags=[25])
        inv = SimpleNamespace(reference=325710, cell=(0, 0, 0))
        with patch(
            "wakfu_server.combat_health_ordering_authority.descending_health_target_ordering",
            return_value=rows,
        ):
            validate_group_registration_flags(
                [25], active=True, effect=effect, reference=325710
            )
            ordered = order_native_targets(
                effect,
                inv,
                actors,
                health_operand=lambda actor: health_operand_for_pv(fight, actor),
            )
        candidates = tuple(SimpleNamespace(target_id=actor.id) for actor in ordered)
        selected = select_multiple_targets(
            {"parameters": [1, 1, 0]},
            candidates,
            caster_position=(0, 0, 0),
            position=lambda uid: fight.actors[uid].position,
            condition=lambda candidate: True,
            rng=lambda: self.fail("Original no-shuffle branch"),
        )
        self.assertEqual([item.target_id for item in selected], [2])
        self.assertEqual([actor.hp for actor in actors], [10, 80, 70])

    def test_exact_flags_and_identity_required_no_scalar_hp_fallback(self):
        rows = self.native_rows()
        with patch(
            "wakfu_server.combat_health_ordering_authority.descending_health_target_ordering",
            return_value=rows,
        ):
            for reference, effect in (
                (999999, dict(effect_class=345, native_effect_flags=[25])),
                (325710, dict(effect_class=330, native_effect_flags=[25])),
                (325710, dict(effect_class=345, native_effect_flags=[25, 14])),
            ):
                with self.subTest(
                    reference=reference, effect=effect
                ), self.assertRaisesRegex(ValueError, "identity"):
                    validate_group_registration_flags(
                        effect["native_effect_flags"],
                        active=True,
                        effect=effect,
                        reference=reference,
                    )
            with self.assertRaisesRegex(ValueError, "Unaudited"):
                validate_group_registration_flags([25], active=True)
            with self.assertRaisesRegex(ValueError, "requires active"):
                validate_group_registration_flags(
                    [25],
                    active=False,
                    effect=dict(effect_class=345, native_effect_flags=[25]),
                    reference=325710,
                )
            with self.assertRaisesRegex(ValueError, "differ"):
                validate_group_registration_flags(
                    [25, 14],
                    active=True,
                    effect=dict(effect_class=345, native_effect_flags=[25]),
                    reference=325710,
                )
        for operand in (None, lambda actor: None):
            with self.subTest(operand=operand), self.assertRaisesRegex(
                ValueError, "PA provider|PA operand"
            ):
                order_native_targets(
                    dict(effect_class=345, native_effect_flags=[25]),
                    SimpleNamespace(reference=325710, cell=(0, 0, 0)),
                    [SimpleNamespace(id=1)],
                    metadata=rows,
                    health_operand=operand,
                )
