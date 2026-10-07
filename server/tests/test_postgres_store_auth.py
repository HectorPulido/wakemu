import os
import threading
import struct
import uuid
from concurrent.futures import ThreadPoolExecutor

from postgres_case import PostgresCase


class StoreAuthTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.clock = [1700000000.0]
        self.store.clock = lambda: self.clock[0]
        self.username = "pg_auth_" + uuid.uuid4().hex[:12]
        self.account = self.store.register(self.username, "test-password")["id"]

    def test_canonical_login_duplicate_and_bad_password(self):
        self.assertEqual(
            self.store.authenticate(self.username.upper(), "test-password")["id"],
            self.account,
        )
        with self.assertRaises(ValueError):
            self.store.register(self.username.upper(), "test-password")
        with self.assertRaises(ValueError):
            self.store.authenticate(self.username, "wrong-password")
        with self.store.connection() as db:
            self.assertFalse(
                db.execute(
                    "SELECT is_admin FROM accounts WHERE id=%s", (self.account,)
                ).fetchone()["is_admin"]
            )

    def test_consumable_token_accepts_exactly_one_concurrent_connection(self):
        token = self.store.issue_token(self.account, "ticket")
        barrier = threading.Barrier(2)

        def consume():
            barrier.wait(timeout=5)
            try:
                return (
                    self.store.token(token, "ticket", consume=True)["account_id"]
                    == self.account
                )
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: consume(), range(2)))
        self.assertEqual(sorted(results), [False, True])

    def test_lease_replacement_old_cleanup_and_expiry(self):
        first = self.store.begin_session(self.account, ttl=60)
        second = self.store.begin_session(self.account, ttl=60)
        self.assertFalse(self.store.current_session(self.account, first))
        self.store.end_session(self.account, first)
        self.assertTrue(self.store.current_session(self.account, second))
        self.assertFalse(self.store.heartbeat(self.account, first))
        self.clock[0] += 61
        self.assertFalse(self.store.heartbeat(self.account, second))
        token = self.store.issue_token(self.account, "api", ttl=1)
        self.clock[0] += 2
        with self.assertRaises(ValueError):
            self.store.token(token, "api")

    def test_clear_character_rejects_replaced_and_expired_lease(self):
        first = self.store.begin_session(self.account)
        second = self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            self.store.clear_character(self.account, first)
        self.store.clear_character(self.account, second)
        self.assertTrue(self.store.current_session(self.account, second))
        self.clock[0] += 61
        with self.assertRaises(ValueError):
            self.store.clear_character(self.account, second)

    def test_current_character_session_tracks_selection_clear_replacement_and_expiry(
        self,
    ):
        first_character = self.store.create_character(self.account, "First Character")
        second_character = self.store.create_character(self.account, "Second Character")
        first_generation = self.store.begin_session(self.account, ttl=60)
        self.assertFalse(
            self.store.current_character_session(
                self.account, first_generation, first_character["id"]
            )
        )

        self.store.select_character(
            self.account, first_generation, first_character["id"]
        )
        self.assertTrue(
            self.store.current_character_session(
                self.account, first_generation, first_character["id"]
            )
        )
        self.assertFalse(
            self.store.current_character_session(
                self.account, first_generation, second_character["id"]
            )
        )

        self.store.clear_character(self.account, first_generation)
        self.assertFalse(
            self.store.current_character_session(
                self.account, first_generation, first_character["id"]
            )
        )
        self.store.select_character(
            self.account, first_generation, second_character["id"]
        )
        self.assertTrue(
            self.store.current_character_session(
                self.account, first_generation, second_character["id"]
            )
        )
        self.assertFalse(
            self.store.current_character_session(
                self.account, first_generation, first_character["id"]
            )
        )

        replacement_generation = self.store.begin_session(self.account, ttl=60)
        self.assertFalse(
            self.store.current_character_session(
                self.account, first_generation, second_character["id"]
            )
        )
        self.store.select_character(
            self.account, replacement_generation, first_character["id"]
        )
        self.assertTrue(
            self.store.current_character_session(
                self.account, replacement_generation, first_character["id"]
            )
        )
        self.clock[0] += 61
        self.assertFalse(
            self.store.current_character_session(
                self.account, replacement_generation, first_character["id"]
            )
        )

    def test_inventory_sequence_concurrent_and_rollback_ids_are_not_reused(self):
        from wakfu_server.inventory_uids import allocate

        def allocate_batch(_):
            with self.store.connection() as db:
                return [allocate(db) for _ in range(32)]

        with ThreadPoolExecutor(max_workers=4) as workers:
            batches = list(workers.map(allocate_batch, range(4)))
        values = [value for batch in batches for value in batch]
        self.assertEqual(len(set(values)), 128)
        self.assertTrue(all((1 << 40) <= value < (1 << 63) for value in values))
        with self.assertRaisesRegex(ValueError, "rollback allocation"):
            with self.store.connection() as db:
                abandoned = allocate(db)
                raise ValueError("rollback allocation")
        with self.store.connection() as db:
            self.assertGreater(allocate(db), abandoned)

    def test_concurrent_reservations_cannot_exceed_client_quota(self):
        from wakfu_server.inventory_uids import reserve

        generation = self.store.begin_session(self.account)
        with self.store.connection() as db:
            character_id = db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                "VALUES(%s,%s,%s,15,false,0,0,'[0,0,0]','{}',50,50) RETURNING id",
                (self.account, self.username, self.username),
            ).fetchone()["id"]
            db.execute(
                "UPDATE sessions SET character_id=%s WHERE account_id=%s",
                (character_id, self.account),
            )
        barrier = threading.Barrier(2)

        def attempt(_):
            barrier.wait(timeout=5)
            try:
                return len(
                    reserve(
                        self.store, self.account, generation, character_id, count=80
                    )["uids"]
                )
            except ValueError:
                return 0

        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(sorted(workers.map(attempt, range(2))), [0, 80])
        with self.store.connection() as db:
            count = db.execute(
                "SELECT count(*) AS count FROM inventory_reserved_uids WHERE account_id=%s",
                (self.account,),
            ).fetchone()["count"]
        self.assertEqual(count, 80)

    def test_inventory_initialization_is_atomic_and_concurrent(self):
        from wakfu_server.inventory import initialize, load, bags

        with self.store.connection() as db:
            character_id = db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                "VALUES(%s,%s,%s,15,false,0,0,'[0,0,0]','{}',50,50) RETURNING id",
                (self.account, self.username, self.username),
            ).fetchone()["id"]
        with self.assertRaisesRegex(ValueError, "rollback inventory"):
            with self.store.connection() as db:
                initialize(db, character_id)
                raise ValueError("rollback inventory")
        with self.store.connection() as db:
            self.assertEqual(load(db, character_id), [])
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_initialized WHERE character_id=%s",
                    (character_id,),
                ).fetchone()
            )
        barrier = threading.Barrier(2)

        def initialize_once(_):
            barrier.wait(timeout=5)
            with self.store.connection() as db:
                initialize(db, character_id)
                return load(db, character_id)

        with ThreadPoolExecutor(max_workers=2) as workers:
            first, second = list(workers.map(initialize_once, range(2)))
        self.assertEqual(first, second)
        self.assertEqual([row["capacity"] for row in first], [30, 4])
        self.assertEqual(len({row["uid"] for row in first}), 2)
        self.assertTrue(all(row["uid"] >= (1 << 40) for row in first))
        self.assertEqual(
            bags({"id": character_id, "inventory_containers": first})[:2], b"\x00\x02"
        )

    def test_item_element_copy_and_hydration_preserve_selection(self):
        from wakfu_server.inventory import initialize, load
        from wakfu_server.inventory_items import load as load_items
        from wakfu_server.inventory_elements import save, copy

        with self.store.connection() as db:
            character_id = db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                "VALUES(%s,%s,%s,15,false,0,0,'[0,0,0]','{}',50,50) RETURNING id",
                (self.account, self.username, self.username),
            ).fetchone()["id"]
            initialize(db, character_id)
            container = load(db, character_id)[0]["uid"]
            ids = []
            for slot in range(3):
                ids.append(
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,2175,1,%s,%s) RETURNING uid",
                        (character_id, container, slot),
                    ).fetchone()["uid"]
                )
            save(db, ids[0], {"damage_elements": 10, "resistance_elements": 20})
            copy(db, ids[0], ids[1])
            copy(db, ids[2], ids[2])  # Absent options stay absent.
        with self.store.connection() as db:
            items = load_items(db, character_id)
        self.assertEqual([item["uid"] for item in items], ids)
        for item in items[:2]:
            self.assertEqual(
                (item["damage_elements"], item["resistance_elements"]), (10, 20)
            )
        self.assertNotIn("damage_elements", items[2])

    def test_concurrent_item_grants_serialize_occupied_slot(self):
        from wakfu_server.inventory import initialize, load
        from wakfu_server.inventory_items import grant, load as load_items

        generation = self.store.begin_session(self.account)
        with self.store.connection() as db:
            character_id = db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                "VALUES(%s,%s,%s,15,false,0,0,'[0,0,0]','{}',50,50) RETURNING id",
                (self.account, self.username, self.username),
            ).fetchone()["id"]
            initialize(db, character_id)
            container = load(db, character_id)[0]["uid"]
            db.execute(
                "UPDATE sessions SET character_id=%s WHERE account_id=%s",
                (character_id, self.account),
            )
        barrier = threading.Barrier(2)

        def attempt(_):
            barrier.wait(timeout=5)
            try:
                grant(
                    self.store,
                    self.account,
                    generation,
                    character_id,
                    reference=2175,
                    quantity=1,
                    container=container,
                    slot=0,
                    allowed_references={2175},
                )
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(sorted(workers.map(attempt, range(2))), [False, True])
        with self.store.connection() as db:
            self.assertEqual(len(load_items(db, character_id)), 1)

    def test_create_character_hydrates_all_initial_domains(self):
        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name, breed=15)
        self.assertEqual(character["xp"], 0)
        self.assertEqual(character["kamas"], 0)
        self.assertEqual(character["hp"], character["max_hp"])
        self.assertGreater(character["hp"], 0)
        self.assertEqual(character["active_build_index"], 0)
        self.assertEqual(character["inventory_items"], [])
        self.assertEqual(len(character["inventory_containers"]), 2)
        self.assertEqual(len(character["haven_bag"]["rooms"]), 9)
        self.assertEqual(self.store.character(self.account, character["id"]), character)
        with self.assertRaises(ValueError):
            self.store.create_character(self.account, name.upper(), breed=15)
        self.assertEqual(len(self.store.characters(self.account)), 1)

    def test_character_capacity_serializes_concurrent_creations(self):
        self.store.max_characters = 1
        barrier = threading.Barrier(2)
        suffix = "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:8])

        def attempt(index):
            barrier.wait(timeout=5)
            try:
                self.store.create_character(
                    self.account, "Audit " + suffix + chr(97 + index)
                )
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(sorted(workers.map(attempt, range(2))), [False, True])
        self.assertEqual(len(self.store.characters(self.account)), 1)

    def test_selection_and_concurrent_moves_reject_stale_origin(self):
        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        start = {key: character[key] for key in ("x", "y", "z")}
        barrier = threading.Barrier(2)

        def attempt(index):
            barrier.wait(timeout=5)
            end = dict(start, x=start["x"] + index + 1)
            try:
                self.store.move(self.account, generation, character["id"], start, end)
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(sorted(workers.map(attempt, range(2))), [False, True])
        updated = self.store.character(self.account, character["id"])
        self.assertIn(updated["x"], (start["x"] + 1, start["x"] + 2))
        self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            self.store.select_character(self.account, generation, character["id"])
        with self.assertRaises(ValueError):
            self.store.move(self.account, generation, character["id"], start, start)

    def test_native_split_replay_and_merge_preserve_quantity(self):
        from wakfu_server.inventory_items import grant
        from wakfu_server.inventory_uids import reserve
        from wakfu_server.inventory_move import transfer

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        source, target = [bag["uid"] for bag in character["inventory_containers"]]
        item = grant(
            self.store,
            self.account,
            generation,
            character["id"],
            reference=12,
            quantity=5,
            container=source,
            slot=0,
            allowed_references={12},
        )
        clone = reserve(self.store, self.account, generation, character["id"], count=1)[
            "uids"
        ][0]
        body = struct.pack(">qqqhBqh", item["uid"], target, source, 0, 1, clone, 2)
        result = transfer(self.store, self.account, generation, character["id"], body)
        self.assertTrue(result["applied"])
        quantities = {
            entry["uid"]: entry["quantity"]
            for entry in result["character"]["inventory_items"]
        }
        self.assertEqual(quantities, {item["uid"]: 3, clone: 2})
        self.assertFalse(
            transfer(self.store, self.account, generation, character["id"], body)[
                "applied"
            ]
        )
        changed = struct.pack(">qqqhBqh", item["uid"], target, source, 1, 1, clone, 1)
        with self.assertRaises(ValueError):
            transfer(self.store, self.account, generation, character["id"], changed)
        merge = struct.pack(">qqqhB", clone, source, target, 0, 0)
        result = transfer(self.store, self.account, generation, character["id"], merge)
        self.assertEqual(
            [
                (entry["uid"], entry["quantity"])
                for entry in result["character"]["inventory_items"]
            ],
            [(item["uid"], 5)],
        )

    def test_stacked_bag_equip_and_remove_preserve_owned_units(self):
        from wakfu_server.inventory_items import grant
        from wakfu_server.inventory_bags import equip, remove

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        base = character["inventory_containers"][0]["uid"]
        item = grant(
            self.store,
            self.account,
            generation,
            character["id"],
            reference=2603,
            quantity=3,
            container=base,
            slot=0,
            allowed_references={2603},
        )
        result = equip(
            self.store,
            self.account,
            generation,
            character["id"],
            struct.pack(">qqqb", item["uid"], base, character["id"], 2),
        )
        equipped = next(
            bag
            for bag in result["character"]["inventory_containers"]
            if bag["kind"] == 2
        )
        self.assertNotEqual(equipped["uid"], item["uid"])
        self.assertEqual(result["character"]["inventory_items"][0]["quantity"], 2)
        result = remove(
            self.store,
            self.account,
            generation,
            character["id"],
            struct.pack(">qqqqb", base, equipped["uid"], equipped["uid"], base, -1),
        )
        quantities = {
            entry["uid"]: entry["quantity"]
            for entry in result["character"]["inventory_items"]
        }
        self.assertEqual(quantities, {item["uid"]: 2, equipped["uid"]: 1})
        self.assertEqual(len(result["character"]["inventory_containers"]), 2)
        self.assertEqual(
            self.store.character(self.account, character["id"])["inventory_items"],
            result["character"]["inventory_items"],
        )

    def test_health_regeneration_utc_stale_update_and_borrowed_rollback(self):
        from wakfu_server.health_store import initialize, sync, tick

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        initialized = initialize(self.store, self.account, generation, character["id"])
        maximum = initialized["max_hp"]
        damaged = sync(
            self.store,
            self.account,
            generation,
            character["id"],
            maximum,
            maximum - 10,
            coefficient=1000,
            now_ms=1700000000000,
        )
        self.assertEqual(damaged["hp"], maximum - 10)
        with self.assertRaises(ValueError):
            sync(
                self.store,
                self.account,
                generation,
                character["id"],
                maximum,
                maximum - 1,
            )
        regenerated = tick(
            self.store,
            self.account,
            generation,
            character["id"],
            maximum - 10,
            now_ms=1700000001000,
        )
        self.assertGreater(regenerated["hp"], maximum - 10)
        with self.assertRaises(ValueError):
            tick(
                self.store,
                self.account,
                generation,
                character["id"],
                regenerated["hp"],
                now_ms=1699999999000,
            )
        with self.assertRaisesRegex(ValueError, "rollback health"):
            with self.store.connection() as db:
                initialize(self.store, self.account, generation, character["id"], db=db)
                raise ValueError("rollback health")
        self.assertEqual(
            self.store.character(self.account, character["id"])["hp"], regenerated["hp"]
        )

    def test_build_save_activate_delete_are_persistent(self):
        from wakfu_server.wire import proto_field
        from wakfu_server.health_store import initialize

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        initialize(self.store, self.account, generation, character["id"])
        sheet = b"".join(
            proto_field(tag, value)
            for tag, value in [(8, 1), (18, b"Postgres build"), (24, 1), (56, 0)]
        )
        blobs = dict(sheet=sheet, equipment=b"", deck=b"", aptitudes=b"")
        saved = self.store.save_build(
            self.account, generation, character["id"], 1, blobs
        )
        self.assertIn(1, saved["builds"])
        active = self.store.activate_build(
            self.account, generation, character["id"], 1, in_fight=False
        )
        self.assertEqual(active["active_build_index"], 1)
        self.assertEqual(active["build_selection_revision"], 1)
        self.assertEqual(
            self.store.character(self.account, character["id"])["active_build_index"], 1
        )
        with self.assertRaises(ValueError):
            self.store.delete_build(
                self.account, generation, character["id"], 1, in_fight=True
            )
        deleted = self.store.delete_build(
            self.account, generation, character["id"], 1, in_fight=False
        )
        self.assertNotIn(1, deleted["builds"])
        self.assertEqual(deleted["active_build_index"], 0)
        self.assertEqual(deleted["build_selection_revision"], 2)
        self.assertLessEqual(deleted["hp"], deleted["max_hp"])

    def test_map_transition_and_wallet_have_single_authority(self):
        self.assertEqual(self.store.account_kamas(self.account), 0)
        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        keys = ("map_id", "instance_id", "x", "y", "z")
        source = {key: character[key] for key in keys}
        destination = dict(source, map_id=1, instance_id=10, x=2, y=3, z=0)
        transitioned = self.store.transition_map(
            self.account, generation, character["id"], source, destination
        )
        self.assertEqual({key: transitioned[key] for key in keys}, destination)
        with self.assertRaises(ValueError):
            self.store.transition_map(
                self.account, generation, character["id"], source, destination
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=123 WHERE account_id=%s",
                (self.account,),
            )
        self.assertEqual(self.store.account_kamas(self.account), 123)
        self.assertEqual(
            self.store.character(self.account, character["id"])["kamas"], 123
        )

    def test_admin_roles_audit_and_json_command_policy(self):
        from wakfu_server.command_permissions import (
            authorize_command,
            is_admin,
            set_admin,
        )

        self.assertFalse(is_admin(self.store, self.account))
        authorize_command(self.store, self.account, "!pos")
        with self.assertRaises(PermissionError):
            authorize_command(self.store, self.account, "!nivel 100")
        set_admin(
            self.store,
            self.account,
            True,
            operator="postgres-test",
            reason="test grant",
        )
        self.assertTrue(is_admin(self.store, self.account))
        authorize_command(self.store, self.account, "!nivel 100")
        set_admin(
            self.store,
            self.account,
            False,
            operator="postgres-test",
            reason="test revoke",
        )
        with self.assertRaises(PermissionError):
            authorize_command(self.store, self.account, "!nivel 100")
        with self.store.connection() as db:
            rows = list(
                db.execute(
                    "SELECT is_admin,changed_at FROM admin_role_audit WHERE account_id=%s ORDER BY id",
                    (self.account,),
                )
            )
        self.assertEqual([row["is_admin"] for row in rows], [True, False])
        self.assertTrue(all(row["changed_at"].tzinfo is not None for row in rows))

    def test_tutorial_transport_and_profession_state_persist(self):
        from wakfu_server import tutorials
        from wakfu_server.transport_discovery import Discoveries
        from wakfu_server.profession_store import ensure_learned, learned, level
        import json
        from wakfu_server.paths import DATA_ROOT

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        tutorials.payload(self.store, self.account)
        tutorials.update(
            self.store, self.account, generation, struct.pack(">BIi", 1, 1, 189)
        )
        with self.store.connection() as db:
            self.assertTrue(
                db.execute(
                    "SELECT pending FROM account_tutorials WHERE account_id=%s AND tutorial_id=189",
                    (self.account,),
                ).fetchone()["pending"]
            )
        tutorials.update(
            self.store, self.account, generation, struct.pack(">BIi", 0, 1, 189)
        )
        discoveries = Discoveries(self.store)
        self.assertTrue(discoveries.discover(self.account, generation, 1, 1))
        self.assertFalse(discoveries.discover(self.account, generation, 1, 1))
        self.assertIn(1, discoveries.known(self.account)[1])
        profession = json.loads((DATA_ROOT / "profession-actions.json").read_text())[
            "profession_ids"
        ][0]
        ensure_learned(
            self.store, self.account, generation, character["id"], [profession]
        )
        self.assertTrue(
            learned(self.store, self.account, generation, character["id"], profession)
        )
        self.assertEqual(
            level(self.store, self.account, generation, character["id"], profession), 0
        )
        self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            discoveries.discover(self.account, generation, 1, 2)

    def test_haven_bag_json_mutations_and_stale_lease(self):
        from wakfu_server.haven_bag_store import save

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        updated = save(
            self.store,
            self.account,
            generation,
            character["id"],
            locked=True,
            rooms=character["haven_bag"]["rooms"],
            furniture=[],
            access=character["haven_bag"]["access"],
        )
        self.assertTrue(updated["haven_bag"]["locked"])
        self.assertEqual(
            self.store.character(self.account, character["id"])["haven_bag"],
            updated["haven_bag"],
        )
        self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            save(self.store, self.account, generation, character["id"], locked=False)
        self.assertTrue(
            self.store.character(self.account, character["id"])["haven_bag"]["locked"]
        )

    def test_fight_checkpoint_json_revision_and_terminal_state(self):
        from types import SimpleNamespace
        from wakfu_server.fight_checkpoint_store import Checkpoints

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, character["id"], self.account),
            )
        fight = SimpleNamespace(
            id=fight_id,
            actors={
                character["id"]: SimpleNamespace(
                    controlled=True, owner_id=self.account, hp=character["hp"]
                )
            },
        )
        checkpoints = Checkpoints(self.store)
        self.assertEqual(checkpoints.save(self.account, generation, fight), 1)
        fight.actors[character["id"]].hp -= 1
        self.assertEqual(
            checkpoints.save(self.account, generation, fight, expected_revision=1), 2
        )
        with self.assertRaises(ValueError):
            checkpoints.save(self.account, generation, fight, expected_revision=1)
        saved = checkpoints.read(self.account, fight_id)
        self.assertEqual(
            saved["snapshot"]["actors"][str(character["id"])]["hp"], character["hp"] - 1
        )
        self.assertEqual(
            checkpoints.end(self.account, generation, fight_id, expected_revision=2), 3
        )
        with self.assertRaises(ValueError):
            checkpoints.save(self.account, generation, fight, expected_revision=3)

    def test_reward_is_once_across_concurrency_and_session_replacement(self):
        from types import SimpleNamespace
        from wakfu_server.combat_rewards import award, Policy

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, character["id"], self.account),
            )
        fight = SimpleNamespace(
            id=fight_id,
            phase="finished",
            winner=0,
            actors={
                character["id"]: SimpleNamespace(
                    controlled=True, owner_id=self.account, team=0
                )
            },
        )
        barrier = threading.Barrier(2)

        def attempt(_):
            barrier.wait(timeout=5)
            return award(
                self.store,
                self.account,
                generation,
                character["id"],
                fight,
                Policy(xp=1000, kamas=10),
            )["awarded"]

        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(sorted(workers.map(attempt, range(2))), [False, True])
        replacement = self.store.begin_session(self.account)
        self.store.select_character(self.account, replacement, character["id"])
        self.assertFalse(
            award(
                self.store,
                self.account,
                replacement,
                character["id"],
                fight,
                Policy(xp=1000, kamas=10),
            )["awarded"]
        )
        saved = self.store.character(self.account, character["id"])
        self.assertEqual((saved["xp"], saved["kamas"]), (1000, 10))
        self.assertGreater(saved["level"], 1)
        self.assertEqual(saved["hp"], saved["max_hp"])

    def test_fight_health_exit_once_and_preserves_later_world_damage(self):
        from types import SimpleNamespace
        from wakfu_server.combat_health import persist
        from wakfu_server.health_store import sync

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, character["id"], self.account),
            )
        fight = SimpleNamespace(
            id=fight_id,
            phase="finished",
            actors={
                character["id"]: SimpleNamespace(
                    controlled=True,
                    owner_id=self.account,
                    hp=character["hp"] - 5,
                    max_hp=character["max_hp"],
                )
            },
        )
        result = persist(self.store, self.account, generation, character, fight)
        self.assertTrue(result["applied"])
        hp = result["character"]["hp"]
        sync(self.store, self.account, generation, character["id"], hp, hp - 1)
        duplicate = persist(self.store, self.account, generation, character, fight)
        self.assertFalse(duplicate["applied"])
        self.assertEqual(duplicate["character"]["hp"], hp - 1)
        replacement = self.store.begin_session(self.account)
        self.store.select_character(self.account, replacement, character["id"])
        self.assertFalse(
            persist(self.store, self.account, replacement, character, fight)["applied"]
        )

    def test_buffered_position_flush_and_stale_generation_eviction(self):
        from wakfu_server.position_buffer import Positions

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        positions = Positions(
            self.store,
            lease_active=lambda account, gen, cid: self.store.current_session(
                account, gen
            ),
        )
        positions.attach(self.account, generation, character)
        end = {axis: character[axis] for axis in ("x", "y", "z")}
        end["x"] += 1
        moved = positions.move(
            self.account, generation, character["id"], character, end
        )
        self.assertEqual(
            self.store.character(self.account, character["id"])["x"], character["x"]
        )
        self.assertEqual(positions.flush(), 1)
        self.assertEqual(
            self.store.character(self.account, character["id"])["x"], end["x"]
        )

        positions.move(
            self.account, generation, character["id"], moved, dict(end, x=end["x"] + 1)
        )
        self.store.begin_session(self.account)
        self.assertEqual(positions.flush(), 0)
        self.assertEqual(
            positions.evictions, [(self.account, generation, character["id"])]
        )
        self.assertEqual(
            self.store.character(self.account, character["id"])["x"], end["x"]
        )

    def test_redis_position_recovery_and_flush_use_postgres_baselines(self):
        import redis
        from wakfu_server.position_redis import Journal, RedisPositions

        client = redis.Redis.from_url(
            os.environ.get("WAKFU_REDIS_TEST_URL", "redis://redis:6379/15"),
            socket_timeout=2,
        )
        namespace = "wakemu:postgres-test:positions:" + uuid.uuid4().hex
        self.addCleanup(client.close)
        self.addCleanup(client.delete, namespace)
        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        journal = Journal(client, namespace=namespace)
        positions = RedisPositions(
            self.store,
            lease_active=lambda a, g, c: self.store.current_session(a, g),
            journal=journal,
        )
        positions.attach(self.account, generation, character)
        end = {axis: character[axis] for axis in ("x", "y", "z")}
        end["x"] += 1
        positions.move(self.account, generation, character["id"], character, end)
        self.assertEqual(journal.recover(self.store)["recovered"], 1)
        self.assertEqual(
            self.store.character(self.account, character["id"])["x"], end["x"]
        )
        self.assertEqual(list(journal.records()), [])
        current = self.store.character(self.account, character["id"])
        restored = RedisPositions(
            self.store,
            lease_active=lambda a, g, c: self.store.current_session(a, g),
            journal=journal,
        )
        restored.attach(self.account, generation, current)
        restored.move(
            self.account,
            generation,
            character["id"],
            current,
            dict(end, x=end["x"] + 1),
        )
        self.assertEqual(restored.flush(), 1)
        self.assertEqual(list(journal.records()), [])

    def test_food_consumption_and_healing_are_atomic(self):
        from wakfu_server.inventory_consumables import CATALOG, healing_plan, use
        from wakfu_server.inventory_items import grant
        from wakfu_server.health_store import sync

        reference = None
        for candidate in CATALOG:
            try:
                healing_plan(candidate)
                reference = candidate
                break
            except ValueError:
                continue
        self.assertIsNotNone(reference)
        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        container = character["inventory_containers"][0]["uid"]
        item = grant(
            self.store,
            self.account,
            generation,
            character["id"],
            reference=reference,
            quantity=2,
            container=container,
            slot=0,
            allowed_references={reference},
        )
        wounded = sync(
            self.store,
            self.account,
            generation,
            character["id"],
            character["hp"],
            character["hp"] - 10,
        )
        body = struct.pack(">qB", item["uid"], 0)
        result = use(
            self.store,
            self.account,
            generation,
            character["id"],
            body,
            expected_hp=wounded["hp"],
            in_fight=False,
        )
        self.assertGreater(result["healed"], 0)
        self.assertEqual(result["character"]["inventory_items"][0]["quantity"], 1)
        with self.assertRaises(ValueError):
            use(
                self.store,
                self.account,
                generation,
                character["id"],
                body,
                expected_hp=wounded["hp"],
                in_fight=False,
            )
        self.assertEqual(
            self.store.character(self.account, character["id"])["inventory_items"][0][
                "quantity"
            ],
            1,
        )

    def test_http_character_create_and_read_encode_postgres_timestamps(self):
        import json
        import urllib.request
        from wakfu_server.api import serve_api

        ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            ready.set()

        thread = threading.Thread(
            target=serve_api,
            args=(self.store, "127.0.0.1", 0),
            kwargs={"on_ready": on_ready},
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(5))
        server = servers[0]
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        token = self.store.issue_token(self.account, "api")
        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        base = f"http://127.0.0.1:{server.server_port}"
        request = urllib.request.Request(
            base + "/characters",
            data=json.dumps({"name": name}).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
            },
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 201)
            created = json.load(response)
        self.assertTrue(created["created_at"].endswith("+00:00"))
        request = urllib.request.Request(
            base + "/characters", headers={"Authorization": "Bearer " + token}
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(json.load(response)[0]["id"], created["id"])

    def test_build_delete_failure_rolls_back_sheet_selection_and_health(self):
        from unittest.mock import patch
        from wakfu_server.wire import proto_field

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        sheet = b"".join(
            proto_field(tag, value)
            for tag, value in [(8, 1), (18, b"Atomic build"), (24, 1), (56, 0)]
        )
        self.store.save_build(
            self.account,
            generation,
            character["id"],
            1,
            dict(sheet=sheet, equipment=b"", deck=b"", aptitudes=b""),
        )
        before = self.store.activate_build(
            self.account, generation, character["id"], 1, in_fight=False
        )
        hydrate = self.store.character
        calls = [0]

        def fail_after_mutations(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 2:
                raise ValueError("injected post-delete failure")
            return hydrate(*args, **kwargs)

        with patch.object(self.store, "character", side_effect=fail_after_mutations):
            with self.assertRaisesRegex(ValueError, "post-delete"):
                self.store.delete_build(
                    self.account, generation, character["id"], 1, in_fight=False
                )
        after = self.store.character(self.account, character["id"])
        for field in (
            "builds",
            "active_build_index",
            "build_selection_revision",
            "hp",
            "max_hp",
        ):
            self.assertEqual(after[field], before[field])

    def test_group_database_claims_serialize_workers_and_npc_identity(self):
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.monsters import owned_instance

        instance_id = int(uuid.uuid4().hex[:12], 16)
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]

        def cleanup_groups():
            with self.store.connection() as db:
                db.execute(
                    "DELETE FROM combat_groups WHERE instance_id=%s", (instance_id,)
                )
                db.execute("DELETE FROM combat_fights WHERE id=%s", (fight_id,))

        self.addCleanup(cleanup_groups)
        members = [
            owned_instance(
                5525, 1, -200, map_id=1134, instance_id=instance_id, x=-7, y=-7, z=-1
            )
        ]
        first, second = PersistentGroups(self.store), PersistentGroups(self.store)
        key = first.register(1134, instance_id, 501, members)
        self.assertEqual(second.register(1134, instance_id, 501, members), key)
        with self.assertRaises(ValueError):
            second.register(1134, instance_id, 502, members)
        moved = [dict(members[0], x=-6)]
        self.assertTrue(first.move_members(key, members, moved))
        self.assertFalse(second.move_members(key, members, moved))
        self.assertEqual(second.register_seed(*key, members), key)
        self.assertEqual(
            second.available(1134, instance_id)[0]["members"], tuple(moved)
        )
        with self.assertRaises(ValueError):
            second.move_members(key, moved, [dict(moved[0], level=99)])
        members = moved
        barrier = threading.Barrier(2)

        def attempt(registry):
            barrier.wait(timeout=5)
            try:
                return registry.claim(key, "test-generation", fight_id)[0]
            except ValueError:
                return None

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(attempt, (first, second)))
        self.assertEqual(sum(value is not None for value in results), 1)
        lease = next(value for value in results if value is not None)
        self.assertTrue(first.finish(lease, defeated=True))
        self.assertFalse(second.finish(lease, defeated=True))
        self.assertEqual(second.respawn(key), tuple(members))

    def test_fight_identity_and_finish_roll_back_with_report_transaction(self):
        from wakfu_server.fight_store import create, finish

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        first = create(self.store, self.account, generation, character["id"])
        second = create(self.store, self.account, generation, character["id"])
        self.assertGreater(second, first)
        self.assertLess(second, 1 << 31)
        with self.assertRaisesRegex(ValueError, "report failure"):
            with self.store.connection() as db:
                finish(self.store, db, self.account, generation, character["id"], first)
                raise ValueError("report failure")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (first,)
                ).fetchone()["status"],
                "placement",
            )
            finish(self.store, db, self.account, generation, character["id"], first)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (first,)
                ).fetchone()["status"],
                "finished",
            )

    def test_fight_activation_abort_and_startup_recovery_preserve_finished(self):
        from wakfu_server.fight_store import create, activate, abort, finish
        from wakfu_server.fight_checkpoint_store import Checkpoints

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        active_id = create(self.store, self.account, generation, character["id"])
        activate(self.store, self.account, generation, character["id"], active_id)
        self.assertTrue(abort(self.store, self.account, character["id"], active_id))
        self.assertFalse(abort(self.store, self.account, character["id"], active_id))
        with self.assertRaises(ValueError):
            activate(self.store, self.account, generation, character["id"], active_id)
        finished_id = create(self.store, self.account, generation, character["id"])
        with self.store.connection() as db:
            finish(
                self.store, db, self.account, generation, character["id"], finished_id
            )
        pending_id = create(self.store, self.account, generation, character["id"])
        Checkpoints(self.store).recover_interrupted()
        with self.store.connection() as db:
            rows = {
                row["id"]: row["status"]
                for row in db.execute(
                    "SELECT id,status FROM combat_fights WHERE id=ANY(%s)",
                    ([active_id, finished_id, pending_id],),
                )
            }
        self.assertEqual(
            rows, {active_id: "aborted", finished_id: "finished", pending_id: "aborted"}
        )

    def test_monster_harvest_receipt_and_explicit_cooldown(self):
        from wakfu_server.monster_collect import Harvests
        from wakfu_server.profession_store import ensure_learned
        from wakfu_server.wire import proto_field
        from psycopg.types.json import Jsonb

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        ensure_learned(self.store, self.account, generation, character["id"], [74])
        monster = dict(
            id=-int(uuid.uuid4().hex[:15], 16),
            ref=1,
            hp=10,
            map_id=character["map_id"],
            instance_id=character["instance_id"],
            # Verified walkable surface in map 1134, region 79301.
            x=-18,
            y=116,
            z=-4,
        )
        body = proto_field(8, 3723) + proto_field(16, monster["id"] % (1 << 64))
        harvests = Harvests(self.store)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_harvest'",
                (Jsonb({"quantity": 1, "cooldown_seconds": 20}),),
            )

        def begin():
            harvests.begin(
                self.account,
                generation,
                character["id"],
                body,
                monster,
                profession_level=0,
                reachable=True,
            )

        def complete():
            return harvests.complete(
                self.account,
                generation,
                character["id"],
                b"\x02\x00\x06",
                monster=monster,
                profession_level=0,
            )

        begin()
        self.clock[0] += 3
        self.assertTrue(complete()["applied"])
        completed_at = self.clock[0]
        self.assertFalse(complete()["applied"])
        with self.assertRaisesRegex(ValueError, "regenerating"):
            begin()
        self.clock[0] = completed_at + 19.999
        with self.assertRaisesRegex(ValueError, "regenerating"):
            begin()
        self.clock[0] = completed_at + 20.0
        begin()
        self.clock[0] += 3
        self.assertTrue(complete()["applied"])
        self.assertEqual(
            sum(
                item["quantity"]
                for item in self.store.character(self.account, character["id"])[
                    "inventory_items"
                ]
            ),
            2,
        )

    def test_planting_atomic_consumption_replay_occupied_cell_and_growth(self):
        from wakfu_server.inventory_items import grant
        from wakfu_server import planting
        from wakfu_server.planting_runtime import Plantings
        from wakfu_server.combat_groups import Groups

        name = "Audit " + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
        character = self.store.create_character(self.account, name)
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, character["id"])
        instance = uuid.uuid4().int % (2**60)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET instance_id=%s WHERE id=%s",
                (instance, character["id"]),
            )
        character = self.store.character(self.account, character["id"])
        from wakfu_server.profession_store import ensure_learned

        ensure_learned(self.store, self.account, generation, character["id"], [72])

        def cleanup_resources():
            with self.store.connection() as db:
                db.execute(
                    "DELETE FROM planting_growth_outbox WHERE (resource->>'instance_id')::bigint=%s",
                    (instance,),
                )
                db.execute(
                    "DELETE FROM planted_resources WHERE instance_id=%s", (instance,)
                )

        self.addCleanup(cleanup_resources)
        item = grant(
            self.store,
            self.account,
            generation,
            character["id"],
            reference=4275,
            quantity=3,
            container=character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={4275},
        )
        body = struct.pack(
            ">iqii", planting.SEEDS[4275]["action_id"], item["uid"], 10, 11
        )
        prepared = planting.prepare(
            self.store,
            self.account,
            generation,
            character,
            body,
            authorize_cell=lambda *args: 0,
            open_test_policy=True,
        )
        kwargs = dict(
            stage=1, creation_time=int(self.clock[0] * 1000), result_prefix=(0, 1)
        )
        operation = uuid.uuid4().hex
        result = planting.complete(
            self.store,
            self.account,
            generation,
            prepared,
            operation_id=operation,
            **kwargs,
        )
        self.assertFalse(result["duplicate"])
        self.assertTrue(
            planting.complete(
                self.store,
                self.account,
                generation,
                prepared,
                operation_id=operation,
                **kwargs,
            )["duplicate"]
        )
        with self.assertRaises(ValueError):
            planting.complete(
                self.store,
                self.account,
                generation,
                prepared,
                operation_id=uuid.uuid4().hex,
                **kwargs,
            )
        self.assertEqual(
            self.store.character(self.account, character["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
        )
        runtime = Plantings(self.store, growth_seconds=30)
        self.assertEqual(len(runtime.snapshots(character["map_id"], instance)), 1)
        self.clock[0] += 31
        deliveries = []
        self.assertEqual(len(runtime.mature(Groups(), publish=deliveries.append)), 1)
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0]["packets"][0][0], 12782)
        self.assertEqual(runtime.mature(Groups(), publish=deliveries.append), [])
        self.assertEqual(len(deliveries), 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT stage FROM planted_resources WHERE instance_id=%s",
                    (instance,),
                ).fetchone()["stage"],
                2,
            )
