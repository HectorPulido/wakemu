"""Six-member local DEV override uses general native party/entry authority."""
import struct
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import rift_entry_adapter, rift_runtime


class RiftSixMemberPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.members = []
        for i in range(7):
            account = self.store.register("rift-six-" + str(i), "local-password")["id"]
            character = self.store.create_character(account, "Riftsix" + chr(97 + i))[
                "id"
            ]
            generation = self.store.begin_session(account)
            self.store.select_character(account, generation, character)
            self.members.append(
                dict(account=account, character=character, generation=generation)
            )
        with self.store.connection() as db:
            self.catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]["3"]
            self.source = self.catalog["entrances"][0]
            db.execute(
                "UPDATE characters SET level=%s,map_id=%s,instance_id=0",
                (self.catalog["level"], self.source["map_id"]),
            )
        self.owner = self.members[0]
        self.body = struct.pack(">qHH", self.source["object_id"], 11, 0)

    def party(self, count):
        with self.store.connection() as db:
            party = db.execute(
                "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING id",
                (self.owner["character"],),
            ).fetchone()["id"]
            for member in self.members[:count]:
                db.execute(
                    "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                    (member["character"], party),
                )

    def enter(self, resolver=None):
        return rift_entry_adapter.enter(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            self.source["map_id"],
            self.body,
            source_allowed=lambda row, obj: True,
            seed="six-member",
            resolve_destination=resolver
            or (
                lambda db, catalog, members: dict(
                    map_id=catalog["map_id"], x=1, y=2, z=0
                )
            ),
        )

    def test_six_enter_move_and_freeze_then_start_exact_complete_roster(self):
        self.party(6)
        from wakfu_server.combat_terrain import map_geometry, local_arena
        from wakfu_server.rift_dispatch_lifecycle import (
            resolve_destination,
            initial_members,
        )

        geometry = map_geometry(self.catalog["map_id"])
        result = self.enter(
            lambda db, catalog, members: resolve_destination(
                db, catalog, members, geometry
            )
        )
        run = result["run"]
        ids = [m["character"] for m in self.members[:6]]
        self.assertEqual(set(run["members"]), set(ids))
        self.assertEqual(run["policy"]["max_members"], 6)
        self.assertEqual(len(result["members"]), 6)
        with self.store.connection() as db:
            moved = db.execute(
                "SELECT map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s)",
                (ids,),
            ).fetchall()
            self.assertTrue(all(r == result["destination"] for r in moved))
            anchor = tuple(result["destination"][key] for key in ("x", "y", "z"))
            enemies = initial_members(db, run, geometry, anchor)
            arena = local_arena(
                self.catalog["map_id"],
                self.owner["character"],
                anchor,
                [(m["x"], m["y"], m["z"]) for m in enemies],
                variation_seed="six",
            )
            self.assertGreaterEqual(len(arena["placement_cells"][0]), 6)
            current = db.execute(
                "SELECT value FROM settings WHERE name='rift_policy'"
            ).fetchone()["value"]
            db.execute(
                "UPDATE settings SET value=%s WHERE name='rift_policy'",
                (Jsonb({**current, "max_members": 4}),),
            )
            self.assertEqual(
                rift_runtime._run(db, run["instance_id"])["policy"]["max_members"], 6
            )
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('placement') RETURNING id"
            ).fetchone()["id"]
            for member in self.members[:6]:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                    (
                        fight,
                        member["character"],
                        member["account"],
                        member["generation"],
                    ),
                )
            started = rift_runtime.start(
                db, run["instance_id"], self.owner["character"], fight
            )
            self.assertEqual(started["status"], "running")

    def test_seventh_rejected_without_moving_or_allocating_run(self):
        self.party(7)
        with self.assertRaisesRegex(ValueError, "membership"):
            self.enter()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM rift_instances").fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM characters WHERE map_id=%s AND instance_id=0",
                    (self.source["map_id"],),
                ).fetchone()["n"],
                7,
            )

    def test_six_member_transition_rolls_back_as_one_transaction(self):
        self.party(6)

        def fail(db, catalog, members):
            self.assertEqual(len(members), 6)
            raise ValueError("arrival unavailable")

        with self.assertRaisesRegex(ValueError, "arrival unavailable"):
            self.enter(fail)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM rift_instances").fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM characters WHERE instance_id=0"
                ).fetchone()["n"],
                7,
            )

    def test_all_seven_classic_native_maps_support_six_member_formation(self):
        from wakfu_server.combat_terrain import map_geometry, local_arena
        from wakfu_server.rift_dispatch_lifecycle import (
            resolve_destination,
            initial_members,
        )

        with self.store.connection() as db:
            catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]
            policy = db.execute(
                "SELECT value FROM settings WHERE name='rift_policy'"
            ).fetchone()["value"]
            classics = [
                row for row in catalog.values() if row["type"] == "INFINITE_WAVE"
            ]
            self.assertEqual(len(classics), 7)
            for native in classics:
                with self.subTest(wave_id=native["wave_id"], map_id=native["map_id"]):
                    geometry = map_geometry(native["map_id"])
                    destination = resolve_destination(
                        db, native, self.members[:6], geometry
                    )
                    anchor = tuple(destination[key] for key in ("x", "y", "z"))
                    run = dict(
                        status="entered",
                        catalog=native,
                        policy=policy,
                        seed="six-all-native",
                        wave=1,
                        instance_id=288230376151711745,
                        members=[m["character"] for m in self.members[:6]],
                    )
                    enemies = initial_members(db, run, geometry, anchor)
                    self.assertEqual(len(enemies), policy["classic_wave_size"])
                    arena = local_arena(
                        native["map_id"],
                        self.owner["character"],
                        anchor,
                        [(m["x"], m["y"], m["z"]) for m in enemies],
                        variation_seed="six-all-native",
                    )
                    self.assertGreaterEqual(len(arena["placement_cells"][0]), 6)
