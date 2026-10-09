import unittest

from wakfu_server.combat_global_event_iterator import native_global_event_iterator


class NativeGlobalEventIteratorTests(unittest.TestCase):
    def iterator(self, eligible=lambda identity: True, **overrides):
        args = dict(
            fighter_order=(9, 2),
            area_order=(-4, -1),
            extra_order=(8,),
            eligible=eligible,
        )
        args.update(overrides)
        return native_global_event_iterator(**args)

    def test_native_segments_are_concatenated_without_sorting(self):
        self.assertEqual(list(self.iterator()), [9, 2, -4, -1, 8])

    def test_live_membership_observes_reaction_removal(self):
        active = {9, 2, -4, -1, 8}
        iterator = self.iterator(eligible=lambda identity: identity in active)
        self.assertEqual(next(iterator), 9)
        active.remove(-4)
        self.assertEqual(list(iterator), [2, -1, 8])

    def test_duplicate_pv_in_distinct_native_segments_is_not_deduplicated(self):
        self.assertEqual(list(self.iterator(extra_order=(9,))), [9, 2, -4, -1, 9])

    def test_caster_only_native_mode_bypasses_membership(self):
        def forbidden(identity):
            raise AssertionError("fcd must not run in rRo caster-only mode")

        self.assertEqual(
            list(self.iterator(eligible=forbidden, caster_only=True, caster_id=-4)),
            [-4],
        )

    def test_unknown_sequence_is_not_inferred_from_roster(self):
        with self.assertRaisesRegex(ValueError, "Captured native PV"):
            list(self.iterator(area_order=None))

    def test_unknown_membership_is_not_false(self):
        with self.assertRaisesRegex(ValueError, "membership result"):
            list(self.iterator(eligible=lambda identity: None))
