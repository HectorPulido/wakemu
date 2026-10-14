"""Bounded isolated-summon fixture contracts; gameplay remains separately proven."""
import sys
import types
import unittest
from unittest.mock import Mock, patch

from isolated_native_summon_fixture import fixture, validate_request


class IsolatedNativeSummonFixtureTests(unittest.TestCase):
    def test_positive_native_bounds_preserve_original_descriptor(self):
        row = {"min_level": 0, "max_level": 50}
        for level in (1, 50):
            self.assertIs(validate_request(3251, level, {3251: row}), row)
        self.assertEqual(row, {"min_level": 0, "max_level": 50})

    def test_invalid_or_unknown_request_rejects(self):
        native = {3251: {"min_level": 0, "max_level": 50}}
        for reference, level in (
            (3251, 0),
            (3251, 51),
            (3251, -1),
            (3251, True),
            (True, 1),
            (9999, 1),
        ):
            with self.subTest(reference=reference, level=level):
                with self.assertRaises(ValueError):
                    validate_request(reference, level, native)

    def _modules(self, runtime, builder, insertion, stats):
        definitions = {
            "combat_server_spell": {"server_runtime": runtime},
            "combat_summon": {
                "SummonSpecification": lambda *args: args,
                "fresh_summon_insertion": insertion,
            },
            "combat_summon_creation": {"NativeSummonBuilder": builder},
            "combat_summon_initialization": {
                "summon_initializer": Mock(return_value="initializer")
            },
            "combat_summon_stats": {"registered_summon_stats": stats},
        }
        result = {}
        for name, values in definitions.items():
            module = types.ModuleType("wakfu_server." + name)
            module.__dict__.update(values)
            result[module.__name__] = module
        return result

    def test_dummy_owner_must_be_current_and_registered(self):
        validator = Mock(
            NATIVE_SOURCE_MONSTERS={3251: {"min_level": 0, "max_level": 50}}
        )
        runtime, builder = Mock(), Mock()
        modules = self._modules(runtime, builder, Mock(), Mock())
        for current in (None, types.SimpleNamespace(id=7)):
            validator.fixture.return_value = (
                types.SimpleNamespace(current=current),
                {},
                {},
                [],
            )
            with patch.dict(sys.modules, modules), self.assertRaisesRegex(
                ValueError, "Dummy native owner"
            ):
                fixture(validator, 3251, 1)
        runtime.assert_not_called()
        builder.assert_not_called()

    def test_builder_and_registration_preserve_native_book_stats(self):
        owner = types.SimpleNamespace(
            id=7, position=(0, 0, 0), hp=100, direction=3, team=1
        )
        fight = types.SimpleNamespace(
            current=owner, actors={7: owner}, walkable={(0, 0, 0), (1, 0, 0)}
        )
        book = {"native": [42, 43]}
        actor = types.SimpleNamespace(
            native_summon_source={"reference": 3251},
            native_summon_action_book=book,
            native_controlled_by_ai=True,
            effect_stats={2: 6, 3: 3, 4: 2},
            effect_maxima={2: 6, 3: 3, 4: 2},
        )
        authority = Mock()
        runtime_factory = types.SimpleNamespace(summon_authority=authority)
        runtime = Mock(return_value=(runtime_factory, None))
        build = Mock(return_value=(actor, "registration"))
        builder = Mock(return_value=build)
        insertion = Mock(return_value=([7, 8], 0))
        stats = Mock()
        validator = Mock(
            NATIVE_SOURCE_MONSTERS={3251: {"min_level": 0, "max_level": 50}}
        )
        validator.fixture.return_value = (fight, {"map_id": 12}, {7: {}}, [])
        with patch.dict(sys.modules, self._modules(runtime, builder, insertion, stats)):
            result = fixture(validator, 3251, 1)
        self.assertIs(result[0], fight)
        self.assertEqual(
            build.call_args.args,
            (fight, (3251, 1, False, 3, 1, "caster", 1), 7, 8, (1, 0, 0)),
        )
        authority.register.assert_called_once_with(
            fight, actor, "registration", new_order=[7, 8], new_turn_index=0
        )
        stats.assert_called_once_with(actor, fight, 12)
        self.assertIs(actor.native_summon_action_book, book)
        self.assertEqual(actor.effect_stats, {2: 6, 3: 3, 4: 2})
        receipt = result[-1]
        self.assertFalse(receipt["resources_granted"])
        self.assertFalse(receipt["creator_cast_required"])
        self.assertFalse(receipt["admission"])
        receipt["native_action_book"]["native"].append(99)
        self.assertEqual(book, {"native": [42, 43]})


if __name__ == "__main__":
    unittest.main()
