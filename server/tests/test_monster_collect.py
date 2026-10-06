import struct
import copy
import threading
import ast
from pathlib import Path
from datetime import timedelta
import psycopg
from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server.monster_collect import (
    Harvests,
    action,
    decode_request,
    decode_result,
    start_packet,
    availability_packet,
)
from wakfu_server.wire import proto_field


class HarvestTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = [1000.0]
        self.store.clock = lambda: self.now[0]
        self.account = self.store.register("harvest-owner", "local-password")["id"]
        self.char = self.store.create_character(self.account, "Harvest Owner")
        self.gen = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.gen, self.char["id"])
        self.harvest = Harvests(self.store)
        self.monster = dict(
            id=-4498523304664558568,
            ref=1,
            hp=10,
            map_id=self.char["map_id"],
            instance_id=self.char["instance_id"],
        )
        self.body = proto_field(8, 3723) + proto_field(
            16, self.monster["id"] % (2**64)
        )

    def begin(self, **kwargs):
        if kwargs:
            self.configure(**kwargs)
        return self.harvest.begin(
            self.account,
            self.gen,
            self.char["id"],
            self.body,
            self.monster,
            profession_level=0,
            reachable=True,
        )

    def configure(self, *, quantity=1, cooldown_seconds=60):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_harvest'",
                (Jsonb({"quantity": quantity, "cooldown_seconds": cooldown_seconds}),),
            )

    def complete(self):
        return self.harvest.complete(
            self.account,
            self.gen,
            self.char["id"],
            b"\x02\x00\x06",
            monster=self.monster,
            profession_level=0,
        )

    def test_native_large_id_and_duration_packet(self):
        self.assertEqual(
            decode_request(self.body),
            dict(action_id=3723, monster_id=self.monster["id"]),
        )
        opcode, body = self.begin()
        self.assertEqual(opcode, 13597)
        self.assertEqual(
            struct.unpack(">Bhqqqi", body),
            (0, 6, self.char["id"], 3000, self.monster["id"], 3723),
        )

    def test_completion_grants_native_resource_once_and_survives_reconnect(self):
        self.begin()
        self.now[0] += 3.0
        result = self.complete()
        self.assertTrue(result["applied"])
        self.assertEqual(result["item"]["reference"], 2246)
        self.assertEqual(result["packets"][0][0], 12471)
        self.assertFalse(self.complete()["applied"])
        items = self.reopen().character(self.account, self.char["id"])[
            "inventory_items"
        ]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["quantity"], 1)

    def test_availability_is_disabled_only_after_receipt_commit(self):
        self.configure(cooldown_seconds=10)
        self.begin()
        self.now[0] += 3
        result = self.complete()
        self.assertTrue(result["applied"])
        self.assertEqual(
            result["availability"],
            (
                self.monster["map_id"],
                self.monster["instance_id"],
                availability_packet(self.monster["id"], 3723, False),
            ),
        )
        key = (
            self.monster["map_id"],
            self.monster["instance_id"],
            self.monster["id"],
            3723,
        )
        self.assertEqual(self.harvest.regenerating[key], self.now[0] + 10)

        # A committed inventory update with a failed receipt must not announce
        # or cache a cooldown; the surrounding PostgreSQL transaction rolls back.
        reopened = self.reopen()
        fresh = Harvests(reopened)
        reopened.clock = self.store.clock
        with reopened.connection() as db:
            db.execute(
                """CREATE FUNCTION reject_harvest_receipt_availability() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'receipt unavailable'; END $$"""
            )
            db.execute(
                "CREATE TRIGGER reject_harvest_receipt_availability BEFORE INSERT ON "
                "monster_harvest_receipts FOR EACH ROW EXECUTE FUNCTION "
                "reject_harvest_receipt_availability()"
            )
        before = dict(fresh.regenerating)
        # Begin/finish on a separate item/action setup after dropping the prior
        # receipt trigger's scope to this new completion.
        self.now[0] += 11
        fresh.begin(
            self.account,
            self.gen,
            self.char["id"],
            self.body,
            self.monster,
            profession_level=0,
            reachable=True,
        )
        self.now[0] += 3
        with self.assertRaises(psycopg.Error):
            fresh.complete(
                self.account,
                self.gen,
                self.char["id"],
                b"\x02\x00\x06",
                monster=self.monster,
                profession_level=0,
            )
        self.assertEqual(fresh.regenerating, before)
        self.assertEqual(fresh.next_regeneration, float("inf"))

    def test_cooldown_snapshot_reconnect_scope_and_single_boundary_drain(self):
        self.configure(cooldown_seconds=5)
        self.begin()
        self.now[0] += 3
        self.complete()
        first_monster_id = self.monster["id"]
        second_monster_id = first_monster_id + 1
        self.monster["id"] = second_monster_id
        self.body = proto_field(8, 3723) + proto_field(
            16, second_monster_id % (2**64)
        )
        self.begin()
        self.now[0] += 3
        self.complete()

        reopened = self.reopen()
        reopened.clock = self.store.clock
        fresh = Harvests(reopened)
        disabled = fresh.availability_snapshot(
            self.monster["map_id"], self.monster["instance_id"]
        )
        self.assertEqual(
            set(disabled),
            {
                availability_packet(first_monster_id, 3723, False),
                availability_packet(second_monster_id, 3723, False),
            },
        )
        self.assertEqual(
            fresh.availability_snapshot(
                self.monster["map_id"] + 1, self.monster["instance_id"]
            ),
            [],
        )
        self.assertEqual(
            fresh.availability_snapshot(
                self.monster["map_id"], self.monster["instance_id"] + 1
            ),
            [],
        )

        self.now[0] += 1.999
        original_connection = reopened.connection
        reopened.connection = lambda: (_ for _ in ()).throw(
            AssertionError("unexpected SQL before deadline")
        )
        self.assertEqual(fresh.due_availability(), [])

        self.assertEqual(
            set(
                fresh.availability_for(
                    self.monster["map_id"],
                    self.monster["instance_id"],
                    [first_monster_id, second_monster_id],
                )
            ),
            {
                availability_packet(first_monster_id, 3723, False),
                availability_packet(second_monster_id, 3723, False),
            },
        )
        reopened.connection = original_connection
        self.now[0] += 0.001
        self.assertEqual(
            fresh.due_availability(),
            [
                (
                    self.monster["map_id"],
                    self.monster["instance_id"],
                    availability_packet(first_monster_id, 3723, True),
                )
            ],
        )
        self.now[0] += 3
        self.assertEqual(
            fresh.due_availability(),
            [
                (
                    self.monster["map_id"],
                    self.monster["instance_id"],
                    availability_packet(second_monster_id, 3723, True),
                )
            ],
        )
        self.assertEqual(fresh.due_availability(), [])
        self.assertEqual(
            fresh.availability_for(
                self.monster["map_id"],
                self.monster["instance_id"],
                [first_monster_id, second_monster_id],
            ),
            [],
        )

    def test_expired_offline_cooldown_is_not_restored_disabled(self):
        self.configure(cooldown_seconds=5)
        self.begin()
        self.now[0] += 3
        self.complete()
        reopened = self.reopen()
        reopened.clock = self.store.clock
        fresh = Harvests(reopened)
        self.now[0] += 5
        self.assertEqual(
            fresh.availability_snapshot(
                self.monster["map_id"], self.monster["instance_id"]
            ),
            [],
        )
        self.assertEqual(fresh.due_availability(), [])
        self.assertEqual(
            fresh.begin(
                self.account,
                self.gen,
                self.char["id"],
                self.body,
                self.monster,
                profession_level=0,
                reachable=True,
            )[0],
            13597,
        )

    def test_completion_freezes_persisted_deadline_while_new_tickets_use_current_policy(
        self,
    ):
        self.configure(cooldown_seconds=10)
        self.begin()
        self.now[0] += 3
        completed_at = self.store.now()
        result = self.complete()
        self.assertTrue(result["applied"])
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT completed_at,regenerates_until FROM monster_harvest_receipts"
            ).fetchone()
        self.assertEqual(
            receipt["regenerates_until"],
            receipt["completed_at"] + timedelta(seconds=10),
        )
        self.assertEqual(receipt["completed_at"], completed_at)

        self.configure(cooldown_seconds=1)
        reopened = self.reopen()
        reopened.clock = self.store.clock
        restored = Harvests(reopened)
        self.assertEqual(
            restored.availability_snapshot(
                self.monster["map_id"], self.monster["instance_id"]
            ),
            [availability_packet(self.monster["id"], 3723, False)],
        )
        self.assertEqual(
            restored.availability_for(
                self.monster["map_id"],
                self.monster["instance_id"],
                [self.monster["id"] + 1],
            ),
            [],
        )
        key = (
            self.monster["map_id"],
            self.monster["instance_id"],
            self.monster["id"],
            3723,
        )
        self.assertEqual(
            restored.regenerating[key], receipt["regenerates_until"].timestamp()
        )

        # The old completion stays blocked until its saved deadline despite the
        # new one-second policy. At that boundary, new occupations freeze 1s.
        self.now[0] = receipt["regenerates_until"].timestamp() - 0.001
        with self.assertRaisesRegex(ValueError, "regenerating"):
            restored.begin(
                self.account,
                self.gen,
                self.char["id"],
                self.body,
                self.monster,
                profession_level=0,
                reachable=True,
            )
        self.now[0] += 0.001
        restored.due_availability()
        restored.begin(
            self.account,
            self.gen,
            self.char["id"],
            self.body,
            self.monster,
            profession_level=0,
            reachable=True,
        )
        self.assertEqual(restored.pending[self.char["id"]]["cooldown_seconds"], 1)
        self.now[0] += 3
        self.assertTrue(
            restored.complete(
                self.account,
                self.gen,
                self.char["id"],
                b"\x02\x00\x06",
                monster=self.monster,
                profession_level=0,
            )["applied"]
        )
        with reopened.connection() as db:
            deadlines = db.execute(
                "SELECT completed_at,regenerates_until FROM monster_harvest_receipts "
                "ORDER BY completed_at"
            ).fetchall()
        self.assertEqual(len(deadlines), 2)
        self.assertEqual(
            deadlines[1]["regenerates_until"],
            deadlines[1]["completed_at"] + timedelta(seconds=1),
        )

    def test_availability_opcode_validates_native_target_and_boolean(self):
        self.assertEqual(
            availability_packet(-1, 1, True), (13421, struct.pack(">qiB", -1, 1, 1))
        )
        for args in (
            (1, 1, True),
            (-1, 0, True),
            (-1, 1, 1),
            (-(1 << 63) - 1, 1, False),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                availability_packet(*args)

    def test_dispatcher_sends_harvest_availability_before_inventory_packets(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        session = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        branches = [node for node in ast.walk(session) if isinstance(node, ast.If)]

        def opcode_branch(node, expected):
            tests = (
                node.test.values if isinstance(node.test, ast.BoolOp) else [node.test]
            )
            return any(
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "opcode"
                and any(
                    isinstance(value, ast.Constant) and value.value == expected
                    for value in test.comparators
                )
                for test in tests
            )

        target = next(node for node in branches if opcode_branch(node, 13429))
        calls = [node for node in ast.walk(target) if isinstance(node, ast.Call)]
        emit = next(
            call
            for call in calls
            if isinstance(call.func, ast.Attribute)
            and call.func.attr == "emit_location"
        )
        packet_loop = next(
            node
            for node in ast.walk(target)
            if isinstance(node, ast.For)
            and isinstance(node.target, ast.Tuple)
            and any(
                isinstance(n, ast.Name) and n.id == "packets"
                for n in ast.walk(node.iter)
            )
        )
        self.assertLess(emit.lineno, packet_loop.lineno)

        harvest_branch = next(node for node in branches if opcode_branch(node, 13481))
        typed_catch = next(
            node
            for node in ast.walk(harvest_branch)
            if isinstance(node, ast.ExceptHandler)
            and isinstance(node.type, ast.Name)
            and node.type.id == "Regenerating"
        )
        catch_calls = [
            node for node in ast.walk(typed_catch) if isinstance(node, ast.Call)
        ]
        self.assertTrue(
            any(
                isinstance(call.func, ast.Name)
                and call.func.id == "send"
                and any(
                    isinstance(n, ast.Name) and n.id == "availability_packet"
                    for n in ast.walk(call)
                )
                for call in catch_calls
            )
        )

        join_world = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "join_world"
        )
        join_calls = [
            node for node in ast.walk(join_world) if isinstance(node, ast.Call)
        ]
        spawn = next(
            call
            for call in join_calls
            if isinstance(call.func, ast.Name)
            and call.func.id == "send"
            and any(
                isinstance(n, ast.Constant) and n.value == 12608 for n in ast.walk(call)
            )
        )
        snapshot = next(
            call
            for call in join_calls
            if isinstance(call.func, ast.Attribute)
            and call.func.attr == "availability_snapshot"
        )
        self.assertLess(spawn.lineno, snapshot.lineno)

        respawn = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "respawn_monsters"
        )
        respawn_calls = [
            node for node in ast.walk(respawn) if isinstance(node, ast.Call)
        ]
        respawn_spawn = next(
            call
            for call in respawn_calls
            if isinstance(call.func, ast.Attribute)
            and call.func.attr == "emit_location"
            and any(
                isinstance(n, ast.Constant) and n.value == 12608 for n in ast.walk(call)
            )
        )
        restore = next(
            call
            for call in respawn_calls
            if isinstance(call.func, ast.Attribute)
            and call.func.attr == "availability_for"
        )
        availability_emit = [
            call
            for call in respawn_calls
            if isinstance(call.func, ast.Attribute)
            and call.func.attr == "emit_location"
            and call is not respawn_spawn
        ]
        self.assertTrue(availability_emit)
        self.assertLess(respawn_spawn.lineno, restore.lineno)
        self.assertLess(restore.lineno, max(call.lineno for call in availability_emit))

    def test_early_finish_cancel_and_foreign_generation_do_not_grant(self):
        self.begin()
        with self.assertRaises(ValueError):
            self.complete()
        self.now[0] += 3
        with self.assertRaises(ValueError):
            self.harvest.complete(
                self.account,
                "foreign",
                self.char["id"],
                b"\x02\x00\x06",
                monster=self.monster,
                profession_level=0,
            )
        self.harvest.complete(
            self.account,
            self.gen,
            self.char["id"],
            b"\x03\x00\x06",
            monster=self.monster,
            profession_level=0,
        )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"], []
        )

    def test_expired_lease_and_target_death_reject_finish(self):
        self.begin()
        self.now[0] += 3
        self.monster["hp"] = 0
        with self.assertRaises(ValueError):
            self.complete()
        self.monster["hp"] = 10
        self.now[0] += 10000
        with self.assertRaises(ValueError):
            self.complete()

    def test_local_cooldown_transaction_and_catalog_ownership(self):
        self.configure(cooldown_seconds=10)
        self.begin()
        self.now[0] += 3
        self.complete()
        with self.assertRaisesRegex(ValueError, "regenerating"):
            self.begin()
        self.assertEqual(self.harvest.pending, {})
        self.now[0] += 9.999
        with self.assertRaisesRegex(ValueError, "regenerating"):
            self.begin()
        self.now[0] = 1013.0
        self.begin()
        self.now[0] += 3
        second = self.complete()
        self.assertTrue(second["applied"])
        first_item = self.store.character(self.account, self.char["id"])[
            "inventory_items"
        ][0]
        self.assertEqual(
            (
                first_item["quantity"],
                len(
                    self.store.character(self.account, self.char["id"])[
                        "inventory_items"
                    ]
                ),
            ),
            (2, 1),
        )
        self.assertEqual(second["item"]["uid"], first_item["uid"])
        self.assertEqual(
            second["packets"], [(12470, struct.pack(">qh", first_item["uid"], 1))]
        )
        self.assertEqual(
            sum(
                i["quantity"]
                for i in self.store.character(self.account, self.char["id"])[
                    "inventory_items"
                ]
            ),
            2,
        )
        with self.assertRaises(ValueError):
            action(1740, 3723)
        with self.assertRaises(ValueError):
            decode_result(b"\x02\x00\x08")

    def test_full_base_pocket_merges_existing_room_without_allocating_new_slot(self):
        self.configure(cooldown_seconds=1)
        self.begin()
        self.now[0] += 3
        first = self.complete()["item"]
        base = self.char["inventory_containers"][0]
        with self.store.connection() as db:
            for slot in range(base["capacity"]):
                if slot == first["slot"]:
                    continue
                db.execute(
                    "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                    "VALUES(%s,%s,2021,1,%s,%s)",
                    (2**42 + slot, self.char["id"], base["uid"], slot),
                )
        self.now[0] += 2
        self.begin()
        self.now[0] += 3
        result = self.complete()
        self.assertTrue(result["applied"])
        self.assertEqual(result["item"]["uid"], first["uid"])
        self.assertEqual(result["item"]["quantity"], 2)
        self.assertEqual(
            result["packets"], [(12470, struct.pack(">qh", first["uid"], 1))]
        )
        with self.store.connection() as db:
            count = db.execute(
                "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s "
                "AND reference=2246",
                (self.char["id"],),
            ).fetchone()["n"]
        self.assertEqual(count, 1)

    def test_maximum_existing_stack_uses_new_slot_and_insertion_packet(self):
        from wakfu_server.inventory_move import STACKS

        self.configure(cooldown_seconds=1)
        maximum = STACKS[2246]["maximum"]
        base = self.char["inventory_containers"][0]
        full_uid = 2**43
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,2246,%s,%s,0)",
                (full_uid, self.char["id"], maximum, base["uid"]),
            )
        self.begin()
        self.now[0] += 3
        result = self.complete()
        self.assertTrue(result["applied"])
        self.assertNotEqual(result["item"]["uid"], full_uid)
        self.assertEqual(result["item"]["quantity"], 1)
        self.assertEqual(result["item"]["slot"], 1)
        self.assertEqual(result["packets"][0][0], 12471)

    def test_receipt_sql_failure_rolls_back_merge_quantity_without_uid_allocation(self):
        self.configure(cooldown_seconds=1)
        self.begin()
        self.now[0] += 3
        first = self.complete()["item"]
        with self.store.connection() as db:
            db.execute(
                """CREATE FUNCTION reject_harvest_receipt() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected receipt failure'; END $$"""
            )
            db.execute(
                "CREATE TRIGGER reject_harvest_receipt BEFORE INSERT ON monster_harvest_receipts "
                "FOR EACH ROW EXECUTE FUNCTION reject_harvest_receipt()"
            )
        self.now[0] += 2
        self.begin()
        self.now[0] += 3
        with self.store.connection() as db:
            before_seq = db.execute(
                "SELECT last_value,is_called FROM inventory_uid"
            ).fetchone()
            before_receipts = db.execute(
                "SELECT count(*) AS n FROM monster_harvest_receipts"
            ).fetchone()["n"]
        with self.assertRaises(psycopg.Error):
            self.complete()
        with self.store.connection() as db:
            item = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (first["uid"],)
            ).fetchone()
            after_seq = db.execute(
                "SELECT last_value,is_called FROM inventory_uid"
            ).fetchone()
            after_receipts = db.execute(
                "SELECT count(*) AS n FROM monster_harvest_receipts"
            ).fetchone()["n"]
        self.assertEqual(item["quantity"], 1)
        self.assertEqual(after_seq, before_seq)
        self.assertEqual(after_receipts, before_receipts)

    def test_inventory_full_and_position_change_leave_no_partial_receipt(self):
        self.begin()
        self.now[0] += 3
        with self.store.connection() as db:
            db.execute("UPDATE characters SET x=x+1 WHERE id=%s", (self.char["id"],))
        with self.assertRaises(ValueError):
            self.complete()
        with self.store.connection() as db:
            db.execute("UPDATE characters SET x=x-1 WHERE id=%s", (self.char["id"],))
            base = self.char["inventory_containers"][0]
            for slot in range(base["capacity"]):
                db.execute(
                    "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(%s,%s,%s,%s,%s,%s)",
                    (2**40 + slot, self.char["id"], 2021, 1, base["uid"], slot),
                )
        with self.assertRaises(ValueError):
            self.complete()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM monster_harvest_receipts"
                ).fetchone()["count"],
                0,
            )

    def test_native_stack_limit_rejects_before_occupation(self):
        from wakfu_server.inventory_move import STACKS

        self.configure(quantity=STACKS[2246]["maximum"] + 1)
        with self.assertRaises(ValueError):
            self.harvest.begin(
                self.account,
                self.gen,
                self.char["id"],
                self.body,
                self.monster,
                profession_level=0,
                reachable=True,
            )
        self.assertEqual(self.harvest.pending, {})

    def test_stale_session_cleanup_preserves_new_generation_occupation(self):
        self.begin()
        oldgen = self.gen
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET expires_at='epoch'::timestamptz WHERE account_id=%s",
                (self.account,),
            )
        self.gen = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.gen, self.char["id"])
        self.begin()
        self.assertFalse(self.harvest.cancel(self.char["id"], oldgen))
        self.assertEqual(self.harvest.pending[self.char["id"]]["generation"], self.gen)
        self.now[0] += 3
        self.assertTrue(self.complete()["applied"])

    def test_generation_scoped_cancel_matches_only_current_owner(self):
        self.begin()
        self.assertFalse(self.harvest.cancel(self.char["id"], "unrelated"))
        self.assertTrue(self.harvest.cancel(self.char["id"], self.gen))
        self.assertEqual(self.harvest.pending, {})

    def test_invalid_database_policies_reject_without_occupation(self):
        invalid = (
            {"quantity": True, "cooldown_seconds": 10},
            {"quantity": 0, "cooldown_seconds": 10},
            {"quantity": 1.0, "cooldown_seconds": 10},
            {"quantity": 1, "cooldown_seconds": True},
            {"quantity": 1, "cooldown_seconds": 0},
            {"quantity": 1, "cooldown_seconds": -1},
            {"quantity": 1, "cooldown_seconds": 86401},
            {"quantity": 1, "cooldown_seconds": 10, "extra": 1},
        )
        for value in invalid:
            with self.subTest(policy=value):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE settings SET value=%s WHERE name='monster_harvest'",
                        (Jsonb(value),),
                    )
                with self.assertRaisesRegex(
                    ValueError, "database monster harvest policy"
                ):
                    self.begin()
                self.assertEqual(self.harvest.pending, {})

    def test_policy_quantity_replay_reopen_and_cancel_do_not_spend_resource(self):
        self.configure(quantity=3, cooldown_seconds=10)
        self.begin()
        self.now[0] += 3
        completed = self.complete()
        self.assertTrue(completed["applied"])
        self.assertEqual(completed["item"]["quantity"], 3)
        self.assertFalse(self.complete()["applied"])
        self.assertEqual(
            sum(
                item["quantity"]
                for item in self.store.character(self.account, self.char["id"])[
                    "inventory_items"
                ]
            ),
            3,
        )

        reopened = self.reopen()
        reopened.clock = self.store.clock
        fresh = Harvests(reopened)
        with self.assertRaisesRegex(ValueError, "regenerating"):
            fresh.begin(
                self.account,
                self.gen,
                self.char["id"],
                self.body,
                self.monster,
                profession_level=0,
                reachable=True,
            )
        self.assertEqual(fresh.pending, {})
        self.now[0] += 10
        packet = fresh.begin(
            self.account,
            self.gen,
            self.char["id"],
            self.body,
            self.monster,
            profession_level=0,
            reachable=True,
        )
        self.assertEqual(packet[0], 13597)
        self.assertTrue(fresh.cancel(self.char["id"], self.gen))
        self.assertEqual(fresh.pending, {})
        self.assertEqual(
            sum(
                item["quantity"]
                for item in reopened.character(self.account, self.char["id"])[
                    "inventory_items"
                ]
            ),
            3,
        )

    def test_cooldown_is_shared_between_players_but_scoped_by_map_and_instance(self):
        self.configure(cooldown_seconds=30)
        self.begin()
        self.now[0] += 3
        self.assertTrue(self.complete()["applied"])

        other_account = self.store.register("harvest-second", "local-password")["id"]
        other = self.store.create_character(other_account, "Harvest Second")
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(other_account, other_generation, other["id"])
        other_monster = {**self.monster}
        other_body = self.body
        reopened = self.reopen()
        reopened.clock = self.store.clock
        other_harvest = Harvests(reopened)
        with self.assertRaisesRegex(ValueError, "regenerating"):
            other_harvest.begin(
                other_account,
                other_generation,
                other["id"],
                other_body,
                other_monster,
                profession_level=0,
                reachable=True,
            )

        for map_id, instance_id in (
            (other["map_id"], other["instance_id"] + 1),
            (other["map_id"] + 1, other["instance_id"] + 1),
        ):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=%s WHERE id=%s",
                    (map_id, instance_id, other["id"]),
                )
            other_monster.update(map_id=map_id, instance_id=instance_id)
            packet = other_harvest.begin(
                other_account,
                other_generation,
                other["id"],
                other_body,
                other_monster,
                profession_level=0,
                reachable=True,
            )
            self.assertEqual(packet[0], 13597)
            self.assertTrue(other_harvest.cancel(other["id"], other_generation))

    def test_started_ticket_freezes_quantity_and_cooldown_when_policy_changes(self):
        self.configure(quantity=3, cooldown_seconds=60)
        first = self.harvest
        second = Harvests(self.store)
        first.begin(
            self.account,
            self.gen,
            self.char["id"],
            self.body,
            self.monster,
            profession_level=0,
            reachable=True,
        )
        second.begin(
            self.account,
            self.gen,
            self.char["id"],
            self.body,
            self.monster,
            profession_level=0,
            reachable=True,
        )
        self.configure(quantity=1, cooldown_seconds=1)
        self.now[0] += 3
        self.assertTrue(
            first.complete(
                self.account,
                self.gen,
                self.char["id"],
                b"\x02\x00\x06",
                monster=self.monster,
                profession_level=0,
            )["applied"]
        )
        self.configure(cooldown_seconds=1)
        with self.assertRaisesRegex(ValueError, "regenerating"):
            second.complete(
                self.account,
                self.gen,
                self.char["id"],
                b"\x02\x00\x06",
                monster=self.monster,
                profession_level=0,
            )
        self.assertEqual(
            len(self.store.character(self.account, self.char["id"])["inventory_items"]),
            1,
        )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            3,
        )
        self.assertTrue(second.cancel(self.char["id"], self.gen))
        self.now[0] += 1
        updated = Harvests(self.store)
        with self.assertRaisesRegex(ValueError, "regenerating"):
            updated.begin(
                self.account,
                self.gen,
                self.char["id"],
                self.body,
                self.monster,
                profession_level=0,
                reachable=True,
            )
        # The first ticket's 60-second deadline survives the database policy
        # update; only a new ticket after that deadline uses the new one-second
        # setting.
        self.now[0] += 30
        self.assertTrue(self.store.heartbeat(self.account, self.gen))
        self.now[0] += 29
        updated.begin(
            self.account,
            self.gen,
            self.char["id"],
            self.body,
            self.monster,
            profession_level=0,
            reachable=True,
        )
        self.assertEqual(updated.pending[self.char["id"]]["quantity"], 1)
        self.assertEqual(updated.pending[self.char["id"]]["cooldown_seconds"], 1)

    def test_concurrent_completion_from_separate_harvest_objects_grants_once(self):
        self.configure(quantity=4)
        self.begin()
        second = Harvests(self.store)
        second.pending[self.char["id"]] = copy.deepcopy(
            self.harvest.pending[self.char["id"]]
        )
        second.targets[self.monster["id"]] = self.char["id"]
        self.now[0] += 3
        barrier = threading.Barrier(3)
        results = []
        errors = []

        def finish(harvest):
            try:
                barrier.wait()
                results.append(
                    harvest.complete(
                        self.account,
                        self.gen,
                        self.char["id"],
                        b"\x02\x00\x06",
                        monster=self.monster,
                        profession_level=0,
                    )
                )
            except Exception as error:
                errors.append(error)

        threads = [
            threading.Thread(target=finish, args=(h,)) for h in (self.harvest, second)
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=5)
        self.assertFalse(errors, errors)
        self.assertEqual(sorted(result["applied"] for result in results), [False, True])
        items = self.store.character(self.account, self.char["id"])["inventory_items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["quantity"], 4)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM monster_harvest_receipts"
                ).fetchone()["count"],
                1,
            )
