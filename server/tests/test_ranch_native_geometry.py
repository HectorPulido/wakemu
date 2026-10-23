import unittest

from wakfu_server import ranch_native_geometry as geometry


class RanchNativeGeometryTests(unittest.TestCase):
    def test_initial_sectors_and_floor_cell_resolution_use_native_gxf(self):
        self.assertEqual((1, 2, 3, 4), geometry.initial_sectors(1))
        self.assertEqual(1, geometry.sector_for_cell(1, 0, 0))
        self.assertEqual(2, geometry.sector_for_cell(1, 0, -36))
        self.assertEqual(3, geometry.sector_for_cell(1, -36, -18))
        self.assertEqual(4, geometry.sector_for_cell(1, -36, -54))
        self.assertIsNone(geometry.sector_for_cell(1, 18, 0))

    def test_static_gxg_slots_are_not_account_owned_instances(self):
        slots = geometry.building_slots(1)
        self.assertEqual((1, 2, 3, 4), tuple(row["id"] for row in slots))
        self.assertTrue(all("uid" not in row for row in slots))

    def test_policy_must_match_native_sector_topology(self):
        rows = geometry.native_biome(1)["terrain_areas"]
        self.assertEqual((1, 2, 3, 4), geometry.validate_initial_area_policy(1, rows))
        with self.assertRaisesRegex(ValueError, "differ from original"):
            geometry.validate_initial_area_policy(1, rows[:-1])

    def test_building_placement_uses_pinned_native_collision_mesh(self):
        from wakfu_server import haven_ranch_building_catalog as catalog

        definition = catalog.definition(33)
        selected = catalog.mode(definition)
        view = selected["epP"][0]
        result = geometry.validate_building_placement(
            definition,
            selected["p"],
            0,
            view["epS"],
            0,
            0,
            biome_id=1,
            existing_buildings=(),
            occupied_cells=(),
        )
        self.assertEqual(1, result["sector_id"])
        self.assertEqual(((0, 0),), result["footprint_cells"])

    def test_every_exported_native_view_resolves_to_its_exact_original_shape(self):
        from wakfu_server import haven_ranch_building_catalog as catalog

        footprints = geometry._footprints()
        self.assertEqual(269, len(footprints))
        for (reference, mode_id, kind, selector), shape in footprints.items():
            definition = catalog.definition(reference)
            native_view = catalog.view(definition, mode_id, kind, selector)
            self.assertEqual(native_view["eki"], shape["view_id"])
            self.assertTrue(shape["cells"])
            x_min, x_max, y_min, y_max = shape["bounds"]
            self.assertTrue(
                all(
                    x_min <= x <= x_max and y_min <= y <= y_max
                    for x, y in shape["cells"]
                )
            )

    def test_original_vb_blocked_cells_and_allowed_cells(self):
        from wakfu_server import haven_ranch_building_catalog as catalog

        definition = catalog.definition(33)
        selected = catalog.mode(definition)
        view = selected["epP"][0]
        # Both points belong to native fBm area 2. VB.aJ blocks only the first.
        with self.assertRaisesRegex(ValueError, "VB terrain blocks"):
            geometry.validate_building_placement(
                definition,
                selected["p"],
                0,
                view["epS"],
                0,
                -31,
                biome_id=1,
                existing_buildings=(),
                occupied_cells=(),
            )
        result = geometry.validate_building_placement(
            definition,
            selected["p"],
            0,
            view["epS"],
            0,
            -36,
            biome_id=1,
            existing_buildings=(),
            occupied_cells=(),
        )
        self.assertEqual(2, result["sector_id"])

    def test_native_masks_reject_building_and_scene_object_overlap(self):
        from wakfu_server import haven_ranch_building_catalog as catalog

        definition = catalog.definition(49)
        selected = catalog.mode(definition)
        view = selected["epP"][0]
        kwargs = dict(
            biome_id=1,
            existing_buildings=(),
            definition=definition,
            mode_id=selected["p"],
            view_kind=0,
            view_value=view["epS"],
            x=0,
            y=0,
        )
        with self.assertRaisesRegex(ValueError, "overlaps an existing object"):
            geometry.validate_building_placement(**kwargs, occupied_cells=((2, 3),))
        existing = dict(
            uid=77,
            building_ref=49,
            mode_id=selected["p"],
            view_kind=0,
            view_value=view["epS"],
            x=0,
            y=0,
            sector_id=1,
        )
        with self.assertRaisesRegex(ValueError, "overlaps an existing object"):
            geometry.validate_building_placement(
                **{**kwargs, "existing_buildings": (existing,)},
                occupied_cells=(),
            )

    def test_newly_resolved_native_views_have_exact_placement_shapes(self):
        from wakfu_server import haven_ranch_building_catalog as catalog

        for reference in (58, 63):
            definition = catalog.definition(reference)
            selected = catalog.mode(definition)
            view = selected["epP"][0]
            result = geometry.validate_building_placement(
                definition,
                selected["p"],
                0,
                view["epS"],
                0,
                -36,
                biome_id=1,
                existing_buildings=(),
                occupied_cells=(),
            )
            self.assertEqual(2, result["sector_id"])
            self.assertEqual(((0, -36),), result["footprint_cells"])

    def test_special_native_view_and_attached_scene_objects(self):
        from wakfu_server import haven_ranch_building_catalog as catalog

        special = catalog.definition(6)
        mode = catalog.mode(special)
        selector = mode["epQ"][0]["epL"]
        result = geometry.validate_building_placement(
            special,
            mode["p"],
            1,
            selector,
            0,
            0,
            biome_id=1,
            existing_buildings=(),
            occupied_cells=(),
        )
        self.assertEqual(((0, 0),), result["footprint_cells"])

        from wakfu_server import haven_ranch_building_catalog as catalog

        attached_definition = catalog.definition(140)
        attached_mode = catalog.mode(attached_definition)
        attached_view = attached_mode["epP"][0]
        attached = dict(
            uid=9,
            building_ref=140,
            mode_id=attached_mode["p"],
            view_kind=0,
            view_value=attached_view["epS"],
            x=0,
            y=0,
        )
        with self.assertRaisesRegex(ValueError, "attached scene-object producer"):
            geometry.changed_scene_object_records(1, (), (attached,))

    def test_native_removal_retires_attached_children_without_fabricating_delta(self):
        from wakfu_server import haven_ranch_building_catalog as catalog

        definition = catalog.definition(140)
        mode = catalog.mode(definition)
        selected = mode["epP"][0]
        attached = dict(
            uid=9,
            building_ref=140,
            mode_id=mode["p"],
            view_kind=0,
            view_value=selected["epS"],
            x=0,
            y=0,
        )
        self.assertEqual((), geometry.changed_scene_object_records(1, (attached,), ()))

    def test_native_scene_object_delta_stays_empty_without_attached_objects(self):
        before = [
            {
                "uid": 7,
                "building_ref": 33,
                "mode_id": 1,
                "view_kind": 0,
                "view_value": 1,
                "x": 0,
                "y": 0,
            }
        ]
        after = [{**before[0], "x": 1}]
        self.assertEqual((), geometry.changed_scene_object_records(1, before, after))

    def test_native_adjacency_recomputes_views_without_mutating_owned_fields(self):
        before = [
            dict(
                uid=77,
                account_id=4,
                biome_id=1,
                sector_id=2,
                building_ref=6,
                mode_id=1,
                view_kind=1,
                view_value=85,
                x=0,
                y=-36,
                contained_item_ref=-1,
                contained_quantity=0,
                revision=4,
            ),
            dict(
                uid=78,
                account_id=4,
                biome_id=1,
                sector_id=2,
                building_ref=8,
                mode_id=1,
                view_kind=1,
                view_value=119,
                x=1,
                y=-36,
                contained_item_ref=-1,
                contained_quantity=0,
                revision=9,
            ),
        ]
        after = geometry.recompute_adjacent_building_views(1, before)
        self.assertEqual((87, 119), tuple(row["view_value"] for row in after))
        for original, updated in zip(before, after):
            for key in original.keys() - {"view_kind", "view_value"}:
                self.assertEqual(original[key], updated[key])
        self.assertEqual(85, before[0]["view_value"])


if __name__ == "__main__":
    unittest.main()
