"""One shared paid-container contract over all seeded sources and leased items."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import struct
from unittest.mock import patch

from postgres_case import PostgresCase


class PaidContainerSettlementTests(PostgresCase):
    def test_bulk_sources_and_atomic_occupation_repeat_cancel_reconnect(self):
        from wakfu_server import paid_containers as service
        from wakfu_server.achievements import rewards
        from wakfu_server.inventory_items import grant

        with self.store.connection() as db:
            locations = db.execute(
                "SELECT map_id,object_id FROM paid_container_locations "
                "WHERE policy_id LIKE 'wakemu.mimik.%' ORDER BY map_id,object_id"
            ).fetchall()
            self.assertEqual(len(locations), 8)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM paid_container_policies WHERE sealed AND policy_id LIKE 'wakemu.mimik.%'"
                ).fetchone()["n"],
                7,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM paid_container_outcomes WHERE policy_id LIKE 'wakemu.mimik.%'"
                ).fetchone()["n"],
                28,
            )
        rules = [
            service.definition(self.store, row["map_id"], row["object_id"])
            for row in locations
        ]
        for rule in rules:
            service._source(
                rule
            )  # All eight original objects/states/catalog/terrain joins.
            self.assertEqual(sum(r["weight"] for r in rule["outcomes"]), 50)
            self.assertTrue(all(r["quantity"] == 1 for r in rule["outcomes"]))
            self.assertEqual(rule["criterion"], "not IsHero()")

        rule = next(row for row in rules if row["map_id"] == 311)
        account = self.store.register("paid-container-contract", "local-test-password")[
            "id"
        ]
        character = self.store.create_character(account, "Paid Container")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        origin = rule["approaches"][0]
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (rule["map_id"], *origin, character["id"]),
            )
        character = self.store.character(account, character["id"])
        body = struct.pack(">qHH", rule["object_id"], 22, 0)
        complete = struct.pack(">bh", 2, 28)
        canceled = struct.pack(">bh", 3, 28)

        def current():
            return self.store.character(account, character["id"])

        def begin(**kwargs):
            return service.begin(
                self.store,
                account,
                generation,
                current(),
                body,
                loaded=True,
                is_hero=False,
                **kwargs
            )

        def finish(token, payload=complete, **kwargs):
            return service.finish(
                self.store,
                account,
                generation,
                current(),
                token,
                payload,
                loaded=True,
                is_hero=False,
                **kwargs
            )

        def quantity(reference):
            return sum(
                item["quantity"]
                for item in current()["inventory_items"]
                if item["reference"] == reference
            )

        def add_keys(amount):
            actor = current()
            base = actor["inventory_containers"][0]
            occupied = {
                item["slot"]
                for item in actor["inventory_items"]
                if item["container"] == base["uid"]
            }
            slot = next(i for i in range(base["capacity"]) if i not in occupied)
            with self.store.connection() as db:
                grant(
                    self.store,
                    account,
                    generation,
                    actor["id"],
                    reference=12324,
                    quantity=amount,
                    container=base["uid"],
                    slot=slot,
                    allowed_references={12324},
                    db=db,
                )

        def elapsed(token):
            # Advance the injected store clock; never forge an attempt deadline.
            instant = self.store.now() + timedelta(seconds=2)
            return patch.object(self.store, "now", return_value=instant)

        with self.assertRaisesRegex(ValueError, "Missing original"):
            begin()
        add_keys(30)
        with self.assertRaises(ValueError):
            service.begin(
                self.store,
                account,
                generation,
                current(),
                body,
                loaded=True,
                is_hero=True,
            )
        with self.assertRaises(ValueError):
            service.begin(
                self.store,
                account,
                generation,
                current(),
                struct.pack(">qHH", rule["object_id"], 0, 0),
                loaded=True,
                is_hero=False,
            )
        started = begin(choose=lambda total: 0)
        self.assertNotIn("selected_ordinal", started)
        self.assertNotIn("receipt", started)
        self.assertEqual(
            struct.unpack(">bhqqq", started["packets"][1][1]),
            (1, 28, character["id"], rule["object_id"], 1000),
        )
        self.assertEqual(quantity(12324), 30)
        active_snapshot = service.snapshots(self.store, rule["map_id"], 0)
        self.assertEqual(struct.unpack_from(">h", active_snapshot[0][1], 17)[0], 3)
        self.assertEqual(
            begin(choose=lambda _: self.fail("Duplicate begin rerolled"))["token"],
            started["token"],
        )
        with self.assertRaisesRegex(ValueError, "before its duration"):
            finish(started["token"])
        with self.store.connection() as db:
            first_choice = db.execute(
                "SELECT selected_ordinal FROM paid_container_attempts WHERE token=%s",
                (started["token"],),
            ).fetchone()["selected_ordinal"]
        original_item = rewards._item

        def fail_after_grant(*args, **kwargs):
            original_item(*args, **kwargs)
            raise ValueError("Injected inventory settlement failure")

        before = current()["inventory_items"]
        with elapsed(started["token"]), patch.object(
            rewards, "_item", side_effect=fail_after_grant
        ):
            with self.assertRaisesRegex(ValueError, "Injected inventory"):
                finish(started["token"])
        self.assertEqual(current()["inventory_items"], before)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT state,selected_ordinal,receipt FROM paid_container_attempts WHERE token=%s",
                (started["token"],),
            ).fetchone()
        self.assertEqual(
            (row["state"], row["selected_ordinal"], row["receipt"]),
            ("active", first_choice, None),
        )
        with elapsed(started["token"]):
            with ThreadPoolExecutor(max_workers=2) as workers:
                results = list(
                    workers.map(lambda _: finish(started["token"]), range(2))
                )
        self.assertEqual(sorted(r["replay"] for r in results), [False, True])
        self.assertEqual(quantity(12324), 30 - rule["qty"])
        reward = next(row for row in results if not row["replay"])["receipt"]
        self.assertEqual(reward["ordinal"], first_choice)
        self.assertEqual(quantity(reward["reference"]), reward["quantity"])
        self.assertEqual(
            struct.unpack_from(
                ">h", service.snapshots(self.reopen(), rule["map_id"], 0)[0][1], 17
            )[0],
            1,
        )
        self.assertTrue(
            all(opcode == 12344 for opcode, _ in finish(started["token"])["packets"])
        )
        # A new paid opening is distinct; cancellation consumes nothing.
        second = begin(choose=lambda _: 0)
        self.assertNotEqual(second["token"], started["token"])
        canceled_result = finish(second["token"], canceled)
        self.assertEqual(canceled_result["state"], "canceled")
        self.assertEqual(quantity(12324), 30 - rule["qty"])
        # Reconnect cannot finish the old connection's ticket; a fresh begin
        # cancels that stale attempt without charging, then binds the new lease.
        third = begin(choose=lambda _: 0)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.assertRaisesRegex(ValueError, "another lease"):
            finish(third["token"])
        fourth = begin(choose=lambda _: 0)
        self.assertNotEqual(third["token"], fourth["token"])
        self.assertEqual(quantity(12324), 30 - rule["qty"])
        # Exact origin is rechecked under the lease, even if the new position
        # happens to be another valid approach for the same object.
        other = next(cell for cell in rule["approaches"] if cell != origin)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                (*other, character["id"]),
            )
        with elapsed(fourth["token"]), self.assertRaisesRegex(ValueError, "origin"):
            finish(fourth["token"])
        service.cancel(self.store, account, generation, current(), fourth["token"])
        self.assertEqual(quantity(12324), 30 - rule["qty"])
        fifth = begin(choose=lambda _: 0)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s AND reference=12324",
                (character["id"],),
            )
        with elapsed(fifth["token"]), self.assertRaisesRegex(
            ValueError, "Missing original"
        ):
            finish(fifth["token"])
        self.assertEqual(quantity(reward["reference"]), reward["quantity"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT state FROM paid_container_attempts WHERE token=%s",
                    (fifth["token"],),
                ).fetchone()["state"],
                "active",
            )
        service.cancel(self.store, account, generation, current(), fifth["token"])
        add_keys(30 - rule["qty"])
        # Three-input family uses exactly its sealed cost, not a per-map branch.
        costly = next(row for row in rules if row["qty"] == 3)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (costly["map_id"], *costly["approaches"][0], character["id"]),
            )
        paid = service.begin(
            self.store,
            account,
            generation,
            current(),
            struct.pack(">qHH", costly["object_id"], 22, 0),
            loaded=True,
            is_hero=False,
            choose=lambda _: 0,
        )
        with elapsed(paid["token"]):
            result = finish(paid["token"])
        self.assertEqual(result["state"], "completed")
        self.assertEqual(quantity(12324), 30 - rule["qty"] - 3)
        # An expired ticket must never reset a different user's new opening.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (rule["map_id"], *origin, character["id"]),
            )
        stale = begin(choose=lambda _: 0)
        other_account = self.store.register(
            "paid-container-other", "local-test-password"
        )["id"]
        other_actor = self.store.create_character(other_account, "Paid Other")
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(other_account, other_generation, other_actor["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (rule["map_id"], *origin, other_actor["id"]),
            )
            base = other_actor["inventory_containers"][0]
            grant(
                self.store,
                other_account,
                other_generation,
                other_actor["id"],
                reference=12324,
                quantity=5,
                container=base["uid"],
                slot=0,
                allowed_references={12324},
                db=db,
            )
        other_actor = self.store.character(other_account, other_actor["id"])
        future = self.store.now() + timedelta(seconds=33)
        with patch.object(self.store, "now", return_value=future):
            reopened = service.begin(
                self.store,
                other_account,
                other_generation,
                other_actor,
                body,
                loaded=True,
                is_hero=False,
                choose=lambda _: 0,
            )
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=527,x=0,y=32,z=0 WHERE id=%s",
                    (character["id"],),
                )
            old_result = finish(stale["token"])
            self.assertEqual(old_result["state"], "canceled")
            self.assertEqual(old_result["location"], (rule["map_id"], 0))
            self.assertEqual(
                struct.unpack_from(">h", old_result["packets"][0][1], 17)[0], 3
            )
            service.cancel(
                self.store,
                other_account,
                other_generation,
                other_actor,
                reopened["token"],
            )
