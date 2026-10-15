"""Real PostgreSQL capacity, metadata isolation and all-or-nothing reward grants."""
from postgres_case import PostgresCase
from wakfu_server.achievements import rewards
from wakfu_server.inventory_move import ACQUISITION_STACKS


class AchievementRewardCapacityPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("capacity-reward-owner", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Capacity Reward")
        from wakfu_server.inventory_elements import create
        from wakfu_server.combat_drop_delivery import _template_bound

        self.reference = next(
            ref
            for ref, rule in ACQUISITION_STACKS.items()
            if rule["minimal_mergeable"]
            and 2 < rule["maximum"] <= 32767
            and create(ref) is None
            and not _template_bound(ref)
        )

    def fill(self, db, quantity=1, *, all_bags=False):
        containers = db.execute(
            "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY kind",
            (self.character["id"],),
        ).fetchall()
        db.execute(
            "DELETE FROM inventory_items WHERE character_id=%s", (self.character["id"],)
        )
        for bag in containers if all_bags else containers[:1]:
            db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) SELECT %s,%s,%s,%s,s FROM generate_series(0,%s) s",
                (
                    self.character["id"],
                    self.reference,
                    quantity,
                    bag["uid"],
                    bag["capacity"] - 1,
                ),
            )
        return containers[0]

    def test_full_base_uses_real_ordinary_extra_bag(self):
        with self.store.connection() as db:
            self.fill(db)
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=1",
                (self.character["id"],),
            ).fetchone()["uid"]
            # Nonmergeable single-unit rewards cannot use occupied base slots.
            from unittest.mock import patch

            with patch.dict(
                ACQUISITION_STACKS,
                {
                    self.reference: dict(
                        ACQUISITION_STACKS[self.reference], minimal_mergeable=False
                    )
                },
            ):
                rewards.grant(
                    db, self.store, self.character, dict(aeV=5, ckl=[self.reference, 1])
                )
            self.assertEqual(
                db.execute(
                    "SELECT SUM(quantity) AS q FROM inventory_items WHERE container=%s",
                    (bag,),
                ).fetchone()["q"],
                1,
            )

    def test_full_base_merges_and_overflow_failure_is_atomic(self):
        maximum = ACQUISITION_STACKS[self.reference]["maximum"]
        with self.store.connection() as db:
            self.fill(db, maximum, all_bags=True)
            first = db.execute(
                "SELECT uid FROM inventory_items WHERE character_id=%s ORDER BY uid LIMIT 1",
                (self.character["id"],),
            ).fetchone()["uid"]
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s", (first,)
            )
            with self.assertRaises(rewards.RewardCapacity):
                rewards.grant(
                    db, self.store, self.character, dict(aeV=5, ckl=[self.reference, 2])
                )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (first,)
                ).fetchone()["quantity"],
                maximum - 1,
            )
            rewards.grant(
                db, self.store, self.character, dict(aeV=5, ckl=[self.reference, 1])
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (first,)
                ).fetchone()["quantity"],
                maximum,
            )

    def test_different_binding_does_not_merge(self):
        from wakfu_server.combat_drop_delivery import _template_bound

        with self.store.connection() as db:
            self.fill(db)
            # 2021 is an unbound resource; mark every existing unit bound.
            self.assertFalse(_template_bound(self.reference))
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) SELECT uid,true,reference FROM inventory_items WHERE character_id=%s",
                (self.character["id"],),
            )
            rewards.grant(
                db, self.store, self.character, dict(aeV=5, ckl=[self.reference, 1])
            )
            self.assertEqual(
                db.execute(
                    "SELECT SUM(quantity) AS q FROM inventory_items WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["q"],
                31,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS n FROM inventory_item_bindings b JOIN inventory_items i USING(uid) WHERE i.character_id=%s AND b.bound AND i.quantity=1",
                    (self.character["id"],),
                ).fetchone()["n"],
                30,
            )

    def test_mount_reward_keeps_individual_state_and_template_binding(self):
        from wakfu_server.combat_drop_delivery import _template_bound, _binding_rows

        with self.store.connection() as db:
            reference = next(
                row["reference"]
                for row in db.execute(
                    "SELECT reference FROM mount_models ORDER BY reference"
                )
                if row["reference"] in ACQUISITION_STACKS
            )
            rewards.grant(
                db, self.store, self.character, dict(aeV=5, ckl=[reference, 2])
            )
            items = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=%s",
                    (self.character["id"],),
                )
            ]
            self.assertEqual([row["quantity"] for row in items], [1, 1])
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS n FROM inventory_mounts WHERE uid=ANY(%s)",
                    ([row["uid"] for row in items],),
                ).fetchone()["n"],
                2,
            )
            bindings = _binding_rows(db, items)
            self.assertTrue(
                all(
                    bindings.get(row["uid"], False) == _template_bound(reference)
                    for row in items
                )
            )

    def test_element_metadata_blocks_resource_merge_without_being_discarded(self):
        with self.store.connection() as db:
            self.fill(db)
            db.execute(
                "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) SELECT uid,2,0 FROM inventory_items WHERE character_id=%s",
                (self.character["id"],),
            )
            rewards.grant(
                db, self.store, self.character, dict(aeV=5, ckl=[self.reference, 1])
            )
            self.assertEqual(
                db.execute(
                    "SELECT SUM(quantity) AS q FROM inventory_items WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["q"],
                31,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS n FROM inventory_item_elements e JOIN inventory_items i USING(uid) WHERE i.character_id=%s AND e.damage_elements=2",
                    (self.character["id"],),
                ).fetchone()["n"],
                30,
            )
