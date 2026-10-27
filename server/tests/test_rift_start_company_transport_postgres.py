"""Actual durable Rift company authorization and selected-owner transport gates.

This component does not create native combat actors or claim Ready coverage.
The sidekick row is a declared durable fixture, not an activation-item test.
"""
import struct

from postgres_case import PostgresCase
from test_rift_dispatch import helper
from wakfu_server import heroes, rift_entry_adapter, rift_transition_delivery
from wakfu_server.world import World


class RiftStartCompanyTransportPostgresTests(PostgresCase):
    def test_real_company_members_and_selected_transport_readiness(self):
        for label, hero_count, other_main in (("mhh", 2, False), ("mhsm", 1, True)):
            with self.subTest(company=label):
                account = self.store.register("start-" + label, "test-password")["id"]
                main = self.store.create_character(account, label + "Main")
                generation = self.store.begin_session(account, ttl=10000)
                self.store.select_character(account, generation, main["id"])
                owned_heroes = []
                for index in range(hero_count):
                    hero = self.store.create_character(
                        account, label + "Hero" + "AB"[index]
                    )
                    heroes.add(self.store, account, generation, main["id"], hero["id"])
                    owned_heroes.append(hero["id"])
                owners = [(account, generation, main["id"])]
                extra_id = self.store.create_character(account, label + "Other")["id"]
                if other_main:
                    other_account = self.store.register(
                        "start-other-" + label, "test-password"
                    )["id"]
                    other = self.store.create_character(other_account, label + "Guest")
                    other_generation = self.store.begin_session(
                        other_account, ttl=10000
                    )
                    self.store.select_character(
                        other_account, other_generation, other["id"]
                    )
                    owners.append((other_account, other_generation, other["id"]))
                with self.store.connection() as db:
                    catalog = db.execute(
                        "SELECT value FROM settings WHERE name='rift_catalog'"
                    ).fetchone()["value"]["3"]
                    portal = catalog["entrances"][0]
                    altar = next(
                        row
                        for row in catalog["objects"]
                        if row["type"] == "GenericActivableInteractiveElement"
                    )
                    ids = [row[2] for row in owners] + owned_heroes
                    db.execute(
                        "UPDATE characters SET level=33,map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                        (portal["map_id"], portal["x"], portal["y"], portal["z"], ids),
                    )
                    if other_main:
                        party = db.execute(
                            "SELECT party_id FROM player_party_members WHERE character_id=%s",
                            (main["id"],),
                        ).fetchone()["party_id"]
                        db.execute(
                            "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                            (owners[1][2], party),
                        )
                        sidekick = db.execute(
                            "INSERT INTO account_companions(account_id,breed_ref,owner_character_id,name,hp,max_hp) VALUES(%s,2802,%s,'FixtureSidekick',1,1) RETURNING id",
                            (account, main["id"]),
                        ).fetchone()["id"]
                        db.execute(
                            "INSERT INTO account_companion_slots(account_id,slot,owner_character_id,companion_id) VALUES(%s,0,%s,%s)",
                            (account, main["id"], sidekick),
                        )

                def nearby(actor, source):
                    return (
                        actor["map_id"] == source["map_id"]
                        and max(
                            abs(actor["x"] - source["x"]), abs(actor["y"] - source["y"])
                        )
                        <= 3
                        and abs(actor["z"] - source["z"]) <= 2
                    )

                from wakfu_server.combat_geometry import published_geometry

                arrival = []
                for axis in ("x", "y", "z"):
                    value = altar[axis]
                    self.assertNotIsInstance(value, bool)
                    self.assertTrue(float(value).is_integer())
                    arrival.append(int(value))
                self.assertIn(
                    tuple(arrival), published_geometry(catalog["map_id"]).cells
                )
                entered = rift_entry_adapter.enter(
                    self.store,
                    account,
                    generation,
                    main["id"],
                    portal["map_id"],
                    struct.pack(">qHH", portal["object_id"], 11, 0),
                    source_allowed=nearby,
                    resolve_destination=lambda db, selected, rows: dict(
                        map_id=selected["map_id"],
                        x=arrival[0],
                        y=arrival[1],
                        z=arrival[2],
                    ),
                    seed="transport-" + label,
                )
                run = entered["run"]
                self.assertEqual(set(ids), set(run["members"]))
                if other_main:
                    self.assertNotIn(sidekick, run["members"])
                    with self.store.connection() as db:
                        self.assertIsNotNone(
                            db.execute(
                                "SELECT 1 FROM account_companion_slots WHERE companion_id=%s",
                                (sidekick,),
                            ).fetchone()
                        )
                world = World(lambda *args: (), lambda *args: (), lambda *args: None)
                for owner_account, owner_generation, identity in owners:
                    character = self.store.character(owner_account, identity)
                    world.players[identity] = (owner_generation, object(), character)
                self.assertTrue(
                    all(identity not in world.players for identity in owned_heroes)
                )
                events = []
                namespace = dict(
                    STORE=self.store,
                    WORLD=world,
                    account_id=account,
                    generation=generation,
                    character=self.store.character(account, main["id"]),
                    record=lambda **event: events.append(event),
                )
                start = helper("prepare_rift_start", namespace)
                body = struct.pack(">qHH", altar["id"], 0, 0)
                self.assertEqual(start(body)["instance_id"], run["instance_id"])
                self.assertEqual(events, [])

                def rejected(fragment):
                    events.clear()
                    self.assertIsNone(start(body))
                    self.assertEqual(events[-1]["event"], "rift_start_rejected")
                    self.assertIn(fragment, events[-1]["reason"])

                target_account, target_generation, target_id = owners[-1]
                original = world.players.pop(target_id)
                rejected("finish loading")
                world.players[target_id] = original
                world.players[target_id] = (
                    "stale-generation",
                    original[1],
                    original[2],
                )
                rejected("finish loading")
                world.players[target_id] = (
                    original[0],
                    original[1],
                    dict(original[2], instance_id=run["instance_id"] + 1),
                )
                rejected("finish loading")
                world.players[target_id] = original
                pending = dict(
                    map_id=catalog["map_id"],
                    instance_id=run["instance_id"],
                    x=altar["x"],
                    y=altar["y"],
                    z=altar["z"],
                )
                rift_transition_delivery.queue(
                    [
                        dict(
                            account_id=target_account,
                            generation=target_generation,
                            id=target_id,
                            selected_character_id=target_id,
                        )
                    ],
                    pending,
                )
                try:
                    rejected("Wait for every frozen rift member")
                finally:
                    rift_transition_delivery.acknowledge(
                        target_account, target_generation, target_id, pending
                    )
                self.assertIsNotNone(start(body))
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE sessions SET character_id=%s WHERE account_id=%s",
                        (extra_id, account),
                    )
                try:
                    rejected("Sesión o personaje inválidos")
                finally:
                    with self.store.connection() as db:
                        db.execute(
                            "UPDATE sessions SET character_id=%s WHERE account_id=%s",
                            (main["id"], account),
                        )
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE characters SET instance_id=instance_id+1 WHERE id=%s",
                        (owned_heroes[0],),
                    )
                try:
                    rejected("Frozen rift members left")
                finally:
                    with self.store.connection() as db:
                        db.execute(
                            "UPDATE characters SET instance_id=%s WHERE id=%s",
                            (run["instance_id"], owned_heroes[0]),
                        )
                self.assertIsNotNone(start(body))
