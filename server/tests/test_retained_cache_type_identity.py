"""Exercise real conversion APIs against typed-LRU metaclass collisions."""
import unittest
from wakfu_server import combat_retained_runtime as retained
from wakfu_server.combat_retained_effects import RetainedEffect


class RetainedCacheTypeIdentityTests(unittest.TestCase):
    def setUp(self):
        retained._cached_retained_record.cache_clear()

    def test_same_hash_metaclass_cannot_alias_plain_value_in_either_order(self):
        calls = []

        class IntMeta(type):
            def __eq__(cls, other):
                calls.append("meta_eq")
                return True

            def __hash__(cls):
                calls.append("meta_hash")
                return hash(int)

        class Impostor(int, metaclass=IntMeta):
            pass

        class Owner:
            pass

        original = dict(uid=1, target_id=7, effect_class=330, generic_effect=123)
        for custom_first in (False, True):
            retained._cached_retained_record.cache_clear()
            owner = Owner()
            values = [Impostor(1), 1] if custom_first else [1, Impostor(1)]
            entries = []
            for value in values:
                row = dict(original, uid=value)
                calls.clear()
                expected = RetainedEffect(**row)
                constructor_calls = list(calls)
                calls.clear()
                actual = retained._retained_record(row)
                self.assertIs(type(actual.uid), type(value))
                self.assertEqual(actual, expected)
                self.assertEqual(calls, constructor_calls)
                calls.clear()
                entry = retained._retained_population(owner, {1: row}, [1])[0]
                self.assertIs(type(entry.uid), type(value))
                self.assertEqual(calls, constructor_calls)
                if type(value) is not int:
                    self.assertNotIn(1, retained._RETAINED_POPULATIONS[owner])
                entries.append(entry)
            self.assertIsNot(entries[0], entries[1])
            self.assertEqual(retained._cached_retained_record.cache_info().currsize, 1)

    def test_custom_keys_preserve_constructor_without_warm_type_comparisons(self):
        calls = []

        class StringMeta(type):
            def __eq__(cls, other):
                calls.append("meta_eq")
                return True

            def __hash__(cls):
                calls.append("meta_hash")
                return hash(str)

        class Key(str, metaclass=StringMeta):
            pass

        class Owner:
            pass

        original = dict(uid=1, target_id=7, effect_class=330, generic_effect=123)
        owner = Owner()
        first = retained._retained_population(owner, {1: original}, [1])[0]
        row = {Key(key): value for key, value in original.items()}
        calls.clear()
        expected = RetainedEffect(**row)
        constructor_calls = list(calls)
        calls.clear()
        actual = retained._retained_record(row)
        self.assertEqual(actual, expected)
        self.assertEqual(calls, constructor_calls)
        calls.clear()
        second = retained._retained_population(owner, {1: row}, [1])[0]
        self.assertEqual(second, expected)
        self.assertIsNot(second, first)
        self.assertEqual(calls, constructor_calls)
        self.assertNotIn(1, retained._RETAINED_POPULATIONS[owner])

    def test_warm_reordered_rows_bool_aliases_and_unsupported_values_stay_distinct(
        self,
    ):
        class Owner:
            pass

        owner = Owner()
        row = dict(uid=1, target_id=7, effect_class=330, generic_effect=123)
        first = retained._retained_population(owner, {1: row}, [1])[0]
        reordered = dict(reversed(tuple(row.items())))
        self.assertIs(
            retained._retained_population(owner, {1: reordered}, [1])[0], first
        )
        changed = dict(row, target_id=True)
        boolean = retained._retained_population(owner, {1: changed}, [1])[0]
        self.assertIs(type(boolean.target_id), bool)
        self.assertIs(type(first.target_id), int)
        for value in ([], "x" * 129, 2**65):
            changed = dict(row, target_id=value)
            self.assertEqual(
                retained._retained_record(changed), RetainedEffect(**changed)
            )
            self.assertEqual(
                retained._retained_population(owner, {1: changed}, [1])[0],
                RetainedEffect(**changed),
            )
            self.assertNotIn(1, retained._RETAINED_POPULATIONS[owner])
        with self.assertRaises(TypeError):
            retained._retained_record(dict(row, unknown=1))
