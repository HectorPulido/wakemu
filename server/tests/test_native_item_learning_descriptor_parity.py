"""Complete DB joins/counts for the nine original item-learning action classes."""
from postgres_case import PostgresCase


class NativeItemLearningDescriptorParityTests(PostgresCase):
    def test_every_seeded_action_has_one_active_native_class_action_and_no_criteria(
        self,
    ):
        expected = {
            "bHv": ("native_mimisymbic_learning_actions", 1),
            "bIA": ("native_ranch_building_learning_actions", 119),
            "bIB": ("native_recipe_learning_actions", 54),
            "bIs": ("native_title_learning_actions", 467),
            "bIt": ("native_cosmetic_learning_actions", 1234),
            "bIv": ("native_bag_view_learning_actions", 91),
            "bIw": ("native_emote_learning_actions", 314),
            "bIx": ("native_furniture_learning_actions", 1338),
            "bIz": ("native_recipe_learning_actions", 78),
        }
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        active = _rules()
        total = 0
        for native_class, (table, count) in expected.items():
            with self.subTest(native_class=native_class):
                with self.store.connection() as db:
                    if native_class == "bIB" or native_class == "bIz":
                        rows = db.execute(
                            "SELECT item_ref,action_id,native_class,has_criteria "
                            "FROM native_recipe_learning_actions WHERE native_class=%s ORDER BY item_ref",
                            (native_class,),
                        ).fetchall()
                    else:
                        criteria = "FALSE" if native_class == "bIA" else "has_criteria"
                        rows = db.execute(
                            f"SELECT item_ref,action_id,{criteria} AS has_criteria "
                            f"FROM {table} ORDER BY item_ref"
                        ).fetchall()
                self.assertEqual(len(rows), count)
                total += len(rows)
                for row in rows:
                    descriptor = active.get(row["item_ref"])
                    self.assertIsNotNone(descriptor, row["item_ref"])
                    self.assertEqual(descriptor.get("use_action_class"), native_class)
                    self.assertEqual(descriptor.get("use_action_id"), row["action_id"])
                    # Legacy publication metadata marks title 14199 true due to
                    # EXCHANGE criteria. Native GIVE_TITLE has no USE criterion;
                    # the title handler deliberately validates its typed row.
                    if native_class == "bIs" and row["item_ref"] == 14199:
                        self.assertTrue(descriptor.get("use_has_criteria"))
                    else:
                        self.assertIs(descriptor.get("use_has_criteria"), False)
                    self.assertIs(row["has_criteria"], False)

        self.assertEqual(total, 3696)

    def test_full_furniture_and_ranch_mapping_rows_are_well_formed(self):
        with self.store.connection() as db:
            furniture = db.execute(
                "SELECT item_ref,action_id,learned_refs,template_ids,has_criteria "
                "FROM native_furniture_learning_actions ORDER BY item_ref"
            ).fetchall()
            ranch = db.execute(
                "SELECT item_ref,action_id,profession_id,minimum_level,building_refs,"
                "native_class,source_sha256 FROM native_ranch_building_learning_actions "
                "ORDER BY item_ref"
            ).fetchall()

        self.assertEqual(len(furniture), 1338)
        self.assertEqual(len(ranch), 119)
        for row in furniture:
            self.assertFalse(row["has_criteria"])
            self.assertTrue(row["learned_refs"])
            self.assertEqual(len(row["learned_refs"]), len(row["template_ids"]))
            self.assertTrue(
                all(type(value) is int and value > 0 for value in row["learned_refs"])
            )
            self.assertTrue(
                all(type(value) is int and value > 0 for value in row["template_ids"])
            )
        for row in ranch:
            self.assertEqual(row["native_class"], "bIA")
            self.assertGreater(row["profession_id"], 0)
            self.assertGreaterEqual(row["minimum_level"], 0)
            self.assertTrue(row["building_refs"])
            self.assertTrue(
                all(type(value) is int and value > 0 for value in row["building_refs"])
            )
            self.assertEqual(len(row["source_sha256"]), 64)
