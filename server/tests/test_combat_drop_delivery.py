import struct
import unittest

from postgres_case import PostgresCase

from wakfu_server.combat_drops import resolve
from wakfu_server.combat_drops import native_drop_catalog
from wakfu_server.combat_drop_delivery import (
    apply,
    bulk_transfer,
    claim,
    discard,
    decode_bulk_transfer,
    decode_claim,
    temporary_section,
    temporary_update,
)
from wakfu_server.combat_drop_delivery import _effective_bound, _save_binding
from wakfu_server.wire import proto_fields
from wakfu_server.inventory_move import STACKS
from wakfu_server.exchange_rules import ITEMS
from wakfu_server.inventory_bag_rules import RULES as BAG_RULES


class GuaranteedDraw:
    def __call__(self, upper):
        return 0


class CombatDropDeliveryTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account_id = self.store.register("drop-delivery", "local-password")["id"]
        self.character = self.store.create_character(self.account_id, "LootWinner")
        self.character_id = self.character["id"]
        self.generation = self.store.begin_session(self.account_id)
        self.store.select_character(self.account_id, self.generation, self.character_id)
        with self.store.connection() as db:
            self.fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (self.fight_id, self.character_id, self.account_id),
            )
            db.execute(
                "INSERT INTO fight_rewards(generation,fight_id,character_id,account_id,xp,kamas,created_at,"
                "start_xp,end_xp,start_level,end_level) VALUES(%s,%s,%s,%s,0,0,CURRENT_TIMESTAMP,0,0,1,1)",
                (self.generation, self.fight_id, self.character_id, self.account_id),
            )

    def _resolve(self, db, rng=None, monster_reference=1, fight_context=None):
        return resolve(
            self.store,
            db,
            account_id=self.account_id,
            generation=self.generation,
            character_id=self.character_id,
            fight_id=self.fight_id,
            monsters=[{"actor_id": -987654, "reference": monster_reference}],
            prospecting_bonus=0,
            can_loot=True,
            fight_context={} if fight_context is None else fight_context,
            rng=GuaranteedDraw() if rng is None else rng,
        )

    def _second_finished_fight(self, db):
        fight_id = db.execute(
            "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
        ).fetchone()["id"]
        db.execute(
            "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
            "VALUES(%s,%s,%s,0)",
            (fight_id, self.character_id, self.account_id),
        )
        db.execute(
            "INSERT INTO fight_rewards(generation,fight_id,character_id,account_id,xp,kamas,created_at,"
            "start_xp,end_xp,start_level,end_level) VALUES(%s,%s,%s,%s,0,0,CURRENT_TIMESTAMP,0,0,1,1)",
            (self.generation, fight_id, self.character_id, self.account_id),
        )
        return fight_id

    def _guarded_native_drop(self, *, identified=False, equipped=False):
        """A real monster-1 drop and native stackable/socketable reference."""
        from wakfu_server.inventory_items import grant
        from wakfu_server.shard_identification import identify
        from wakfu_server.equipment import RULES
        from wakfu_server.wire import proto_field

        reference = 2024  # Native monster-1 Capa Jalosa; maximum 99.
        self.assertEqual(STACKS[reference]["maximum"], 99)
        self.assertTrue(STACKS[reference]["minimal_mergeable"])
        self.assertTrue(
            any(
                row["reference_id"] == reference
                for row in native_drop_catalog()["monsters"][1]
            )
        )
        self._fill_base_bag()
        bag = self.character["inventory_containers"][0]["uid"]
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s AND container=%s AND slot=0",
                (self.character_id, bag),
            )
        target = grant(
            self.store,
            self.account_id,
            self.generation,
            self.character_id,
            reference=reference,
            quantity=1,
            container=bag,
            slot=0,
            allowed_references={reference},
        )
        shard = None
        if identified:
            shard = identify(
                self.store,
                self.account_id,
                self.generation,
                self.character_id,
                struct.pack(">q", target["uid"]),
                randbelow=lambda _: 0,
            )["shard_state"]
        if equipped:
            equipment = proto_field(
                10,
                proto_field(8, target["uid"])
                + proto_field(16, RULES[reference]["slots"][0]),
            )
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) "
                    "VALUES(%s,0,%s,%s,%s,%s) ON CONFLICT(character_id,build_index) "
                    "DO UPDATE SET equipment=EXCLUDED.equipment",
                    (self.character_id, proto_field(24, 1), equipment, b"", b""),
                )
        with self.store.connection() as db:
            batch = self._resolve(db, monster_reference=1)
            awarded = sum(
                row.quantity
                for row in batch.decisions
                if row.success and row.item_reference == reference
            )
            self.assertGreater(awarded, 0)
            apply(self.store, db, batch)
            sources = [
                dict(row)
                for row in db.execute(
                    "SELECT uid,quantity FROM temporary_combat_items WHERE character_id=%s "
                    "AND reference=%s ORDER BY uid",
                    (self.character_id, reference),
                )
            ]
        return dict(
            reference=reference,
            bag=bag,
            uid=target["uid"],
            shard=shard,
            awarded=awarded,
            sources=sources,
        )

    def _claim_guarded_drop(self, fixture, *, all_items, free_slot=True):
        self.assertEqual(
            sum(row["quantity"] for row in fixture["sources"]), fixture["awarded"]
        )
        if free_slot:
            with self.store.connection() as db:
                db.execute(
                    "DELETE FROM inventory_items WHERE character_id=%s AND container=%s AND slot=1",
                    (self.character_id, fixture["bag"]),
                )
        if all_items:
            body = struct.pack(
                ">qqh", self.character_id, self.character_id, len(fixture["sources"])
            )
            body += b"".join(
                struct.pack(">q", row["uid"]) for row in fixture["sources"]
            )
            result = bulk_transfer(
                self.store, self.account_id, self.generation, self.character_id, body
            )
        else:
            self.assertEqual(len(fixture["sources"]), 1)
            row = fixture["sources"][0]
            body = struct.pack(
                ">qh b q h", row["uid"], row["quantity"], -1, fixture["bag"], -1
            )
            result = claim(
                self.store, self.account_id, self.generation, self.character_id, body
            )
        self.assertTrue(result["applied"])
        self._assert_guarded_drop(fixture, claimed=True)

    def _assert_guarded_drop(self, fixture, *, claimed=False, merged=False):
        character = self.reopen().character(self.account_id, self.character_id)
        items = [
            row
            for row in character["inventory_items"]
            if row["reference"] == fixture["reference"]
        ]
        target = next(row for row in items if row["uid"] == fixture["uid"])
        self.assertEqual(target["quantity"], 1 + fixture["awarded"] if merged else 1)
        if fixture["shard"] is not None:
            self.assertEqual(target["shard_state"], fixture["shard"])
        self.assertEqual(
            sum(row["quantity"] for row in items),
            1 + fixture["awarded"] if claimed or merged else 1,
        )
        with self.store.connection() as db:
            temporary = db.execute(
                "SELECT coalesce(sum(quantity),0) AS n FROM temporary_combat_items "
                "WHERE character_id=%s AND reference=%s",
                (self.character_id, fixture["reference"]),
            ).fetchone()["n"]
        self.assertEqual(temporary, 0 if claimed or merged else fixture["awarded"])

    def test_native_drop_preserves_identified_singleton(self):
        fixture = self._guarded_native_drop(identified=True)
        self._assert_guarded_drop(fixture)

    def test_native_claim_preserves_identified_singleton(self):
        self._claim_guarded_drop(
            self._guarded_native_drop(identified=True), all_items=False
        )

    def test_native_get_all_preserves_identified_singleton(self):
        self._claim_guarded_drop(
            self._guarded_native_drop(identified=True), all_items=True
        )

    def test_native_claim_preserves_equipped_plain_singleton(self):
        self._claim_guarded_drop(
            self._guarded_native_drop(equipped=True), all_items=False
        )

    def test_native_get_all_preserves_equipped_plain_singleton(self):
        self._claim_guarded_drop(
            self._guarded_native_drop(equipped=True), all_items=True
        )

    def test_native_plain_drop_still_merges_at_native_capacity(self):
        self._assert_guarded_drop(self._guarded_native_drop(), merged=True)

    def _fill_base_bag(self, *, leave=0):
        with self.store.connection() as db:
            bags = db.execute(
                "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s ORDER BY kind",
                (self.character_id,),
            ).fetchall()
            free = max(0, leave)
            total = sum(bag["capacity"] for bag in bags)
            filled = total - free
            for bag in bags:
                for slot in range(min(bag["capacity"], filled)):
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,2021,1,%s,%s)",
                        (self.character_id, bag["uid"], slot),
                    )
                filled -= min(bag["capacity"], filled)
            return total, total - free

    def test_resolved_successes_are_delivered_once_and_survive_reopen(self):
        with self.store.connection() as db:
            batch = self._resolve(db)
            successes = [decision for decision in batch.decisions if decision.success]
            self.assertTrue(successes)
            first = apply(self.store, db, batch)
            self.assertEqual(len(first), len(successes))
            self.assertEqual(
                sum(row["awarded_quantity"] for row in first),
                sum(decision.quantity for decision in successes),
            )
        with self.store.connection() as db:
            counts = db.execute(
                "SELECT count(*) AS n,coalesce(sum(awarded_quantity),0) AS awarded,"
                "coalesce(sum(inventory_quantity),0) AS inventory,"
                "coalesce(sum(temporary_quantity),0) AS temporary "
                "FROM fight_drop_delivery_receipts WHERE fight_id=%s AND character_id=%s",
                (self.fight_id, self.character_id),
            ).fetchone()
            self.assertEqual(counts["n"], len(successes))
            self.assertEqual(
                counts["awarded"], counts["inventory"] + counts["temporary"]
            )
            before_uids = db.execute(
                "SELECT uid FROM inventory_items WHERE character_id=%s ORDER BY uid",
                (self.character_id,),
            ).fetchall()
            replay = self._resolve(db, rng=lambda upper: upper - 1)
            self.assertTrue(replay.replayed)
            second = apply(self.store, db, replay)
            self.assertEqual(second, first)
            self.assertEqual(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE character_id=%s ORDER BY uid",
                    (self.character_id,),
                ).fetchall(),
                before_uids,
            )
        reopened = self.reopen()
        with reopened.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_drop_delivery_receipts WHERE fight_id=%s",
                    (self.fight_id,),
                ).fetchone()["n"],
                len(successes),
            )

    def test_full_bag_uses_bootstrap_and_clear_plus_add_snapshot_without_loss(self):
        self._fill_base_bag()
        with self.store.connection() as db:
            batch = self._resolve(db)
            successes = [decision for decision in batch.decisions if decision.success]
            self.assertTrue(successes)
            placements = apply(self.store, db, batch)
            self.assertTrue(
                all(
                    item["temporary_quantity"] == item["awarded_quantity"]
                    for item in placements
                )
            )
            total = sum(decision.quantity for decision in successes)
            rows = db.execute(
                "SELECT * FROM temporary_combat_items WHERE character_id=%s ORDER BY uid",
                (self.character_id,),
            ).fetchall()
            self.assertEqual(sum(row["quantity"] for row in rows), total)
            section = temporary_section(db, self.character_id)
            self.assertGreater(struct.unpack_from(">h", section)[0], 0)
            fields = list(proto_fields(section[2:]))
            self.assertEqual(len(fields), len(rows))
            decoded = [dict(proto_fields(value)) for tag, value in fields if tag == 10]
            self.assertEqual(
                {(entry[8], entry[16], entry[24]) for entry in decoded},
                {(row["uid"], row["reference"], row["quantity"]) for row in rows},
            )
            opcode, update = temporary_update(db, self.character_id)
            self.assertEqual(opcode, 12691)
            self.assertEqual(struct.unpack_from(">q", update)[0], self.character_id)
            events = update[8:]
            self.assertEqual(
                events[0], 3
            )  # full native CLEAR before snapshot ADD_ITEM events
            from wakfu_server.inventory_items import item_form

            expected_adds = []
            for row in rows:
                item = dict(row)
                if (
                    item["damage_elements"] is None
                    and item["resistance_elements"] is None
                ):
                    item.pop("damage_elements")
                    item.pop("resistance_elements")
                expected_adds.append(b"\x00" + item_form(item))
            self.assertEqual(
                events,
                b"\x03" + b"".join(expected_adds),
            )
            inventory_total = db.execute(
                "SELECT coalesce(sum(quantity),0) AS n FROM inventory_items WHERE character_id=%s",
                (self.character_id,),
            ).fetchone()["n"]
            self.assertEqual(inventory_total, 34)

    def test_partial_capacity_places_what_fits_and_keeps_exact_remainder(self):
        self._fill_base_bag(leave=1)
        with self.store.connection() as db:
            batch = self._resolve(
                db, monster_reference=44, fight_context={"in_infinite_waves": False}
            )
            successes = [decision for decision in batch.decisions if decision.success]
            self.assertTrue(successes)
            placements = apply(self.store, db, batch)
            for placement, decision in zip(placements, successes):
                self.assertEqual(
                    placement["inventory_quantity"] + placement["temporary_quantity"],
                    decision.quantity,
                )
            totals = db.execute(
                "SELECT coalesce(sum(quantity),0) AS n FROM temporary_combat_items WHERE character_id=%s",
                (self.character_id,),
            ).fetchone()["n"]
            accounted = db.execute(
                "SELECT coalesce(sum(awarded_quantity),0) AS n FROM fight_drop_delivery_receipts "
                "WHERE fight_id=%s AND character_id=%s",
                (self.fight_id, self.character_id),
            ).fetchone()["n"]
            delivered = db.execute(
                "SELECT coalesce(sum(inventory_quantity),0) AS n FROM fight_drop_delivery_receipts "
                "WHERE fight_id=%s AND character_id=%s",
                (self.fight_id, self.character_id),
            ).fetchone()["n"]
            self.assertEqual(delivered + totals, accounted)

    def test_claim_requires_owned_uid_and_moves_all_requested_items_atomically(self):
        self._fill_base_bag()
        with self.store.connection() as db:
            batch = self._resolve(db)
            placements = apply(self.store, db, batch)
            temp = db.execute(
                "SELECT * FROM temporary_combat_items WHERE character_id=%s ORDER BY uid LIMIT 1",
                (self.character_id,),
            ).fetchone()
            self.assertIsNotNone(temp)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s AND container=(SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0) ",
                (self.character_id, self.character_id),
            )
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid,kind FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character_id,),
            ).fetchone()
        body = struct.pack(
            ">qh b q h", temp["uid"], temp["quantity"], -1, bag["uid"], -1
        )
        self.assertEqual(decode_claim(body)["uid"], temp["uid"])
        result = claim(
            self.store, self.account_id, self.generation, self.character_id, body
        )
        self.assertTrue(result["applied"])
        retry = claim(
            self.store, self.account_id, self.generation, self.character_id, body
        )
        self.assertFalse(retry["applied"])
        self.assertEqual(retry["packets"], result["packets"])
        reconnect_generation = self.store.begin_session(self.account_id)
        self.store.select_character(
            self.account_id, reconnect_generation, self.character_id
        )
        reconnect_retry = claim(
            self.store, self.account_id, reconnect_generation, self.character_id, body
        )
        self.assertFalse(reconnect_retry["applied"])
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM temporary_combat_items WHERE uid=%s",
                    (temp["uid"],),
                ).fetchone()
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT uid FROM inventory_items WHERE character_id=%s AND reference=%s",
                    (self.character_id, temp["reference"]),
                ).fetchone()
            )
        foreign = struct.pack(">qh b q h", temp["uid"] + 98765, 1, -1, bag["uid"], 0)
        with self.assertRaises(ValueError):
            claim(
                self.store, self.account_id, self.generation, self.character_id, foreign
            )

    def test_native_claim_aggregates_compatible_uid_rows_and_merges_when_bag_is_full(
        self,
    ):
        self._fill_base_bag()
        with self.store.connection() as db:
            batch = self._resolve(db, monster_reference=4196)
            apply(self.store, db, batch)
            first = db.execute(
                "SELECT * FROM temporary_combat_items WHERE character_id=%s AND reference=12325",
                (self.character_id,),
            ).fetchone()
            self.assertIsNotNone(first)
            second_fight = self._second_finished_fight(db)
            original_fight = self.fight_id
            self.fight_id = second_fight
            second_batch = self._resolve(db, monster_reference=4196)
            apply(self.store, db, second_batch)
            self.fight_id = original_fight
            rows = db.execute(
                "SELECT uid,quantity FROM temporary_combat_items "
                "WHERE character_id=%s AND reference=12325 ORDER BY uid",
                (self.character_id,),
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(sum(row["quantity"] for row in rows), 6)
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character_id,),
            ).fetchone()
            filler = db.execute(
                "SELECT uid FROM inventory_items WHERE character_id=%s AND container=%s "
                "ORDER BY slot LIMIT 1",
                (self.character_id, bag["uid"]),
            ).fetchone()
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (filler["uid"],))
            existing = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,12325,21,%s,0) RETURNING uid",
                (self.character_id, bag["uid"]),
            ).fetchone()
            if _effective_bound(dict(first)):
                _save_binding(db, existing["uid"], 12325, True)
        body = struct.pack(">qh b q h", rows[0]["uid"], 6, -1, bag["uid"], -1)
        result = claim(
            self.store, self.account_id, self.generation, self.character_id, body
        )
        self.assertTrue(result["applied"])
        retry = claim(
            self.store, self.account_id, self.generation, self.character_id, body
        )
        self.assertFalse(retry["applied"])
        with self.store.connection() as db:
            stacks = db.execute(
                "SELECT count(*) AS n,coalesce(sum(quantity),0) AS quantity "
                "FROM inventory_items WHERE character_id=%s AND reference=12325",
                (self.character_id,),
            ).fetchone()
            self.assertEqual((stacks["n"], stacks["quantity"]), (1, 27))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM temporary_combat_items "
                    "WHERE character_id=%s AND reference=12325",
                    (self.character_id,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM temporary_inventory_transfer_receipts "
                    "WHERE source_character_id=%s AND operation=1",
                    (self.character_id,),
                ).fetchone()["n"],
                1,
            )

    def test_native_get_all_same_character_merges_full_bag_and_retries_once(self):
        self._fill_base_bag()
        with self.store.connection() as db:
            batch = self._resolve(db, monster_reference=4196)
            apply(self.store, db, batch)
            temp = db.execute(
                "SELECT * FROM temporary_combat_items WHERE character_id=%s AND reference=12325",
                (self.character_id,),
            ).fetchone()
            self.assertIsNotNone(temp)
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character_id,),
            ).fetchone()
            filler = db.execute(
                "SELECT uid FROM inventory_items WHERE character_id=%s AND container=%s "
                "ORDER BY slot LIMIT 1",
                (self.character_id, bag["uid"]),
            ).fetchone()
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (filler["uid"],))
            existing = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,12325,21,%s,0) RETURNING uid",
                (self.character_id, bag["uid"]),
            ).fetchone()
            temp = dict(temp)
            temp["bound"] = _effective_bound(temp)
            _save_binding(db, existing["uid"], 12325, temp["bound"])
            uids = [temp["uid"]]
            body = struct.pack(">qqh", self.character_id, self.character_id, len(uids))
            body += b"".join(struct.pack(">q", uid) for uid in uids)
        self.assertEqual(
            decode_bulk_transfer(body)["source_character"], self.character_id
        )
        result = bulk_transfer(
            self.store, self.account_id, self.generation, self.character_id, body
        )
        self.assertTrue(result["applied"])
        self.assertEqual([opcode for opcode, _ in result["packets"]].count(13713), 1)
        retry = bulk_transfer(
            self.store, self.account_id, self.generation, self.character_id, body
        )
        self.assertFalse(retry["applied"])
        with self.store.connection() as db:
            stacks = db.execute(
                "SELECT count(*) AS n,coalesce(sum(quantity),0) AS quantity "
                "FROM inventory_items WHERE character_id=%s AND reference=12325",
                (self.character_id,),
            ).fetchone()
            self.assertEqual((stacks["n"], stacks["quantity"]), (1, 24))
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM temporary_combat_items WHERE uid=%s",
                    (temp["uid"],),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM temporary_inventory_transfer_receipts "
                    "WHERE source_character_id=%s AND operation=2",
                    (self.character_id,),
                ).fetchone()["n"],
                1,
            )

    def test_native_close_discards_exact_temporary_snapshot_durably(self):
        self._fill_base_bag()
        with self.store.connection() as db:
            batch = self._resolve(db, monster_reference=4196)
            apply(self.store, db, batch)
            initial = db.execute(
                "SELECT uid,quantity FROM temporary_combat_items WHERE character_id=%s "
                "ORDER BY uid",
                (self.character_id,),
            ).fetchall()
            self.assertTrue(initial)

        result = discard(
            self.store, self.account_id, self.generation, self.character_id, b""
        )
        self.assertTrue(result["applied"])
        self.assertEqual(result["packets"][0][0], 12691)
        self.assertEqual(result["packets"][0][1][8], 3)  # CLEAR, no item ADDs.
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM temporary_combat_items WHERE character_id=%s",
                    (self.character_id,),
                ).fetchone()["n"],
                0,
            )
            receipts = db.execute(
                "SELECT operation,request_body FROM temporary_inventory_transfer_receipts "
                "WHERE source_character_id=%s AND operation=3",
                (self.character_id,),
            ).fetchall()
            self.assertEqual(len(receipts), 1)
            self.assertTrue(
                bytes(receipts[0]["request_body"]).startswith(b"12561-discard\0")
            )

        replay = discard(
            self.store, self.account_id, self.generation, self.character_id, b""
        )
        self.assertFalse(replay["applied"])
        reconnect_generation = self.store.begin_session(self.account_id)
        self.store.select_character(
            self.account_id, reconnect_generation, self.character_id
        )
        self.generation = reconnect_generation
        with self.store.connection() as db:
            self.assertEqual(temporary_section(db, self.character_id), b"\x00\x00")

        # A later explicit close has a different locked snapshot and still
        # discards its rows; it is not suppressed by the earlier receipt.
        with self.store.connection() as db:
            next_fight = self._second_finished_fight(db)
            previous_fight = self.fight_id
            self.fight_id = next_fight
            batch = self._resolve(db, monster_reference=4196)
            apply(self.store, db, batch)
            self.fight_id = previous_fight
            later = db.execute(
                "SELECT uid FROM temporary_combat_items WHERE character_id=%s ORDER BY uid",
                (self.character_id,),
            ).fetchall()
            self.assertTrue(later)
        second_discard = discard(
            self.store, self.account_id, reconnect_generation, self.character_id, b""
        )
        self.assertTrue(second_discard["applied"])
        with self.store.connection() as db:
            self.assertEqual(temporary_section(db, self.character_id), b"\x00\x00")

    def test_native_close_requires_empty_body_and_current_lease(self):
        with self.assertRaises(ValueError):
            discard(
                self.store, self.account_id, self.generation, self.character_id, b"x"
            )
        stale_generation = self.generation
        active_generation = self.store.begin_session(self.account_id)
        self.store.select_character(
            self.account_id, active_generation, self.character_id
        )
        with self.assertRaises(ValueError):
            discard(
                self.store, self.account_id, stale_generation, self.character_id, b""
            )

    def test_bulk_transfer_requires_same_account_and_is_all_or_nothing(self):
        other = self.store.create_character(self.account_id, "LootAlt")
        self._fill_base_bag()
        with self.store.connection() as db:
            batch = self._resolve(db)
            apply(self.store, db, batch)
            rows = db.execute(
                "SELECT uid FROM temporary_combat_items WHERE character_id=%s ORDER BY uid LIMIT 2",
                (self.character_id,),
            ).fetchall()
            self.assertTrue(rows)
            selected = [row["uid"] for row in rows]
        body = struct.pack(
            ">qqh", self.character_id, other["id"], len(selected)
        ) + b"".join(struct.pack(">q", uid) for uid in selected)
        self.assertEqual(decode_bulk_transfer(body)["uids"], selected)
        result = bulk_transfer(
            self.store, self.account_id, self.generation, self.character_id, body
        )
        self.assertTrue(result["applied"])
        retry = bulk_transfer(
            self.store, self.account_id, self.generation, self.character_id, body
        )
        self.assertFalse(retry["applied"])
        self.assertEqual(retry["packets"], result["packets"])
        reconnect_generation = self.store.begin_session(self.account_id)
        self.store.select_character(
            self.account_id, reconnect_generation, self.character_id
        )
        reconnect_retry = bulk_transfer(
            self.store, self.account_id, reconnect_generation, self.character_id, body
        )
        self.assertFalse(reconnect_retry["applied"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM temporary_combat_items WHERE uid=ANY(%s)",
                    (selected,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE uid=ANY(%s) AND character_id=%s",
                    (selected, other["id"]),
                ).fetchone()["n"],
                len(selected),
            )
        invalid = struct.pack(
            ">qqh", self.character_id, other["id"] + 99999, 1
        ) + struct.pack(">q", selected[0])
        with self.assertRaises(ValueError):
            bulk_transfer(
                self.store, self.account_id, self.generation, self.character_id, invalid
            )

    def test_partial_claim_preserves_uid_and_exact_remainder_after_lost_ack_retry(self):
        self._fill_base_bag()
        with self.store.connection() as db:
            batch = self._resolve(
                db, monster_reference=5889, fight_context={"in_infinite_waves": False}
            )
            placements = apply(self.store, db, batch)
            temp = db.execute(
                "SELECT * FROM temporary_combat_items WHERE character_id=%s AND reference=33214",
                (self.character_id,),
            ).fetchone()
            self.assertIsNotNone(temp)
            self.assertGreaterEqual(temp["quantity"], 3)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s AND container=(SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0)",
                (self.character_id, self.character_id),
            )
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character_id,),
            ).fetchone()
        body = struct.pack(">qh b q h", temp["uid"], 2, -1, bag["uid"], -1)
        result = claim(
            self.store, self.account_id, self.generation, self.character_id, body
        )
        self.assertTrue(result["applied"])
        replay = claim(
            self.store, self.account_id, self.generation, self.character_id, body
        )
        self.assertFalse(replay["applied"])
        with self.store.connection() as db:
            remaining = db.execute(
                "SELECT uid,quantity FROM temporary_combat_items WHERE uid=%s",
                (temp["uid"],),
            ).fetchone()
            self.assertEqual(remaining["quantity"], temp["quantity"] - 2)
            moved = db.execute(
                "SELECT uid,quantity FROM inventory_items WHERE character_id=%s AND reference=33214",
                (self.character_id,),
            ).fetchone()
            self.assertEqual(moved["quantity"], 2)
            self.assertNotEqual(moved["uid"], temp["uid"])

    def test_all_drop_templates_have_stack_and_binding_metadata(self):
        catalog = native_drop_catalog()
        references = {
            row["reference_id"]
            for monster in catalog["monsters"].values()
            for row in monster
            if isinstance(row, dict) and type(row.get("reference_id")) is int
        }
        self.assertGreater(len(references), 6000)
        self.assertTrue(references.issubset(STACKS))
        self.assertTrue(references.issubset({int(reference) for reference in ITEMS}))
        self.assertTrue(
            any(
                ITEMS[str(reference)]["binding_template"]["default_eKo"]
                for reference in references
            )
        )

    def test_bound_native_drop_survives_temp_bootstrap_claim_and_replay(self):
        self._fill_base_bag()
        with self.store.connection() as db:
            batch = self._resolve(
                db, monster_reference=5889, fight_context={"in_infinite_waves": False}
            )
            delivered = apply(self.store, db, batch)
            row = db.execute(
                "SELECT * FROM temporary_combat_items WHERE character_id=%s AND reference=33214",
                (self.character_id,),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertTrue(row["bound"])
            section_fields = [
                dict(proto_fields(value))
                for tag, value in proto_fields(
                    temporary_section(db, self.character_id)[2:]
                )
                if tag == 10
            ]
            encoded = next(item for item in section_fields if item[16] == 33214)
            self.assertEqual(encoded[440], 1)
            _, live_update = temporary_update(db, self.character_id)
            from wakfu_server.combat_drop_delivery import _temporary_item_form

            live_item = _temporary_item_form(dict(row))
            self.assertIn(b"\x00" + live_item, live_update[9:])
            # vj.afx is field five: native bind type 2, applied=true.
            self.assertEqual(live_item[14:21], b"\x00\x00\x00\x00\x01\x04\x01")
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character_id,),
            ).fetchone()
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s AND container=%s",
                (self.character_id, bag["uid"]),
            )
        claim_body = struct.pack(
            ">qh b q h", row["uid"], row["quantity"], -1, bag["uid"], -1
        )
        result = claim(
            self.store, self.account_id, self.generation, self.character_id, claim_body
        )
        self.assertTrue(result["applied"])
        replay = claim(
            self.store, self.account_id, self.generation, self.character_id, claim_body
        )
        self.assertFalse(replay["applied"])
        with self.store.connection() as db:
            moved = db.execute(
                "SELECT uid,reference FROM inventory_items WHERE character_id=%s AND reference=33214",
                (self.character_id,),
            ).fetchone()
            self.assertIsNotNone(moved)
            binding = db.execute(
                "SELECT bound,template_reference FROM inventory_item_bindings WHERE uid=%s",
                (moved["uid"],),
            ).fetchone()
            self.assertEqual(
                dict(binding), {"bound": True, "template_reference": 33214}
            )
            self.assertTrue(any(packet[0] == 13078 for packet in result["packets"]))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM temporary_inventory_transfer_receipts "
                    "WHERE source_character_id=%s AND operation=1",
                    (self.character_id,),
                ).fetchone()["n"],
                1,
            )

    def test_bound_drop_merges_only_with_same_effective_binding(self):
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character_id,),
            ).fetchone()
            target_uid = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,33214,1,%s,29) RETURNING uid",
                (self.character_id, bag["uid"]),
            ).fetchone()["uid"]
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,true,33214)",
                (target_uid,),
            )
            for slot in range(1, 29):
                db.execute(
                    "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                    "VALUES(%s,2021,1,%s,%s)",
                    (self.character_id, bag["uid"], slot),
                )
            batch = self._resolve(
                db, monster_reference=5889, fight_context={"in_infinite_waves": False}
            )
            successes = [
                item
                for item in batch.decisions
                if item.success and item.item_reference == 33214
            ]
            self.assertTrue(successes)
            apply(self.store, db, batch)
            target = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (target_uid,)
            ).fetchone()
            self.assertEqual(
                target["quantity"], 1 + sum(item.quantity for item in successes)
            )

    def test_unbound_drop_does_not_merge_into_instance_bound_stack(self):
        self.assertFalse(ITEMS["20595"]["binding_template"]["default_eKo"])
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character_id,),
            ).fetchone()
            target_uid = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,20595,1,%s,0) RETURNING uid",
                (self.character_id, bag["uid"]),
            ).fetchone()["uid"]
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,true,20595)",
                (target_uid,),
            )
            batch = self._resolve(db, monster_reference=1)
            successes = [
                item
                for item in batch.decisions
                if item.success and item.item_reference == 20595
            ]
            self.assertTrue(successes)
            apply(self.store, db, batch)
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (target_uid,)
                ).fetchone()["quantity"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT coalesce(sum(quantity),0) AS n FROM inventory_items "
                    "WHERE character_id=%s AND reference=20595 AND uid<>%s",
                    (self.character_id, target_uid),
                ).fetchone()["n"],
                sum(item.quantity for item in successes),
            )

    def test_specialized_bag_is_not_used_for_drops_claim_or_bulk_transfer(self):
        filtered = next(row for row in BAG_RULES.values() if row["accepted_types"])
        other = self.store.create_character(self.account_id, "LootAltFiltered")
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_containers SET reference=%s,capacity=%s "
                "WHERE character_id=%s AND kind=1",
                (filtered["reference"], filtered["capacity"], self.character_id),
            )
            db.execute(
                "UPDATE inventory_containers SET reference=%s,capacity=%s "
                "WHERE character_id=%s AND kind=1",
                (filtered["reference"], filtered["capacity"], other["id"]),
            )
            base = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character_id,),
            ).fetchone()
            other_base = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (other["id"],),
            ).fetchone()
            for slot in range(30):
                db.execute(
                    "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                    "VALUES(%s,2021,1,%s,%s)",
                    (self.character_id, base["uid"], slot),
                )
                db.execute(
                    "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                    "VALUES(%s,2021,1,%s,%s)",
                    (other["id"], other_base["uid"], slot),
                )
            batch = self._resolve(
                db, monster_reference=44, fight_context={"in_infinite_waves": False}
            )
            apply(self.store, db, batch)
            temp = db.execute(
                "SELECT uid FROM temporary_combat_items WHERE character_id=%s ORDER BY uid LIMIT 1",
                (self.character_id,),
            ).fetchone()
            self.assertIsNotNone(temp)
            destination_bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=1",
                (self.character_id,),
            ).fetchone()
        claim_body = struct.pack(
            ">qh b q h", temp["uid"], 1, -1, destination_bag["uid"], -1
        )
        with self.assertRaises(ValueError):
            claim(
                self.store,
                self.account_id,
                self.generation,
                self.character_id,
                claim_body,
            )
        body = struct.pack(">qqh", self.character_id, other["id"], 1) + struct.pack(
            ">q", temp["uid"]
        )
        with self.assertRaises(ValueError):
            bulk_transfer(
                self.store, self.account_id, self.generation, self.character_id, body
            )
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT uid FROM temporary_combat_items WHERE uid=%s",
                    (temp["uid"],),
                ).fetchone()
            )

    def test_delivery_failure_rolls_back_awards_and_inventory_together(self):
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_drop_delivery() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'forced delivery failure'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_drop_delivery BEFORE INSERT ON fight_drop_delivery_receipts "
                "FOR EACH ROW EXECUTE FUNCTION reject_drop_delivery()"
            )
            batch = self._resolve(db)
            with self.assertRaises(Exception):
                apply(self.store, db, batch)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_drop_awards WHERE fight_id=%s",
                    (self.fight_id,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_drop_delivery_receipts WHERE fight_id=%s",
                    (self.fight_id,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s",
                    (self.character_id,),
                ).fetchone()["n"],
                0,
            )

    def test_native_request_decoders_reject_truncated_duplicates_and_foreign_shape(
        self,
    ):
        with self.assertRaises(ValueError):
            decode_claim(b"\x00" * 20)
        for destination_type in (-2, 0, 1, 4):
            with self.assertRaises(ValueError):
                decode_claim(struct.pack(">qh b q h", 1, 1, destination_type, 1, 0))
        with self.assertRaises(ValueError):
            decode_claim(struct.pack(">qh b q h", 1, 0, -1, 1, 0))
        duplicate = struct.pack(">qqhqq", 1, 2, 2, 10, 10)
        with self.assertRaises(ValueError):
            decode_bulk_transfer(duplicate)
        with self.assertRaises(ValueError):
            decode_bulk_transfer(struct.pack(">qqh", 1, 2, 1))
