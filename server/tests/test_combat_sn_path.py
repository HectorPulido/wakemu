import unittest
from contextlib import contextmanager
from wakfu_server.combat_sn_path import (
    NativePhysicalSurface,
    NativeSnColumns,
    NativeSnPathAuthority,
    native_sm_transitions,
)
from wakfu_server.combat_conditions import UnknownCondition


def surface(z=0, *, bld=0, ble=0, blf=0, thickness=1, through=False):
    return NativePhysicalSurface(z, bld, ble, blf, thickness, through)


class NativeSnPathTests(unittest.TestCase):
    def path(
        self,
        *,
        source=(0, 0, 0),
        target=(2, 0, 0),
        columns=None,
        qi_z=lambda x, y: False,
        **options
    ):
        rows = {(x, 0): (surface(),) for x in range(3)} if columns is None else columns
        return NativeSnPathAuthority(
            source=source,
            target=target,
            height=6,
            radius=options.pop("radius", 0),
            jump=1,
            physical_column=lambda x, y: rows.get((x, y)),
            qi_z=qi_z,
            is_qi=True,
            target_obstacle_present=options.pop("target_obstacle_present", False),
            **options,
        )

    def test_selected_path_masks_visit_source_and_intermediate_not_destination(self):
        visited = []
        self.assertTrue(
            self.path(qi_z=lambda x, y: visited.append((x, y)) or x == 2)(True)
        )
        self.assertEqual(visited, [(0, 0), (1, 0)])
        self.assertFalse(self.path(qi_z=lambda x, y: x == 0)(True))
        self.assertFalse(self.path(qi_z=lambda x, y: x == 1)(True))
        self.assertTrue(self.path(qi_z=lambda x, y: True)(False))

    def test_actual_source_last_duplicate_altitude_is_used(self):
        rows = {
            (0, 0): (surface(ble=64), surface(ble=-128)),
            (1, 0): (surface(ble=-128),),
        }
        self.assertTrue(self.path(target=(1, 0, 0), columns=rows)(False))

    def test_destination_altitude_is_not_rechecked(self):
        self.assertTrue(self.path(target=(2, 0, 123))(False))

    def test_same_xy_different_z_requires_only_source_floor(self):
        self.assertTrue(self.path(target=(0, 0, 123))(True))
        self.assertFalse(self.path(target=(0, 0, 123), columns={})(True))

    def test_identical_full_cell_returns_true_without_physical_columns(self):
        self.assertTrue(self.path(target=(0, 0, 0), columns={})(True))

    def test_missing_floor_or_column_and_noncardinal_are_false(self):
        self.assertFalse(self.path(source=(0, 0, 1))(False))
        self.assertFalse(self.path(columns={(0, 0): (surface(),)})(False))
        self.assertFalse(self.path(target=(2, 1, 0))(False))

    def test_radius_does_not_add_unproved_footprint_checks(self):
        self.assertTrue(self.path(radius=3)(False))

    def test_exclusion_scope_restores_on_unknown_authority(self):
        events = []

        @contextmanager
        def exclude():
            events.append("exclude")
            try:
                yield
            finally:
                events.append("restore")

        def unknown(x, y):
            raise UnknownCondition("Missing current QI masks")

        path = self.path(
            qi_z=unknown, target_obstacle_present=True, target_exclusion=exclude
        )
        with self.assertRaises(UnknownCondition):
            path(True)
        self.assertEqual(events, ["exclude", "restore"])
        events.clear()
        self.assertTrue(
            self.path(target_obstacle_present=True, target_exclusion=exclude)(False)
        )
        self.assertEqual(events, ["exclude", "restore"])

    def test_actual_target_identity_and_exclusion_cannot_default_to_absence(self):
        with self.assertRaises(UnknownCondition):
            NativeSnPathAuthority(
                source=None,
                target=None,
                height=6,
                radius=0,
                jump=1,
                physical_column=lambda x, y: None,
            )
        with self.assertRaises(UnknownCondition):
            self.path(target_obstacle_present=True)

    def test_unknown_physical_rows_and_mask_result_remain_unknown(self):
        with self.assertRaises(UnknownCondition):
            self.path(columns={(0, 0): ((0, 0),)})(False)
        with self.assertRaises(UnknownCondition):
            self.path(qi_z=lambda x, y: None)(True)

    def test_sm_jump_exception_and_ceiling_obstruction(self):
        self.assertEqual(
            native_sm_transitions(0, [surface()], [surface(3)], height=6, jump=1), ()
        )
        self.assertEqual(
            native_sm_transitions(
                0, [surface(blf=64)], [surface(3, blf=64)], height=6, jump=1
            ),
            (0,),
        )
        self.assertEqual(
            native_sm_transitions(
                0, [surface(), surface(5)], [surface(1)], height=6, jump=1
            ),
            (),
        )

    def test_multi_surface_native_candidate_flag_quirk_is_preserved(self):
        # The native multi-surface branch reads candidate.bLf during the source
        # clearance loop, unlike its single-surface branch's overhead flag.
        start = [surface(), surface(3, through=True)]
        single = [surface(1)]
        multiple = [surface(1), surface(20)]
        self.assertEqual(
            native_sm_transitions(0, start, single, height=6, jump=1), (0,)
        )
        self.assertEqual(
            native_sm_transitions(0, start, multiple, height=6, jump=1), ()
        )

    def test_native_fixed_transition_buffer_overflow(self):
        with self.assertRaises(IndexError):
            native_sm_transitions(
                0,
                [surface(blf=64)],
                [surface(i * 10, blf=64) for i in range(33)],
                height=0,
                jump=0,
            )

    def test_signed_physical_fields_reject_boolean_and_out_of_bounds(self):
        with self.assertRaises(ValueError):
            NativePhysicalSurface(True, 0, 0, 0, 1, False)
        with self.assertRaises(ValueError):
            NativePhysicalSurface(0, 128, 0, 0, 1, False)


class NativeSnColumnsTests(unittest.TestCase):
    def data(self):
        return dict(
            schema="native-Sn-Vy-columns-v1",
            map_id=1,
            source_sha256="a" * 64,
            chunks=[
                dict(
                    x=0,
                    y=0,
                    width=18,
                    height=18,
                    columns=[[0, 0, [[0, 0, 0, 0, 1, False]]]],
                )
            ],
        )

    def test_complete_native_columns_distinguish_empty_from_missing_chunk(self):
        columns = NativeSnColumns(self.data(), map_id=1, source_sha256="a" * 64)
        self.assertEqual(columns.column(0, 0), (surface(),))
        self.assertEqual(columns.column(1, 0), ())
        self.assertIsNone(columns.column(18, 0))

    def test_matching_topology_provenance_and_signed_fields_are_required(self):
        with self.assertRaises(ValueError):
            NativeSnColumns(self.data(), map_id=2, source_sha256="a" * 64)
        data = self.data()
        data["chunks"][0]["columns"][0][2][0][1] = 128
        with self.assertRaises(ValueError):
            NativeSnColumns(data, map_id=1, source_sha256="a" * 64)

    def test_overlapping_chunks_are_rejected(self):
        data = self.data()
        data["chunks"].append(dict(x=1, y=0, width=18, height=18, columns=[]))
        with self.assertRaises(ValueError):
            NativeSnColumns(data, map_id=1, source_sha256="a" * 64)
