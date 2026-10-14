"""Native eYy/865 does not consume its source LIFE_STEAL_HEAL_EFFECT tag."""
import unittest
from copy import deepcopy
from wakfu_server.combat_native_events import validate_group_registration_flags


class ValueTransferFlag29Tests(unittest.TestCase):
    def setUp(self):
        # Authentic installed spell6764 root282680 and its two native children.
        self.effect = dict(
            effect_class=865, native_effect_flags=[29], children=[282681, 282682]
        )

    def validate(self, effect=None, flags=(29,)):
        return validate_group_registration_flags(
            flags,
            active=True,
            effect=self.effect if effect is None else effect,
            reference=282680,
        )

    def test_actual_transfer_source_marker_preserved_without_mutation(self):
        before = deepcopy(self.effect)
        self.validate()
        self.assertEqual(self.effect, before)

    def test_flag_only_other_family_and_invalid_transfer_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_group_registration_flags([29], active=True)
        for change in (
            dict(effect_class=330),
            dict(children=[]),
            dict(children=[True, 2]),
            dict(native_effect_flags=[]),
        ):
            with self.assertRaises(ValueError):
                self.validate(dict(self.effect, **change))

    def test_native_marker_does_not_admit_unrelated_unknown_flag(self):
        with self.assertRaisesRegex(ValueError, "123"):
            self.validate(
                dict(self.effect, native_effect_flags=[29, 123]), flags=(29, 123)
            )

    def test_marker_keeps_real_damage_callback_and_healing_wire_identical(self):
        import test_combat_value_transfer_runtime as fixture_module
        from wakfu_server.combat_effect_dispatch import (
            EffectInvocation,
            run_effect_transaction,
        )
        from wakfu_server.fight_checkpoint_store import snapshot

        results = []
        for flags in ([], [29]):
            fixture = fixture_module.ValueTransferRuntimeTests()
            fixture.setUp()
            fixture.effects["90"]["native_effect_flags"] = flags
            preview, outcomes = run_effect_transaction(
                fixture.fight,
                [EffectInvocation(90, 1, 7, -7, (9, 9, 0))],
                fixture.factory,
            )
            self.assertEqual(outcomes, (True,))
            results.append((snapshot(preview), fixture.outbox))
        self.assertEqual(results[0], results[1])

    def test_actual_compiled_catalog_tuple_children_keep_same_native_contract(self):
        from wakfu_server.combat_static_catalogs import ImmutableCatalog

        compiled = ImmutableCatalog(self.effect)
        self.assertIsInstance(compiled["children"], tuple)
        self.validate(compiled)
