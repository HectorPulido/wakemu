"""Compose native Drago travel, account chest custody, and fight checkpoint I/O.

All persistent work uses the isolated PostgreSQL schema provided by PostgresCase.
"""
import struct
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from postgres_case import PostgresCase
from test_haven_chest import deposit_body, withdraw_body
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_chest import load as load_chest
from wakfu_server.haven_chest import transfer as chest_transfer
from wakfu_server.haven_chest import validate_open
from wakfu_server.inventory_items import grant
from wakfu_server.native_transports import OBJECTS, TRANSPORTS, bootstrap, resolve
from wakfu_server.transport_discovery import Discoveries
from wakfu_server.world_static import objects as static_objects


class TransportStorageConcurrentPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1000
        self.account = self.store.register("route-chest-owner", "test-password")["id"]
        self.character = self.store.create_character(self.account, "Route Chest Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.character = self.store.character(self.account, self.character["id"])

    def _fight_checkpoint(self):
        account = self.store.register("concurrent-checkpoint", "test-password")["id"]
        character = self.store.create_character(account, "Checkpoint Owner")["id"]
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character)
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (fight_id, character, account, generation),
            )
        owner = Actor(character, 0, (0, 0, 0), 60, 6, 3, 10, 1, account, True)
        opponent = Actor(-200, 1, (1, 0, 0), 12, 6, 3, 5, 1)
        fight = Fight(
            fight_id,
            [owner, opponent],
            {owner.position, opponent.position},
            {0: {owner.position}, 1: {opponent.position}},
        )
        fight.ready(account)
        checkpoints = Checkpoints(self.store)
        revision = checkpoints.save(account, generation, fight)
        return checkpoints, account, generation, fight, revision

    def test_native_drago_chest_custody_and_checkpoint_io_overlap(self):
        # Pick two distinct, actual native Drago endpoints which require no
        # criterion and have one installed arrival altitude. No criteria waiver.
        candidates = [
            row
            for row in TRANSPORTS.values()
            if row["kind"] == 2
            and not row["condition"]
            and row["id"] in OBJECTS
            and len(OBJECTS[row["id"]]["arrival_heights"]) == 1
        ]
        self.assertGreaterEqual(len(candidates), 2)
        source = candidates[0]
        destination = next(
            row
            for row in candidates[1:]
            if row["id"] != source["id"]
            and (OBJECTS[row["id"]]["map_id"], row["x"], row["y"])
            != (OBJECTS[source["id"]]["map_id"], source["x"], source["y"])
        )
        source_object = OBJECTS[source["id"]]
        discovery = Discoveries(self.store)
        discovery.discover(self.account, self.generation, 2, source["id"])
        discovery.discover(self.account, self.generation, 2, destination["id"])
        known = discovery.known(self.account)

        # Establish the actor at the native Drago source through the normal
        # durable transition path, then exercise ordinary native resolution.
        before_kamas = self.store.account_kamas(self.account)
        character = self.store.transition_map(
            self.account,
            self.generation,
            self.character["id"],
            self.character,
            dict(
                map_id=source_object["map_id"],
                instance_id=0,
                x=source["x"],
                y=source["y"],
                z=int(source_object["z"]),
            ),
        )

        def perform_transport_and_chest():
            route = resolve(
                character,
                struct.pack(">qq", source["id"], destination["id"]),
                known_ids=known,
            )
            moved = self.store.transition_map(
                self.account,
                self.generation,
                character["id"],
                character,
                route["destination"],
            )
            persisted = self.store.character(self.account, moved["id"])
            self.assertEqual(
                tuple(
                    persisted[key] for key in ("map_id", "instance_id", "x", "y", "z")
                ),
                tuple(
                    route["destination"][key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                ),
            )
            packets = bootstrap(persisted)
            self.assertTrue(any(opcode == 13974 for opcode, _ in packets))
            with self.assertRaisesRegex(ValueError, "origin.*desynchronized"):
                self.store.transition_map(
                    self.account,
                    self.generation,
                    character["id"],
                    character,
                    route["destination"],
                )

            # The interior is built from the freshly persisted destination.
            # This mirrors production's fresh return point after world travel.
            bag = HavenBagSession(persisted)
            objects = static_objects(9)
            chest_object = next(row for row in objects if row["type"] == "AccountChest")
            actor = dict(
                bag.inside,
                x=chest_object["x"],
                y=chest_object["y"],
                z=chest_object["z"],
            )
            opening_body = struct.pack(">qHH", chest_object["id"], 12, 0)
            opening_id = validate_open(
                actor, bag, opening_body, objects, fight_active=False
            )
            self.assertEqual(opening_id, chest_object["id"])
            opening_token = uuid.uuid4()
            chest = load_chest(
                self.store, self.account, self.generation, character["id"]
            )
            container = self.store.character(self.account, character["id"])[
                "inventory_containers"
            ][0]["uid"]
            item = grant(
                self.store,
                self.account,
                self.generation,
                character["id"],
                reference=2504,
                quantity=3,
                container=container,
                slot=0,
                allowed_references={2504},
            )
            from wakfu_server.item_custody_metadata import snapshot as metadata_snapshot

            with self.store.connection() as db:
                metadata_before = metadata_snapshot(db, item["uid"])
            location = actor

            deposited = chest_transfer(
                self.store,
                self.account,
                self.generation,
                character["id"],
                12038,
                deposit_body(item["uid"], 2, compartment=chest["id"]),
                opening_token=opening_token,
                location=location,
            )
            deposit_retry = chest_transfer(
                self.store,
                self.account,
                self.generation,
                character["id"],
                12038,
                deposit_body(item["uid"], 2, compartment=chest["id"]),
                opening_token=opening_token,
                location=location,
            )
            withdrawn = chest_transfer(
                self.store,
                self.account,
                self.generation,
                character["id"],
                12551,
                withdraw_body(
                    character["id"], 2504, 1, container, compartment=chest["id"]
                ),
                opening_token=opening_token,
                location=location,
            )
            withdraw_retry = chest_transfer(
                self.store,
                self.account,
                self.generation,
                character["id"],
                12551,
                withdraw_body(
                    character["id"], 2504, 1, container, compartment=chest["id"]
                ),
                opening_token=opening_token,
                location=location,
            )
            self.assertTrue(deposited["applied"])
            self.assertFalse(deposit_retry["applied"])
            self.assertTrue(withdrawn["applied"])
            self.assertFalse(withdraw_retry["applied"])
            reopened = self.reopen()
            reopened.clock = self.store.clock
            saved_chest = load_chest(
                reopened, self.account, self.generation, character["id"]
            )
            saved_character = reopened.character(self.account, character["id"])
            with reopened.connection() as db:
                metadata_after = metadata_snapshot(db, item["uid"])
            self.assertEqual(saved_chest, withdraw_retry["chest"])
            self.assertEqual(metadata_after, metadata_before)
            self.assertEqual(
                sum(
                    row["quantity"]
                    for row in saved_character["inventory_items"]
                    if row["reference"] == 2504
                )
                + sum(
                    row["item"]["quantity"]
                    for row in saved_chest["items"]
                    if row["item"]["reference"] == 2504
                ),
                3,
            )
            self.assertIn(
                item["uid"],
                {row["uid"] for row in saved_character["inventory_items"]}
                | {row["item"]["uid"] for row in saved_chest["items"]},
            )
            self.assertEqual(self.store.account_kamas(self.account), before_kamas)
            return saved_chest, bag, chest_object, opening_body, objects

        # A separate account performs real Fight snapshot + checkpoint SQL I/O
        # at the same time as the normal travel and chest transaction sequence.
        (
            checkpoints,
            fight_account,
            fight_generation,
            fight,
            initial_revision,
        ) = self._fight_checkpoint()
        barrier = threading.Barrier(2)

        def checkpoint_during_world_work():
            barrier.wait()
            controlled = next(
                actor for actor in fight.actors.values() if actor.controlled
            )
            controlled.hp = 59
            revision = checkpoints.save(
                fight_account,
                fight_generation,
                fight,
                expected_revision=initial_revision,
            )
            self.assertEqual(revision, initial_revision + 1)
            persisted = checkpoints.read(fight_account, fight.id)
            self.assertEqual(
                persisted["snapshot"]["actors"][str(controlled.id)]["hp"], 59
            )

        def concurrent_world_work():
            barrier.wait()
            return perform_transport_and_chest()

        with ThreadPoolExecutor(max_workers=2) as pool:
            fight_future = pool.submit(checkpoint_during_world_work)
            world_future = pool.submit(concurrent_world_work)
            (
                saved_chest,
                bag,
                chest_object,
                opening_body,
                objects,
            ) = world_future.result()
            fight_future.result()

        # A guest in the owner's bag cannot open the native account chest.
        guest_account = self.store.register("route-chest-guest", "test-password")["id"]
        guest = self.store.create_character(guest_account, "Guest")
        guest_inside = dict(
            guest,
            map_id=9,
            instance_id=bag.bag_instance_id,
            x=chest_object["x"],
            y=chest_object["y"],
            z=chest_object["z"],
        )
        with self.assertRaises(ValueError):
            validate_open(guest_inside, bag, opening_body, objects, fight_active=False)
        self.assertEqual(
            load_chest(self.store, self.account, self.generation, character["id"]),
            saved_chest,
        )
