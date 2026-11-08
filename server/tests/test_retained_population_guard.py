from copy import deepcopy
import gc
import unittest
from unittest.mock import patch
import weakref
from wakfu_server import combat_retained_runtime as retained
from wakfu_server.combat_retained_effects import RetainedEffect


class Owner:
    pass


class PopulationGuardTests(unittest.TestCase):
    def setUp(self):
        self.owner = Owner()
        self.row = dict(
            uid=1,
            target_id=2,
            effect_class=310,
            generic_effect=-1,
            definition_type=0,
            container_present=False,
            state_dispellable=False,
            state_unremovable=True,
        )

    def read(self, row):
        return retained._retained_population(self.owner, {1: row}, [1])[0]

    def test_order_independent_warm_values_and_type_changes(self):
        first = self.read(self.row)
        self.assertIs(self.read(dict(reversed(tuple(self.row.items())))), first)
        for field, value in [
            ("state_unremovable", 1),
            ("definition_type", False),
            ("target_id", 3),
            ("container_present", None),
        ]:
            changed = dict(self.row, **{field: value})
            actual = self.read(changed)
            self.assertEqual(actual, RetainedEffect(**changed))
            self.assertIs(type(getattr(actual, field)), type(value))
            self.assertIsNot(actual, first)
            self.assertEqual(first, RetainedEffect(**self.row))
            self.read(self.row)

    def test_noncanonical_keys_and_unhashable_values_use_constructor(self):
        self.read(self.row)

        class Key(str):
            pass

        changed = {Key(key): value for key, value in self.row.items()}
        for altered in [
            changed,
            dict(self.row, target_id=[]),
            dict(self.row, target_id=2**100),
        ]:
            with patch.object(
                retained, "_retained_record", wraps=retained._retained_record
            ) as convert:
                self.assertEqual(self.read(altered), RetainedEffect(**altered))
                self.assertEqual(convert.call_count, 1)
            self.read(self.row)

    def test_added_removed_invalid_fields_and_missing_order_preserve_errors(self):
        self.read(self.row)
        for altered in [
            dict(self.row, unknown=1),
            {key: value for key, value in self.row.items() if key != "uid"},
        ]:
            with self.assertRaises(TypeError):
                self.read(altered)
        with self.assertRaises(KeyError):
            retained._retained_population(self.owner, {}, [1])
        self.assertEqual(self.read(self.row), RetainedEffect(**self.row))

    def test_order_and_duplicate_uids_and_empty_population(self):
        rows = {1: self.row, 2: dict(self.row, uid=2)}
        actual = retained._retained_population(self.owner, rows, [2, 1, 2])
        self.assertEqual([entry.uid for entry in actual], [2, 1, 2])
        self.assertEqual(retained._retained_population(self.owner, rows, []), [])

    def test_weak_owner_and_clone_do_not_share_population_authority(self):
        first = self.read(self.row)
        clone = deepcopy(self.owner)
        self.assertNotIn(clone, retained._RETAINED_POPULATIONS)
        self.assertFalse(vars(self.owner))
        ref = weakref.ref(self.owner)
        del self.owner
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(first.uid, 1)
