import unittest, struct
from wakfu_server.native_transports import resolve, registration, bootstrap
from wakfu_server.transport_discovery import known_all


from postgres_case import PostgresCase


class NativeTransportTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1000
        self.character = dict(
            id=7, account_id=9, map_id=1134, instance_id=0, x=-10, y=-11, z=-1
        )

    def test_all_native_zaaps_geometry_and_roundtrip(self):
        known = known_all()[1]
        self.assertEqual(len(known), 45)
        for target in known:
            route = resolve(
                self.character,
                struct.pack(">qq", 31316, target),
                known_ids=known,
                waive_criteria=True,
            )
            moved = dict(self.character, **route["destination"])
            back = resolve(
                moved,
                struct.pack(">qq", target, 31316),
                known_ids=known,
                waive_criteria=True,
            )
            self.assertEqual(back["destination"]["map_id"], 1134)
            self.assertEqual(back["destination"]["z"], -1)

    def test_native_register_and_rejections(self):
        body = struct.pack(">qH", 31316, 24) + b"\0\0"
        self.assertEqual(registration(self.character, body), (1, 31316))
        with self.assertRaises(ValueError):
            resolve(self.character, struct.pack(">qq", 31316, 31316), known_ids=())
        with self.assertRaises(ValueError):
            registration(dict(self.character, instance_id=7), body)
        with self.assertRaises(ValueError):
            registration(dict(self.character, x=50), body)

    def test_clean_bootstrap_contains_only_own_identity(self):
        packets = bootstrap(self.character)
        self.assertEqual([x[0] for x in packets], [13256, 13974, 12318])
        body = packets[1][1]
        self.assertEqual(struct.unpack_from(">H", body)[0], 56)
        self.assertEqual(struct.unpack_from(">q", body, 3)[0], 7)
        self.assertEqual(struct.unpack_from(">q", body, 12)[0], 9)

    def test_concurrent_travel_persists_all_routes_without_cross_account_writes(self):
        from concurrent.futures import ThreadPoolExecutor

        store = self.store
        travelers = []
        for number in range(3):
            account = store.register("traveler" + str(number), "local-test-password")[
                "id"
            ]
            character = store.create_character(account, "Traveler " + chr(65 + number))
            generation = store.begin_session(account)
            store.select_character(account, generation, character["id"])
            origin = dict(map_id=1134, instance_id=0, x=-10, y=-11, z=-1)
            character = store.transition_map(
                account, generation, character["id"], character, origin
            )
            travelers.append((account, generation, character))
        known = known_all()[1]

        def travel(traveler):
            account, generation, character = traveler
            for destination in known:
                route = resolve(
                    character,
                    struct.pack(">qq", 31316, destination),
                    known_ids=known,
                    waive_criteria=True,
                )
                character = store.transition_map(
                    account,
                    generation,
                    character["id"],
                    character,
                    route["destination"],
                )
                persisted = store.character(account, character["id"])
                self.assertEqual(
                    tuple(persisted[k] for k in ("map_id", "x", "y", "z")),
                    tuple(character[k] for k in ("map_id", "x", "y", "z")),
                )
                route = resolve(
                    character,
                    struct.pack(">qq", destination, 31316),
                    known_ids=known,
                    waive_criteria=True,
                )
                character = store.transition_map(
                    account,
                    generation,
                    character["id"],
                    character,
                    route["destination"],
                )
            return account, generation, character

        with ThreadPoolExecutor(max_workers=3) as pool:
            completed = list(pool.map(travel, travelers))
        for account, generation, character in completed:
            self.assertEqual(
                (
                    character["map_id"],
                    character["x"],
                    character["y"],
                    character["z"],
                ),
                (1134, -10, -10, -1),
            )
            other_account = next(a for a, _, _ in completed if a != account)
            with self.assertRaises(ValueError):
                store.transition_map(
                    other_account,
                    generation,
                    character["id"],
                    character,
                    dict(map_id=1134, instance_id=0, x=-10, y=-11, z=-1),
                )
            store.begin_session(account)
            with self.assertRaises(ValueError):
                store.transition_map(
                    account,
                    generation,
                    character["id"],
                    character,
                    dict(map_id=1134, instance_id=0, x=-10, y=-11, z=-1),
                )


class NativeDragoTests(unittest.TestCase):
    def test_actual_user_drago_register_and_own_travel(self):
        character = dict(
            id=7, account_id=9, map_id=1134, instance_id=0, x=8, y=-9, z=-1
        )
        self.assertEqual(
            registration(character, struct.pack(">qH", 31333, 24) + b"\0\0"), (2, 31333)
        )
        route = resolve(
            character,
            struct.pack(">qq", 31333, 31334),
            known_ids={1: (), 2: (31333, 31334)},
        )
        self.assertEqual(
            route["destination"], dict(map_id=1134, instance_id=0, x=7, y=101, z=0)
        )
        with self.assertRaises(ValueError):
            resolve(
                character,
                struct.pack(">qq", 31333, 31316),
                known_ids={1: (31316,), 2: (31333,)},
            )
        with self.assertRaises(ValueError):
            registration(
                dict(character, map_id=527), struct.pack(">qH", 31333, 24) + b"\0\0"
            )

    def test_all_120_drago_arrivals_have_native_map_and_single_height(self):
        from wakfu_server.native_transports import OBJECTS, TRANSPORTS

        dragos = [o for o in OBJECTS.values() if o["type"] == "Drago"]
        self.assertEqual(len(dragos), 120)
        for source in dragos:
            target = next(o for o in dragos if o["map_id"] == source["map_id"])
            character = dict(
                map_id=source["map_id"],
                instance_id=0,
                x=source["arrival_x"],
                y=source["arrival_y"],
                z=source["arrival_heights"][0],
            )
            route = resolve(
                character,
                struct.pack(">qq", source["id"], target["id"]),
                known_ids={2: (target["id"],)},
                waive_criteria=True,
            )
            self.assertEqual(route["destination"]["map_id"], target["map_id"])
        self.assertNotIn(4412, OBJECTS)

    def test_static_activation_is_current_map_native_data(self):
        from wakfu_server.native_transports import static_objects, OBJECTS
        from protocol_codec import Reader

        opcode, body = static_objects(527)
        self.assertEqual(opcode, 13984)
        reader = Reader(body)
        count = reader.number("H")
        self.assertEqual(count, 12)
        for _ in range(count):
            identity = reader.number("q")
            data = reader.take(reader.number("H"))
            self.assertEqual(OBJECTS[identity]["map_id"], 527)
            self.assertEqual(data, bytes.fromhex(OBJECTS[identity]["payload_hex"]))
        reader.finish()

    def test_arrival_direction_is_native_and_validated(self):
        character = dict(
            id=7, account_id=9, map_id=1134, instance_id=0, x=-10, y=-11, z=-1
        )
        for direction in range(8):
            body = bootstrap(character, direction=direction)[1][1]
            self.assertEqual(body[2 + 1 + 8 + 1 + 8 + 4 + 4 + 2 + 8], direction)
        with self.assertRaises(ValueError):
            bootstrap(character, direction=8)
