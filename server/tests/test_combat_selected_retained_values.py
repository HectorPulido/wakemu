"""Selected frozen values remain content-checked, independent of authority."""
import gc
import unittest
import weakref
from unittest.mock import patch
from wakfu_server import combat_retained_runtime as retained
from wakfu_server.combat_selected_retained_values import SelectedRetainedValues


class SelectedValueTests(unittest.TestCase):
    class Owner:
        pass

    def test_borrowed_full_population_subsets_mutations_and_fresh_uids(self):
        owner = self.Owner()
        rows = {
            i: dict(
                uid=i,
                target_id=7,
                effect_class=400,
                generic_effect=100,
                state_unremovable=False,
            )
            for i in (1, 2)
        }
        full = retained._retained_population(owner, rows, [1, 2])
        previous = retained._RETAINED_POPULATIONS[owner]
        values = SelectedRetainedValues(owner)
        with patch.object(
            retained, "_retained_record", wraps=retained._retained_record
        ) as convert:
            for _ in range(3):
                self.assertIs(values.read(owner, 1, rows[1]), full[0])
                self.assertIs(values.read(owner, 2, rows[2]), full[1])
            self.assertEqual(convert.call_count, 0)
            rows[1]["generic_effect"] = 101
            self.assertEqual(values.read(owner, 1, rows[1]).generic_effect, 101)
            rows[1]["state_unremovable"] = 0
            self.assertIs(type(values.read(owner, 1, rows[1]).state_unremovable), int)
            rows[3] = dict(rows[1], uid=3)
            self.assertEqual(values.read(owner, 3, rows[3]).uid, 3)
            self.assertEqual(convert.call_count, 3)
        self.assertIs(retained._RETAINED_POPULATIONS[owner], previous)
        self.assertEqual(set(previous), {1, 2})
        self.assertFalse(previous[1][0]["state_unremovable"])
        pointer = weakref.ref(owner)
        del owner
        gc.collect()
        self.assertIsNone(pointer())

    def test_custom_values_owner_mismatch_and_metadata_remain_fresh(self):
        owner, other = self.Owner(), self.Owner()
        row = dict(uid=1, target_id=7, effect_class=400, generic_effect=100)
        values = SelectedRetainedValues(owner)
        values.read(owner, 1, row)

        class EqualType(type):
            def __eq__(self, other):
                return True

            __hash__ = type.__hash__

        class Custom(metaclass=EqualType):
            def __eq__(self, other):
                return True

        custom = Custom()
        row["generic_effect"] = custom
        with patch.object(
            retained, "_retained_record", wraps=retained._retained_record
        ) as convert:
            actual = values.read(owner, 1, row)
            self.assertIs(actual.generic_effect, custom)
            values.read(other, 1, row)
            self.assertEqual(convert.call_count, 2)
        self.assertNotIn(1, values.current)
        row["generic_effect"] = 100
        row["unknown_field"] = True
        with self.assertRaises(TypeError):
            values.read(owner, 1, row)


if __name__ == "__main__":
    unittest.main()
