"""Atomic cinematic return retains durable membership and native exit ACKs."""

from hashlib import sha256
import struct
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import owned_cinematic_continuations as module
from wakfu_server.achievements import storage

from test_owned_cinematic_continuations import DOCUMENT


class OwnedCinematicReturnPostgresTests(PostgresCase):
    def test_two_real_private_stages_keep_native_world_interest_isolated_across_reconnect(
        self,
    ):
        from wakfu_server import dungeon_exit, dungeon_instances
        from wakfu_server.dungeon_hydration import prepare_transition
        from wakfu_server.position_buffer import Positions
        from wakfu_server.world import World
        from wakfu_server.application.world_publication import WorldPublication

        now = self.store.clock()
        self.store.clock = lambda: now
        live, owners, deliveries = set(), [], []
        positions = Positions(
            self.store, lease_active=lambda a, g, c: (a, g, c) in live
        )

        class Peer:
            pass

        world = World(
            lambda c: struct.pack(">q", c["id"]),
            lambda c: struct.pack(">q", c),
            lambda peer, opcode, body: deliveries.append((peer, opcode, body)),
            native=positions.native,
        )
        publication = WorldPublication(
            SimpleNamespace(STORE=self.store, DUNGEON_ROOM_RUNTIME_AVAILABLE=True)
        )
        pointer = dict(
            path="astrub-ullu-898.json",
            sha256=sha256(
                (module.ROOT / "astrub-ullu-898.json").read_bytes()
            ).hexdigest(),
        )
        controller = dict(cinematic_continuation=pointer)
        with patch.object(module, "policy", return_value=DOCUMENT), patch(
            "wakfu_server.owned_story_exits.authenticate_exit",
            return_value=dict(
                controller=controller,
                completed_steps={"boss-victory", "boss-exit-scene-done"},
            ),
        ):
            for index in range(2):
                account = self.store.register(
                    f"ullu-private-{index}", "local-password"
                )["id"]
                character = self.store.create_character(
                    account, f"Ullu Private {'One' if index == 0 else 'Two'}"
                )
                generation = self.store.begin_session(account)
                self.store.select_character(account, generation, character["id"])
                live.add((account, generation, character["id"]))
                with self.store.connection() as db:
                    party = db.execute(
                        "INSERT INTO player_parties(leader_id,dungeon_solo) VALUES(%s,true) RETURNING id",
                        (character["id"],),
                    ).fetchone()["id"]
                    db.execute(
                        "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                        (character["id"], party),
                    )
                    run = db.execute(
                        "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id) "
                        "VALUES(%s,1,%s,887,887,747,23621,4029,887) RETURNING instance_id",
                        (party, character["id"]),
                    ).fetchone()["instance_id"]
                    db.execute(
                        "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) VALUES(%s,%s,%s,%s,1,'leader')",
                        (run, party, character["id"], generation),
                    )
                    db.execute(
                        "UPDATE characters SET map_id=887,instance_id=%s,x=0,y=-69,z=12 WHERE id=%s",
                        (run, character["id"]),
                    )
                    state = storage.load_locked(db, character["id"])
                    state["completed"] = sorted(set(state["completed"]) | {2170})
                    state["completion_dates"]["2170"] = int(now * 1000)
                    storage.store(db, character["id"], state)
                source = self.store.character(account, character["id"])
                positions.attach(account, generation, source)
                with positions.account_barrier(account), self.store.connection() as db:
                    with self.assertRaisesRegex(ValueError, "another owner"):
                        with db.transaction():
                            dungeon_exit._leave(
                                self.store,
                                account,
                                generation,
                                character["id"],
                                in_fight=lambda _: False,
                                destination_for=lambda *_: dict(
                                    DOCUMENT["stage"],
                                    instance_id=module.stage_instance_id(
                                        character["id"] + 1000
                                    ),
                                ),
                                _db=db,
                            )
                    module.begin(
                        db,
                        self.store,
                        account,
                        generation,
                        character["id"],
                        struct.pack(">qiBi", 23582, 2074, 0, 2),
                        source_allowed=lambda *_: True,
                        in_fight=lambda _: False,
                    )
                staged = positions.rebind_selected(account, generation, character["id"])
                self.assertEqual(
                    staged["instance_id"], module.stage_instance_id(character["id"])
                )
                self.assertFalse(publication.is_dungeon_run(staged["instance_id"]))
                peer = Peer()
                world.join(generation, peer, staged)
                pending = dungeon_instances.pending_transitions(
                    self.store, account, generation, character["id"]
                )
                self.assertEqual(len(pending), 1)
                self.assertEqual(
                    pending[0]["destination_instance_id"], staged["instance_id"]
                )
                plan = prepare_transition(
                    self.store, account, generation, character["id"], pending[0]
                )
                self.assertEqual(plan.character["instance_id"], staged["instance_id"])
                scene_body = next(
                    body for opcode, body in plan.packets if opcode == 13974
                )
                entity_size = struct.unpack_from(">H", scene_body)[0]
                self.assertEqual(
                    struct.unpack(">BqBqiihqBBiihq", scene_body[2 : 2 + entity_size])[
                        7
                    ],
                    898,
                )
                self.assertTrue(
                    dungeon_instances.acknowledge_transition(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        pending[0]["event_id"],
                    )
                )
                with self.store.connection() as db:
                    ready = module.ready(
                        db, self.store, account, generation, character["id"]
                    )
                    self.assertEqual(
                        ready["packets"],
                        [module.packet(DOCUMENT, 14387, character["id"])],
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                            (party,),
                        ).fetchone()["n"],
                        0,
                    )
                owners.append(
                    dict(
                        account=account,
                        character=character["id"],
                        generation=generation,
                        peer=peer,
                        stage=staged,
                        due_ms=ready["due_ms"],
                    )
                )
            self.assertEqual(deliveries, [])
            self.assertNotEqual(
                owners[0]["stage"]["instance_id"], owners[1]["stage"]["instance_id"]
            )
            for owner in owners:
                world.update(
                    owner["generation"],
                    owner["stage"],
                    13530,
                    b"ordinary-native-movement",
                    include_sender=False,
                )
            self.assertEqual(deliveries, [])
            # Reconnect midway without replaying the cinematic or losing its deadline.
            now += 20
            first = owners[0]
            live.discard((first["account"], first["generation"], first["character"]))
            first["generation"] = self.store.begin_session(first["account"])
            self.store.select_character(
                first["account"], first["generation"], first["character"]
            )
            live.add((first["account"], first["generation"], first["character"]))
            first["stage"] = positions.rebind_selected(
                first["account"], first["generation"], first["character"]
            )
            first["peer"] = Peer()
            world.join(first["generation"], first["peer"], first["stage"])
            with self.store.connection() as db:
                resumed = module.ready(
                    db,
                    self.store,
                    first["account"],
                    first["generation"],
                    first["character"],
                )
                self.assertEqual(resumed, dict(packets=[], due_ms=first["due_ms"]))
            self.assertEqual(deliveries, [])
            now += 25
            for owner in owners:
                with positions.account_barrier(
                    owner["account"]
                ), self.store.connection() as db:
                    result = module.finish(
                        db,
                        self.store,
                        owner["account"],
                        owner["generation"],
                        owner["character"],
                    )
                saved = positions.rebind_selected(
                    owner["account"], owner["generation"], owner["character"]
                )
                self.assertEqual((saved["map_id"], saved["instance_id"]), (527, 0))
                world.join(owner["generation"], owner["peer"], saved)
                events = dungeon_instances.pending_transitions(
                    self.store,
                    owner["account"],
                    owner["generation"],
                    owner["character"],
                )
                self.assertEqual(len(events), 1)
                plan = prepare_transition(
                    self.store,
                    owner["account"],
                    owner["generation"],
                    owner["character"],
                    events[0],
                )
                self.assertEqual(
                    (plan.character["map_id"], plan.character["instance_id"]), (527, 0)
                )
                self.assertTrue(
                    dungeon_instances.acknowledge_transition(
                        self.store,
                        owner["account"],
                        owner["generation"],
                        owner["character"],
                        events[0]["event_id"],
                    )
                )
                self.assertFalse(
                    dungeon_instances.acknowledge_transition(
                        self.store,
                        owner["account"],
                        owner["generation"],
                        owner["character"],
                        events[0]["event_id"],
                    )
                )
            # Ordinary exterior interest is restored, without any custom visibility filter.
            self.assertEqual(
                {
                    (id(peer), struct.unpack(">q", body)[0])
                    for peer, opcode, body in deliveries
                    if opcode == 12608
                },
                {
                    (id(owners[0]["peer"]), owners[1]["character"]),
                    (id(owners[1]["peer"]), owners[0]["character"]),
                },
            )
            # A genuine later temple visit keeps its completion-only exit,
            # without forcing another boss/cinematic or minting new progress.
            first = owners[0]
            with self.store.connection() as db:
                party = db.execute(
                    "INSERT INTO player_parties(leader_id,dungeon_solo) VALUES(%s,true) RETURNING id",
                    (first["character"],),
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                    (first["character"], party),
                )
                revisit = db.execute(
                    "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id) VALUES(%s,1,%s,887,887,747,23621,4029,887) RETURNING instance_id",
                    (party, first["character"]),
                ).fetchone()["instance_id"]
                db.execute(
                    "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) VALUES(%s,%s,%s,%s,1,'leader')",
                    (revisit, party, first["character"], first["generation"]),
                )
                db.execute(
                    "UPDATE characters SET map_id=887,instance_id=%s,x=0,y=-69,z=12 WHERE id=%s",
                    (revisit, first["character"]),
                )
            source = positions.rebind_selected(
                first["account"], first["generation"], first["character"]
            )
            world.join(first["generation"], first["peer"], source)
            with patch(
                "wakfu_server.owned_story_exits.authenticate_exit",
                return_value=dict(controller=controller, completed_steps=set()),
            ):
                with positions.account_barrier(
                    first["account"]
                ), self.store.connection() as db:
                    repeated = module.begin(
                        db,
                        self.store,
                        first["account"],
                        first["generation"],
                        first["character"],
                        struct.pack(">qiBi", 23582, 2074, 0, 2),
                        source_allowed=lambda *_: True,
                        in_fight=lambda _: False,
                    )
                    self.assertEqual(
                        (repeated["map_id"], repeated["instance_id"]), (527, 0)
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                            (first["character"], module._key(DOCUMENT, "started")),
                        ).fetchone()["n"],
                        1,
                    )
            saved = positions.rebind_selected(
                first["account"], first["generation"], first["character"]
            )
            world.join(first["generation"], first["peer"], saved)
            repeated_event = dungeon_instances.pending_transitions(
                self.store, first["account"], first["generation"], first["character"]
            )[0]
            self.assertEqual(repeated_event["instance_id"], revisit)
            self.assertTrue(
                dungeon_instances.acknowledge_transition(
                    self.store,
                    first["account"],
                    first["generation"],
                    first["character"],
                    repeated_event["event_id"],
                )
            )
        for owner in owners:
            world.leave(owner["character"], owner["generation"])
        another = self.store.create_character(owners[0]["account"], "After Ullu Return")
        self.store.select_character(
            owners[0]["account"], owners[0]["generation"], another["id"]
        )
        live.discard(
            (owners[0]["account"], owners[0]["generation"], owners[0]["character"])
        )
        live.add((owners[0]["account"], owners[0]["generation"], another["id"]))
        selected = positions.attach(
            owners[0]["account"], owners[0]["generation"], another
        )
        self.assertEqual(selected["id"], another["id"])

    def test_failed_return_rolls_back_and_success_acknowledges_closed_member_once(self):
        account = self.store.register("ullu-return", "local-password")["id"]
        character = self.store.create_character(account, "Ullu Return")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        pointer = dict(
            path="astrub-ullu-898.json",
            sha256=sha256(
                (module.ROOT / "astrub-ullu-898.json").read_bytes()
            ).hexdigest(),
        )
        with self.store.connection() as db:
            party = db.execute(
                "INSERT INTO player_parties(leader_id,dungeon_solo) VALUES(%s,true) RETURNING id",
                (character["id"],),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (character["id"], party),
            )
            run = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,"
                "definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id,status,ended_at) "
                "VALUES(%s,1,%s,887,887,747,23621,4029,887,'closed',now()) RETURNING instance_id",
                (party, character["id"]),
            ).fetchone()["instance_id"]
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,"
                "party_revision,role,status,ended_at) VALUES(%s,%s,%s,'original-lease',1,'leader','returned',now())",
                (run, party, character["id"]),
            )
            from wakfu_server import player_parties

            cleanup = player_parties.cleanup_dungeon_solo(db, party)
            self.assertEqual(cleanup["removed"], [character["id"]])
            db.execute(
                "UPDATE characters SET map_id=898,instance_id=%s,x=0,y=0,z=0 WHERE id=%s",
                (module.stage_instance_id(character["id"]), character["id"]),
            )
            storage.record_event(
                db,
                character["id"],
                module._key(DOCUMENT, "arrival"),
                dict(
                    schema=module.SCHEMA,
                    owner=character["id"],
                    account_id=account,
                    source_instance_id=run,
                    policy_sha256=module._digest(DOCUMENT),
                    profile_id=DOCUMENT["id"],
                    profile_pointer=pointer,
                    stage_map_id=898,
                    stage_instance_id=module.stage_instance_id(character["id"]),
                ),
            )
            storage.record_event(
                db,
                character["id"],
                module._key(DOCUMENT, "started"),
                dict(
                    owner=character["id"],
                    generation="original-lease",
                    due_ms=0,
                ),
            )
        with patch.object(module, "policy", return_value=DOCUMENT):
            with self.store.connection() as db:
                with self.assertRaisesRegex(ValueError, "receipt failure"):
                    with db.transaction():
                        with patch.object(
                            module.storage,
                            "record_event",
                            side_effect=ValueError("receipt failure"),
                        ):
                            module.finish(
                                db, self.store, account, generation, character["id"]
                            )
                row = db.execute(
                    "SELECT map_id,instance_id FROM characters WHERE id=%s",
                    (character["id"],),
                ).fetchone()
                self.assertEqual(
                    row,
                    dict(
                        map_id=898,
                        instance_id=module.stage_instance_id(character["id"]),
                    ),
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM dungeon_transition_outbox WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT session_generation FROM dungeon_instance_members WHERE instance_id=%s",
                        (run,),
                    ).fetchone()["session_generation"],
                    "original-lease",
                )
                result = module.finish(
                    db, self.store, account, generation, character["id"]
                )
                self.assertEqual((result["map_id"], result["instance_id"]), (527, 0))
                self.assertEqual(result["before_transition_packets"], [])
                self.assertIsNone(
                    module.finish(db, self.store, account, generation, character["id"])
                )
                event = db.execute(
                    "SELECT * FROM dungeon_transition_outbox WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()
                self.assertEqual(
                    (
                        event["source_map_id"],
                        event["source_instance_id"],
                        event["destination_map_id"],
                        event["destination_instance_id"],
                    ),
                    (898, module.stage_instance_id(character["id"]), 527, 0),
                )
                member = db.execute(
                    "SELECT status,session_generation FROM dungeon_instance_members WHERE instance_id=%s",
                    (run,),
                ).fetchone()
                self.assertEqual(
                    member, dict(status="returned", session_generation=generation)
                )
                self.assertIsNone(
                    db.execute(
                        "SELECT leader_id FROM player_parties WHERE id=%s", (party,)
                    ).fetchone()["leader_id"]
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                        (party,),
                    ).fetchone()["n"],
                    0,
                )
        from wakfu_server import dungeon_instances

        self.assertTrue(
            dungeon_instances.acknowledge_transition(
                self.store, account, generation, character["id"], event["event_id"]
            )
        )
        self.assertFalse(
            dungeon_instances.acknowledge_transition(
                self.store, account, generation, character["id"], event["event_id"]
            )
        )
