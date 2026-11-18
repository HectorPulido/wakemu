"""One owned-content lifecycle matrix, independent of optional journal state."""

import json
from pathlib import Path
import struct
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
import test_owned_story_reentry_postgres as paid_fixture
from wakfu_server import (
    companions,
    dungeon_instances,
    dungeon_transport,
    generic_transports,
)
from wakfu_server.achievements import storage
from wakfu_server.maps import dungeon_exit
from wakfu_server.position_buffer import Positions


class OwnedContentVisitPostgresTests(PostgresCase):
    _install = paid_fixture.OwnedStoryPaidReentryPostgresTests._install
    _entry_route = staticmethod(
        paid_fixture.OwnedStoryPaidReentryPostgresTests._entry_route
    )

    def test_optional_journal_entry_exit_reentry_and_selection_share_one_lifecycle(
        self,
    ):
        self.store.clock = lambda: 2_000_000_000.0
        config = json.loads(
            (
                Path(__file__).parents[1]
                / "wakfu_server/maps/quest_encounter_profiles/astrub-warehouse.configuration.json"
            ).read_text()
        )
        route = self._entry_route(config)
        source = generic_transports.source(route.entry_map_id, route.entry_object_id)
        body = struct.pack(">qiBi", route.entry_object_id, route.destination_id, 0, 2)
        with self.store.connection() as db:
            installed = db.execute(
                "SELECT configuration FROM dungeon_runtime_configurations "
                "WHERE route_key=%s AND policy_version=%s",
                (route.key, config["version"]),
            ).fetchone()
            if installed is None:
                self._install(db, config)
            else:
                self.assertEqual(installed["configuration"], config)
                active = db.execute(
                    "SELECT policy_version FROM dungeon_runtime_active_configurations "
                    "WHERE route_key=%s",
                    (route.key,),
                ).fetchone()
                self.assertEqual(active["policy_version"], config["version"])
            # This archetype must remain visitable even when ordinary routes
            # require their native achievement expression.
            db.execute(
                "UPDATE settings SET value=%s WHERE name='dungeon_entry_access_policy'",
                (
                    Jsonb(
                        dict(
                            version=1,
                            bypass_mission_prerequisites=False,
                            bypass_state_prerequisites=False,
                        )
                    ),
                ),
            )
        with patch.object(dungeon_instances, "_ROUTES", {route.key: route}):
            for phase in ("unassigned", "running", "completed"):
                with self.subTest(phase=phase):
                    account = self.store.register(
                        f"content-{phase}", "isolated-password"
                    )["id"]
                    actor = self.store.create_character(account, f"Visit {phase}")
                    generation = self.store.begin_session(account, ttl=10000)
                    self.store.select_character(account, generation, actor["id"])
                    actor_id = actor["id"]
                    with self.store.connection() as db:
                        db.execute(
                            "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                            (
                                route.entry_map_id,
                                source["x"],
                                source["y"],
                                source["z"],
                                actor_id,
                            ),
                        )
                        before = storage.load_locked(db, actor_id)
                        before["running"] = [2016] if phase == "running" else []
                        before["completed"] = [2016] if phase == "completed" else []
                        # Admission was previously earned for the assigned
                        # lifecycle fixture; actual callback earning is covered
                        # by the initialize/settle matrix, without a combat here.
                        before["objectives"] = [4079] if phase != "unassigned" else []
                        storage.store(db, actor_id, before)
                    key = (account, generation, actor_id)
                    positions = Positions(
                        self.store,
                        lease_active=lambda *actual, expected=key: actual == expected,
                    )
                    positions.attach(
                        account, generation, self.store.character(account, actor_id)
                    )
                    for visit in range(2):
                        entered = dungeon_transport.enter(
                            self.store,
                            account,
                            generation,
                            actor_id,
                            route.entry_map_id,
                            body,
                            criterion_allowed=lambda *_: False,
                            source_allowed=lambda actual, native: actual["map_id"]
                            == route.entry_map_id
                            and actual["instance_id"] == 0
                            and native["id"] == source["id"],
                            positions=positions,
                        )
                        instance = entered["instance_id"]
                        with self.store.connection() as db:
                            member = db.execute(
                                "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                                (instance, actor_id),
                            ).fetchone()
                            self.assertEqual(member["status"], "active")
                            self.assertEqual(
                                companions.controlled_count(db, [actor_id]), 0
                            )
                            self.assertEqual(storage.load_locked(db, actor_id), before)
                        current = positions.entry_snapshot(key)["current"]
                        self.assertEqual(
                            (current["map_id"], current["instance_id"]), (891, instance)
                        )
                        pending = dungeon_instances.pending_transitions(
                            self.store, account, generation, actor_id
                        )
                        self.assertEqual(len(pending), 1)
                        self.assertEqual(pending[0]["transition_kind"], "enter")
                        dungeon_instances.acknowledge_transition(
                            self.store,
                            account,
                            generation,
                            actor_id,
                            pending[0]["event_id"],
                        )
                        dungeon_exit._leave(
                            self.store,
                            account,
                            generation,
                            actor_id,
                            in_fight=lambda _: False,
                            destination_for=lambda *_: dict(
                                map_id=route.entry_map_id,
                                x=source["x"],
                                y=source["y"],
                                z=source["z"],
                            ),
                            positions=positions,
                        )
                        pending = dungeon_instances.pending_transitions(
                            self.store, account, generation, actor_id
                        )
                        self.assertEqual(len(pending), 1)
                        self.assertEqual(pending[0]["transition_kind"], "exit")
                        current = positions.entry_snapshot(key)["current"]
                        self.assertEqual(
                            (current["map_id"], current["instance_id"]), (527, 0)
                        )
                        dungeon_instances.acknowledge_transition(
                            self.store,
                            account,
                            generation,
                            actor_id,
                            pending[0]["event_id"],
                        )
                        with self.store.connection() as db:
                            self.assertEqual(
                                db.execute(
                                    "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                                    (instance, actor_id),
                                ).fetchone()["status"],
                                "returned",
                            )
                            self.assertIsNone(
                                db.execute(
                                    "SELECT 1 FROM player_party_members WHERE character_id=%s",
                                    (actor_id,),
                                ).fetchone()
                            )
                    alternate = self.store.create_character(account, f"Other {phase}")
                    self.store.select_character(account, generation, alternate["id"])
                    selected = self.store.select_character(
                        account, generation, actor_id
                    )
                    self.assertEqual(
                        (selected["map_id"], selected["instance_id"]), (527, 0)
                    )
