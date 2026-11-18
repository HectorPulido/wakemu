"""Cat dungeon core lifecycle is independent of quest cutscene eligibility.

Use the reviewed three-room configuration and real local PostgreSQL, group
hydration, position buffers and transition delivery. Fight outcomes are domain
fixtures; this does not claim graphical rendering or live combat acceptance.
"""

from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import (
    combat_terrain,
    dungeon_auto_exit,
    dungeon_auto_transition,
    dungeon_entry_access,
    dungeon_instances,
    dungeon_position_barrier,
    dungeon_progression,
    dungeon_runtime,
    dungeon_runtime_config,
    dungeon_transition_delivery,
    dungeon_transport,
    generic_transports,
    heroes,
)
from wakfu_server.achievements import (
    astrub_cat_story,
    astrub_cat_story_authority,
    storage,
)
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.position_buffer import Positions


class MiaubuelitaLifecyclePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        path = Path(__file__).parent / "fixtures/dungeons/cat-runtime-config-v4.json"
        self.configuration = json.loads(path.read_text())
        route = self.configuration["route"]
        self.route = dungeon_instances.EntryRoute(
            **{
                field.name: route[field.name]
                for field in fields(dungeon_instances.EntryRoute)
                if field.name in route
            }
        )
        self.addCleanup(patch.stopall)
        patch.dict(dungeon_instances._ROUTES, {self.route.key: self.route}).start()
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, self.configuration)
        self.live = set()
        self.positions = Positions(
            self.store, lease_active=lambda a, g, c: (a, g, c) in self.live
        )
        self.groups = PersistentGroups(self.store)
        self.geometry = combat_terrain.map_geometry(312)

    def player(self, mode):
        token = uuid.uuid4().hex[:10]
        account = self.store.register("catlife" + token, "isolated-test-password")["id"]
        name = "Cat Life " + "".join(chr(97 + int(c, 16)) for c in token)
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account, ttl=10000)
        character = self.store.select_character(account, generation, character["id"])
        source = generic_transports.source(527, 18736)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (source["x"], source["y"], source["z"], character["id"]),
            )
            state = storage.load_locked(db, character["id"])
            state.update(
                running=[5568] if mode == "active" else [],
                completed=[5568] if mode == "completed" else [],
                objectives=([11508, 11509, 11510] if mode != "unavailable" else [])
                + (
                    [11511, 11512, 11513, 11514, 11515, 11544]
                    if mode == "completed"
                    else []
                ),
            )
            storage.store(db, character["id"], state)
            db.execute(
                "INSERT INTO character_achievement_authority(character_id,snapshot,revision,provenance) VALUES(%s,%s,1,'isolated-cat-lifecycle') ON CONFLICT(character_id) DO UPDATE SET snapshot=EXCLUDED.snapshot,revision=EXCLUDED.revision,provenance=EXCLUDED.provenance",
                (
                    character["id"],
                    Jsonb(
                        {
                            key: state[key]
                            for key in ("running", "completed", "objectives")
                        }
                    ),
                ),
            )
            character = self.store.character(account, character["id"], db)
        self.live.add((account, generation, character["id"]))
        self.positions.attach(account, generation, character)
        return account, generation, character, deepcopy(state)

    def deliver(self, account, generation, character):
        worker = {
            key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")
        }
        seen = []

        def bootstrap(event):
            current = self.store.character(account, character["id"])
            self.positions.attach(account, generation, current)
            worker.update({key: current[key] for key in worker})
            seen.append(event["event_id"])
            return True

        result = dungeon_transition_delivery.deliver_pending_transitions(
            self.store,
            account,
            generation,
            character["id"],
            worker_generation=generation,
            current_location=lambda: dict(worker),
            in_fight=lambda: False,
            bootstrap=bootstrap,
        )
        self.assertEqual(result["state"], "delivered")
        self.assertEqual(len(seen), 1)
        self.assertFalse(result["pending_event_ids"])
        self.assertFalse(
            dungeon_instances.pending_transitions(
                self.store, account, generation, character["id"]
            )
        )
        return self.store.character(account, character["id"])

    def victory(self, account, character, session):
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, character["id"], account),
            )
            dungeon_progression.bind_encounter(
                db,
                session["instance_id"],
                session["party_id"],
                character["id"],
                fight_id,
                player_team=0,
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            result = dungeon_progression.settle_encounter(
                db, SimpleNamespace(id=fight_id, phase="finished", winner=0)
            )
            if not result["completed"]:
                dungeon_runtime.ensure_current_room(
                    db, self.groups, session["instance_id"], self.geometry
                )
        return fight_id, result

    def test_active_completed_and_unavailable_quest_enter_progress_and_exit_cleanly(
        self,
    ):
        for mode in ("active", "completed", "unavailable"):
            with self.subTest(mode=mode):
                account, generation, character, state_before = self.player(mode)
                session = dungeon_transport.enter(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    527,
                    struct.pack(">qiBi", 18736, 713, 0, 2),
                    criterion_allowed=lambda actor, criterion: dungeon_entry_access.evaluate(
                        self.store, criterion, character=actor, destination_map_id=312
                    ),
                    source_allowed=lambda actor, source: actor["map_id"] == 527
                    and source["id"] == 18736
                    and (actor["x"], actor["y"], actor["z"])
                    == (source["x"], source["y"], source["z"]),
                    initialize_instance=lambda db, run: dungeon_runtime.initialize_instance(
                        db,
                        run,
                        groups=self.groups,
                        geometry=self.geometry,
                        store=self.store,
                    ),
                    resolve_destination=dungeon_runtime.entry_destination,
                    positions=self.positions,
                )
                self.assertFalse(session["reused"])
                character = self.deliver(account, generation, character)
                self.assertEqual(
                    (character["map_id"], character["instance_id"]),
                    (312, session["instance_id"]),
                )
                for room in (1, 2, 3):
                    with self.store.connection() as db:
                        scope = astrub_cat_story_authority.context(
                            db, character, allow_finished=True
                        )
                        self.assertEqual(scope is not None, mode == "active")
                        if scope is not None:
                            self.assertEqual(scope["room"], room)
                        spawned = db.execute(
                            "SELECT group_id FROM dungeon_room_spawn_receipts WHERE instance_id=%s AND room_order=%s",
                            (session["instance_id"], room),
                        ).fetchone()
                        self.assertIsNotNone(spawned)
                    if mode != "active":
                        self.assertIsNone(
                            astrub_cat_story.poll(
                                self.store,
                                account,
                                generation,
                                character,
                                bootstrap=True,
                            )
                        )
                    fight_id, result = self.victory(account, character, session)
                    transition = (
                        dungeon_auto_exit.complete
                        if room == 3
                        else dungeon_auto_transition.advance
                    )
                    moved = dungeon_position_barrier.run_auto_transition(
                        self.store,
                        self.positions,
                        session["instance_id"],
                        fight_id,
                        transition=transition,
                        topology=self.configuration["topology"],
                        in_fight=lambda identity: False,
                    )
                    self.assertFalse(moved.get("deferred", False))
                    self.assertFalse(moved["replay"])
                    character = self.deliver(account, generation, character)
                self.assertEqual(
                    (character["map_id"], character["instance_id"]), (527, 0)
                )
                with self.store.connection() as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                            (session["instance_id"], character["id"]),
                        ).fetchone()["status"],
                        "returned",
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                            (session["instance_id"],),
                        ).fetchone()["status"],
                        "closed",
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT status FROM dungeon_room_runs WHERE instance_id=%s",
                            (session["instance_id"],),
                        ).fetchone()["status"],
                        "completed",
                    )
                    roster = heroes.load_roster(
                        db, self.store, account, character["id"]
                    )
                    self.assertEqual(roster["leader"]["instance_id"], 0)
                    self.assertEqual(roster["heroes"], ())
                    state_after = storage.load_locked(db, character["id"])
                    for key in ("running", "completed", "objectives"):
                        self.assertEqual(state_after[key], state_before[key])
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s AND event_key LIKE 'astrub-cat-story:%%'",
                            (character["id"],),
                        ).fetchone()["n"],
                        0,
                    )
                entry = self.positions.entries[(account, generation, character["id"])]
                self.assertFalse(entry["dirty"])
                self.assertEqual(entry["persisted"]["instance_id"], 0)
                created = self.store.create_character(
                    account,
                    "Cat After "
                    + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:8]),
                )
                selected = self.store.select_character(
                    account, generation, created["id"]
                )
                self.assertEqual(selected["instance_id"], 0)
