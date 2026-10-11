"""Reference-level short circuiting for bulk monster activation previews."""
from pathlib import Path
import sys
import struct
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server" / "tools"))

import validate_monster_spell_activation as validator  # noqa: E402


class MonsterActivationReferenceEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.row = {"ref": 1297, "min_level": 1, "max_level": 2}

    def test_fail_fast_stops_lazily_at_first_pending_case(self):
        ability_levels = []
        calls = []

        def abilities(reference, level):
            ability_levels.append((reference, level))
            yield {"spell_id": level * 10 + 1, "spell_level": 1}
            yield {"spell_id": level * 10 + 2, "spell_level": 2}

        def run(reference, level, spell, spell_level, cells, limit):
            calls.append((reference, level, spell, spell_level))
            return {"status": "pending"}

        result = validator.evaluate_reference_cases(
            self.row, abilities, (), 12, fail_fast=True, case_runner=run
        )

        self.assertEqual(result, [{"status": "pending"}])
        self.assertEqual(ability_levels, [(1297, 1)])
        self.assertEqual(calls, [(1297, 1, 11, 1)])

    def test_success_evaluates_every_spell_at_every_native_level(self):
        calls = []

        def abilities(reference, level):
            return [
                {"spell_id": level * 10 + 1, "spell_level": 1},
                {"spell_id": level * 10 + 2, "spell_level": 2},
            ]

        def run(reference, level, spell, spell_level, cells, limit):
            calls.append((level, spell, spell_level))
            return {"status": "validated"}

        result = validator.evaluate_reference_cases(
            self.row, abilities, (), 12, fail_fast=True, case_runner=run
        )

        self.assertEqual(len(result), 4)
        self.assertEqual(
            calls,
            [(1, 11, 1), (1, 12, 2), (2, 21, 1), (2, 22, 2)],
        )

    def test_fail_fast_collects_garbage_after_each_sixteen_cases(self):
        self.row["max_level"] = 17

        def abilities(reference, level):
            return [{"spell_id": level, "spell_level": 1}]

        gc_calls = []

        with patch.object(
            validator.gc, "collect", side_effect=lambda: gc_calls.append("collect")
        ) as collect, patch.object(
            validator.gc, "freeze", side_effect=lambda: gc_calls.append("freeze")
        ) as freeze:
            result = validator.evaluate_reference_cases(
                self.row,
                abilities,
                (),
                12,
                fail_fast=True,
                case_runner=lambda *args: {"status": "validated"},
            )

        self.assertEqual(len(result), 17)
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(freeze.call_count, 1)
        self.assertEqual(gc_calls, ["collect", "freeze"])

    def test_default_mode_does_not_collect_garbage_per_batch(self):
        self.row["max_level"] = 33

        def abilities(reference, level):
            return [{"spell_id": level, "spell_level": 1}]

        with patch.object(validator.gc, "collect") as collect, patch.object(
            validator.gc, "freeze"
        ) as freeze:
            result = validator.evaluate_reference_cases(
                self.row,
                abilities,
                (),
                12,
                case_runner=lambda *args: {"status": "validated"},
            )

        self.assertEqual(len(result), 33)
        collect.assert_not_called()
        freeze.assert_not_called()

    def test_fixture_cache_reuses_only_matching_enemy_and_scenario(self):
        calls = []

        def factory(reference, level, enemy_cell, *, scenario=None):
            calls.append((reference, level, enemy_cell, scenario))
            return (object(), object(), object(), object())

        cache = validator.ReferenceFixtureCache(factory)
        with patch.object(cache, "snapshot", return_value=("stable",)):
            first = cache.get(1297, 1, (-7, -7), scenario={"kind": "base", "x": 1})
            equivalent = cache.get(1297, 1, (-7, -7), scenario={"x": 1, "kind": "base"})
            other_enemy = cache.get(1297, 1, (-6, -7), scenario={"kind": "base"})
            other_scenario = cache.get(
                1297, 1, (-7, -7), scenario={"kind": "wounded_ally"}
            )

        self.assertIs(first, equivalent)
        self.assertIsNot(first, other_enemy)
        self.assertIsNot(first, other_scenario)
        self.assertEqual(len(calls), 3)

    def test_fixture_cache_evicts_when_reference_or_actor_level_changes(self):
        calls = []

        def factory(reference, level, enemy_cell, *, scenario=None):
            calls.append((reference, level))
            return (object(), object(), object(), object())

        cache = validator.ReferenceFixtureCache(factory)
        with patch.object(cache, "snapshot", return_value=("stable",)):
            original = cache.get(1297, 1, (-7, -7))
            same_scope = cache.get(1297, 1, (-7, -7))
            other_level = cache.get(1297, 2, (-7, -7))
            other_reference = cache.get(1298, 2, (-7, -7))

        self.assertIs(original, same_scope)
        self.assertIsNot(original, other_level)
        self.assertIsNot(other_level, other_reference)
        self.assertEqual(calls, [(1297, 1), (1297, 2), (1298, 2)])

    def test_failed_fixture_construction_is_not_cached(self):
        calls = []

        def factory(reference, level, enemy_cell, *, scenario=None):
            calls.append((reference, level))
            if len(calls) == 1:
                raise ValueError("constructor proof unavailable")
            return (object(), object(), object(), object())

        cache = validator.ReferenceFixtureCache(factory)
        with patch.object(cache, "snapshot", return_value=("stable",)):
            with self.assertRaisesRegex(ValueError, "constructor proof"):
                cache.get(1297, 1, (-7, -7))
            succeeded = cache.get(1297, 1, (-7, -7))
            repeated = cache.get(1297, 1, (-7, -7))

        self.assertIs(succeeded, repeated)
        self.assertEqual(calls, [(1297, 1), (1297, 1)])

    def test_cached_fixture_mutation_is_rejected_by_source_snapshot_guard(self):
        fight = types.SimpleNamespace(state="original")
        character = types.SimpleNamespace(state="original")
        monsters = [types.SimpleNamespace(state="original")]
        deck = {"state": "original"}
        context = fight, character, monsters, deck

        def plain(value):
            if hasattr(value, "state"):
                return value.state
            if isinstance(value, (tuple, list)):
                return tuple(plain(item) for item in value)
            if isinstance(value, dict):
                return tuple(sorted((key, plain(item)) for key, item in value.items()))
            return value

        modules = {
            "wakfu_server.combat_geometry_snapshot": types.SimpleNamespace(
                source_snapshot=lambda source: source.state
            ),
            "wakfu_server.fight_checkpoint_store": types.SimpleNamespace(_plain=plain),
        }
        cache = validator.ReferenceFixtureCache(lambda *args, **kwargs: context)

        with patch.dict(sys.modules, modules):
            cached = cache.get(1297, 1, (-7, -7))
            self.assertIs(cached, context)
            fight.state = "mutated"
            with self.assertRaisesRegex(RuntimeError, "mutated cached fixture"):
                cache.verify(context)
            with self.assertRaisesRegex(RuntimeError, "mutated cached fixture"):
                cache.get(1297, 1, (-7, -7))

    @staticmethod
    def plain_test_value(value):
        if hasattr(value, "state"):
            return MonsterActivationReferenceEvaluationTests.plain_test_value(
                value.state
            )
        if isinstance(value, (tuple, list)):
            return tuple(
                MonsterActivationReferenceEvaluationTests.plain_test_value(item)
                for item in value
            )
        if isinstance(value, dict):
            return tuple(
                sorted(
                    (
                        key,
                        MonsterActivationReferenceEvaluationTests.plain_test_value(
                            item
                        ),
                    )
                    for key, item in value.items()
                )
            )
        if value is None or type(value) in (str, int, float, bool):
            return value
        raise TypeError("unsupported fixture metadata")

    def snapshot_modules(self):
        return {
            "wakfu_server.combat_geometry_snapshot": types.SimpleNamespace(
                source_snapshot=lambda source: source.state
            ),
            "wakfu_server.fight_checkpoint_store": types.SimpleNamespace(
                _plain=self.plain_test_value
            ),
        }

    def test_native_bytes_deck_is_attested_and_fixture_reuse_succeeds(self):
        calls = []
        deck = struct.pack(">iiiii", 0, 0, 0, 0, -1)

        def factory(reference, level, enemy_cell, *, scenario=None):
            calls.append((reference, level, enemy_cell))
            return (
                types.SimpleNamespace(state="fight"),
                types.SimpleNamespace(state="character"),
                [types.SimpleNamespace(state="monster")],
                deck,
            )

        cache = validator.ReferenceFixtureCache(factory)
        with patch.dict(sys.modules, self.snapshot_modules()):
            first = cache.get(1297, 1, (-7, -7))
            reused = cache.get(1297, 1, (-7, -7))

        self.assertIs(first, reused)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(deck), 20)

    def test_bytearray_deck_mutation_is_rejected(self):
        context = (
            types.SimpleNamespace(state="fight"),
            types.SimpleNamespace(state="character"),
            [],
            bytearray(struct.pack(">iiiii", 0, 0, 0, 0, -1)),
        )
        cache = validator.ReferenceFixtureCache(lambda *args, **kwargs: context)

        with patch.dict(sys.modules, self.snapshot_modules()):
            cache.get(1297, 1, (-7, -7))
            context[3][0] = 1
            with self.assertRaisesRegex(RuntimeError, "mutated cached fixture"):
                cache.verify(context)

    def test_unsupported_new_fixture_metadata_is_returned_uncached(self):
        calls = []

        def factory(reference, level, enemy_cell, *, scenario=None):
            calls.append((reference, level))
            return (
                types.SimpleNamespace(state="fight"),
                types.SimpleNamespace(state=object()),
                [],
                b"native-deck",
            )

        cache = validator.ReferenceFixtureCache(factory)
        with patch.dict(sys.modules, self.snapshot_modules()):
            first = cache.get(1297, 1, (-7, -7))
            second = cache.get(1297, 1, (-7, -7))

        self.assertIsNot(first, second)
        self.assertEqual(len(cache.entries), 0)
        self.assertEqual(calls, [(1297, 1), (1297, 1)])

    def test_cached_fixture_becoming_unattestable_still_fails_closed(self):
        character = types.SimpleNamespace(state="valid")
        context = (
            types.SimpleNamespace(state="fight"),
            character,
            [],
            b"native-deck",
        )
        cache = validator.ReferenceFixtureCache(lambda *args, **kwargs: context)

        with patch.dict(sys.modules, self.snapshot_modules()):
            cache.get(1297, 1, (-7, -7))
            character.state = object()
            with self.assertRaisesRegex(RuntimeError, "mutated cached fixture"):
                cache.verify(context)

    def test_fail_fast_full_matrix_reuses_cached_fixture_within_level_only(self):
        factory_calls = []
        run_calls = []

        def fake_run_case(
            reference,
            level,
            spell,
            spell_level,
            cells,
            limit,
            *,
            propagate_infrastructure=False,
            fixture_cache=None
        ):
            fixture = fixture_cache.get(reference, level, (-7, -7))
            run_calls.append((reference, level, spell, fixture_cache, fixture))
            return {"status": "validated", "fixture": fixture}

        def factory(reference, level, enemy_cell, *, scenario=None):
            factory_calls.append((reference, level, enemy_cell))
            return (object(), object(), object(), object())

        def abilities(reference, level):
            return [
                {"spell_id": level * 10 + 1, "spell_level": 1},
                {"spell_id": level * 10 + 2, "spell_level": 2},
            ]

        with patch.object(
            validator, "run_case", side_effect=fake_run_case
        ), patch.object(
            validator.ReferenceFixtureCache, "__init__", autospec=True
        ) as cache_init, patch.object(
            validator.ReferenceFixtureCache, "snapshot", return_value=("stable",)
        ):

            def initialize(cache, cache_factory=None):
                cache.factory = factory
                cache.scope = None
                cache.entries = {}

            cache_init.side_effect = initialize
            result = validator.evaluate_reference_cases(
                self.row, abilities, (), 12, fail_fast=True
            )

        self.assertEqual(len(result), 4)
        self.assertEqual(
            [(ref, level, spell) for ref, level, spell, _, _ in run_calls],
            [(1297, 1, 11), (1297, 1, 12), (1297, 2, 21), (1297, 2, 22)],
        )
        self.assertEqual(factory_calls, [(1297, 1, (-7, -7)), (1297, 2, (-7, -7))])
        self.assertIs(run_calls[0][3], run_calls[1][3])
        self.assertIs(run_calls[2][3], run_calls[3][3])
        self.assertIs(run_calls[0][4], run_calls[1][4])
        self.assertIs(run_calls[2][4], run_calls[3][4])
        self.assertIsNot(run_calls[0][4], run_calls[2][4])

    def test_default_evaluation_does_not_create_or_pass_fixture_cache(self):
        calls = []

        def fake_run_case(*args, **kwargs):
            calls.append(kwargs)
            return {"status": "validated"}

        with patch.object(
            validator, "run_case", side_effect=fake_run_case
        ), patch.object(validator, "ReferenceFixtureCache") as cache_type:
            result = validator.evaluate_reference_cases(
                self.row,
                lambda reference, level: [{"spell_id": level, "spell_level": 1}],
                (),
                12,
            )

        self.assertEqual(len(result), 2)
        cache_type.assert_not_called()
        self.assertEqual(
            calls,
            [{"propagate_infrastructure": False, "fixture_cache": None}] * 2,
        )

    def test_case_exception_becomes_pending_with_error_evidence(self):
        def fail(*args):
            raise ValueError("native constructor proof unavailable")

        result = validator.evaluate_reference_cases(
            self.row,
            lambda reference, level: [
                {"spell_id": 110, "spell_level": 3},
                {"spell_id": 111, "spell_level": 4},
            ],
            (),
            12,
            fail_fast=True,
            case_runner=fail,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0],
            {
                "level": 1,
                "spell_id": 110,
                "spell_level": 3,
                "status": "pending",
                "attempts": 0,
                "errors": {"ValueError: native constructor proof unavailable": 1},
                "successful_targets": [],
                "initialization_receipts": [],
            },
        )

    def test_ability_lookup_exception_becomes_pending_without_spell_identity(self):
        def abilities(reference, level):
            raise TypeError("malformed native ability metadata")

        result = validator.evaluate_reference_cases(
            self.row, abilities, (), 12, fail_fast=True, case_runner=lambda *args: None
        )

        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["spell_id"])
        self.assertEqual(result[0]["status"], "pending")
        self.assertEqual(
            result[0]["errors"],
            {"TypeError: malformed native ability metadata": 1},
        )

    def test_infrastructure_failures_propagate(self):
        for error in (
            OSError("database unavailable"),
            RuntimeError("Native preview mutated original fight"),
        ):
            with self.subTest(error=error), self.assertRaises(type(error)):
                validator.evaluate_reference_cases(
                    self.row,
                    lambda reference, level: [{"spell_id": 110, "spell_level": 3}],
                    (),
                    12,
                    fail_fast=True,
                    case_runner=lambda *args, error=error: (_ for _ in ()).throw(error),
                )

    def test_default_mode_keeps_full_evaluation_and_propagates_exceptions(self):
        calls = []

        def abilities(reference, level):
            return [
                {"spell_id": level * 10 + 1, "spell_level": 1},
                {"spell_id": level * 10 + 2, "spell_level": 2},
            ]

        def run(reference, level, spell, spell_level, cells, limit):
            calls.append((level, spell))
            return {"status": "pending" if spell == 11 else "validated"}

        result = validator.evaluate_reference_cases(
            self.row, abilities, (), 12, case_runner=run
        )

        self.assertEqual(len(result), 4)
        self.assertEqual(calls, [(1, 11), (1, 12), (2, 21), (2, 22)])

        with self.assertRaisesRegex(ValueError, "baseline behavior"):
            validator.evaluate_reference_cases(
                self.row,
                abilities,
                (),
                12,
                case_runner=lambda *args: (_ for _ in ()).throw(
                    ValueError("baseline behavior")
                ),
            )


if __name__ == "__main__":
    unittest.main()
