"""Isolated normal entry/return/revisit proof for the offline 885 context."""

import json
from pathlib import Path
import struct
from unittest.mock import Mock

from postgres_case import PostgresCase
from wakfu_server import dungeon_instances
from wakfu_server.achievements import storage
from wakfu_server.maps import (
    dungeon_runtime,
    dungeon_runtime_config,
    dungeon_exit,
    owned_story_exits,
    owned_story_generic_entry,
)
from wakfu_server.position_buffer import Positions


CONFIG_PATH = (
    Path(__file__).resolve().parents[2]
    / "server/wakfu_server/maps/owned_story_profiles/astrub-pizzlarva-885.configuration.json"
)


class NativeOrderTrialContextPostgresTests(PostgresCase):
    def test_normal_entry_free_exit_and_questless_revisit_preserve_durable_scope(self):
        configuration = json.loads(CONFIG_PATH.read_text())
        route_key = configuration["route"]["key"]
        account = self.store.register("native-order-context", "isolated-test-password")[
            "id"
        ]
        character = self.store.create_character(account, "Order Context Owner")
        next_character = self.store.create_character(account, "Order Context Next")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])

        public_position = (546, 0, -4, -8, 3)
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, configuration)
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (public_position[0], *public_position[2:], character["id"]),
            )

        previous_routes = dungeon_instances._ROUTES
        try:
            dungeon_instances.load_runtime_routes(self.store)
            route = dungeon_instances.route(route_key)
            self.assertEqual(
                (
                    route.entry_map_id,
                    route.entry_object_id,
                    route.destination_id,
                    route.start_map_id,
                ),
                (546, 23626, 1457, 885),
            )

            live = {(account, generation, character["id"])}
            positions = Positions(
                self.store,
                lease_active=lambda owner, lease, identity: (owner, lease, identity)
                in live,
            )
            positions.attach(
                account,
                generation,
                self.store.character(account, character["id"]),
            )
            groups = Mock()

            def initialize(db, admitted):
                result = dungeon_runtime.initialize_instance(
                    db, admitted, groups=groups, geometry={}, store=self.store
                )
                self.assertIsNone(result)

            def enter():
                with positions.account_barrier(account):
                    positions.flush(account_id=account)
                    result = owned_story_generic_entry.enter(
                        self.store,
                        account,
                        generation,
                        self.store.character(account, character["id"]),
                        struct.pack(">qHH", 23626, 0, 0),
                        loaded=True,
                        blocked=False,
                        allowed_position_accounts=frozenset({account}),
                        initialize_instance=initialize,
                    )
                    positions.rebind_selected(account, generation, character["id"])
                    return result

            with self.store.connection() as db:
                before = storage.load_locked(db, character["id"])
                events_before = db.execute(
                    "SELECT event_key,payload FROM character_achievement_events "
                    "WHERE character_id=%s ORDER BY event_key",
                    (character["id"],),
                ).fetchall()
            entered = enter()
            instance_id = entered["instance_id"]
            self.assertEqual(entered["destination"]["instance_id"], instance_id)
            self.assertEqual(entered["destination"]["map_id"], 885)
            groups.assert_not_called()
            inside = self.store.character(account, character["id"])
            self.assertEqual(
                tuple(inside[key] for key in ("map_id", "instance_id", "x", "y", "z")),
                (885, instance_id, 0, 0, 0),
            )
            with self.store.connection() as db:
                pinned_run, pinned = dungeon_runtime.configuration_for_instance(
                    db, instance_id
                )
                self.assertEqual(pinned_run["context_route_key"], route_key)
                self.assertEqual(pinned["topology"]["rooms"], [])
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM dungeon_room_runs WHERE instance_id=%s",
                        (instance_id,),
                    ).fetchone()["n"],
                    0,
                )
                member = db.execute(
                    "SELECT status,session_generation FROM dungeon_instance_members "
                    "WHERE instance_id=%s AND character_id=%s",
                    (instance_id, character["id"]),
                ).fetchone()
                self.assertEqual(
                    (member["status"], member["session_generation"]),
                    ("active", generation),
                )
                company = db.execute(
                    "SELECT p.id,p.leader_id,p.dungeon_solo,m.character_id "
                    "FROM dungeon_instances d "
                    "JOIN player_parties p ON p.id=d.party_id "
                    "JOIN player_party_members m ON m.party_id=p.id "
                    "WHERE d.instance_id=%s ORDER BY m.character_id",
                    (instance_id,),
                ).fetchall()
                self.assertEqual(len(company), 1)
                self.assertEqual(
                    (
                        company[0]["leader_id"],
                        company[0]["dungeon_solo"],
                        company[0]["character_id"],
                    ),
                    (character["id"], True, character["id"]),
                )

            def source_allowed(current, source):
                return (
                    source["map_id"] == 885
                    and source["id"] == 23627
                    and (source["x"], source["y"], source["z"]) == (0, 1, 0)
                    and tuple(current[key] for key in ("x", "y", "z")) == (0, 0, 0)
                    and current["map_id"] == 885
                    and current["instance_id"] > 0
                )

            exit_body = struct.pack(">qiBi", 23627, 2016, 0, 2)
            with positions.account_barrier(account):
                positions.flush(account_id=account)
                with self.store.connection() as db:
                    current = self.store.character(account, character["id"], db)
                    authenticated = owned_story_exits.authenticate_exit(
                        db,
                        self.store,
                        current,
                        exit_body,
                        source_allowed=source_allowed,
                    )
                    destination = {
                        key: authenticated["destination"][key]
                        for key in ("map_id", "x", "y", "z")
                    }
                    dungeon_exit._leave(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        in_fight=lambda _identity: False,
                        destination_for=lambda *_: destination,
                        _db=db,
                    )
                positions.rebind_selected(account, generation, character["id"])
            first_exit = self.store.character(account, character["id"])
            self.assertEqual(
                tuple(
                    first_exit[key] for key in ("map_id", "instance_id", "x", "y", "z")
                ),
                (546, 0, -4, -8, 3),
            )
            snapshot = positions.entry_snapshot((account, generation, character["id"]))
            self.assertEqual(
                tuple(
                    snapshot["current"][key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                ),
                (546, 0, -4, -8, 3),
            )
            with self.store.connection() as db:
                member = db.execute(
                    "SELECT status FROM dungeon_instance_members "
                    "WHERE instance_id=%s AND character_id=%s",
                    (instance_id, character["id"]),
                ).fetchone()
                self.assertEqual(member["status"], "returned")
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM player_party_members WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone()
                )
                transitions = db.execute(
                    "SELECT transition_kind,status,destination_map_id,destination_instance_id "
                    "FROM dungeon_transition_outbox WHERE instance_id=%s AND character_id=%s "
                    "ORDER BY transition_revision",
                    (instance_id, character["id"]),
                ).fetchall()
                self.assertEqual(
                    [row["transition_kind"] for row in transitions], ["enter", "exit"]
                )
                self.assertEqual(transitions[-1]["status"], "pending")
                self.assertEqual(
                    (
                        transitions[-1]["destination_map_id"],
                        transitions[-1]["destination_instance_id"],
                    ),
                    (546, 0),
                )

            # A second physical visit with no mission assignment does not
            # manufacture quest progress, rewards, or cinematic receipts.
            second_entry = enter()
            self.assertNotEqual(second_entry["instance_id"], instance_id)
            with self.store.connection() as db:
                after = storage.load_locked(db, character["id"])
                self.assertEqual(after, before)
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT event_key,payload FROM character_achievement_events "
                        "WHERE character_id=%s ORDER BY event_key",
                        (character["id"],),
                    ).fetchall(),
                    events_before,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                        (second_entry["instance_id"], character["id"]),
                    ).fetchone()["status"],
                    "active",
                )

            # A fresh character selection is valid only after the normal native
            # exit has durably returned this second visit as well.
            with positions.account_barrier(account):
                positions.flush(account_id=account)
                with self.store.connection() as db:
                    current = self.store.character(account, character["id"], db)
                    authenticated = owned_story_exits.authenticate_exit(
                        db,
                        self.store,
                        current,
                        exit_body,
                        source_allowed=source_allowed,
                    )
                    destination = {
                        key: authenticated["destination"][key]
                        for key in ("map_id", "x", "y", "z")
                    }
                    dungeon_exit._leave(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        in_fight=lambda _identity: False,
                        destination_for=lambda *_: destination,
                        _db=db,
                    )
                positions.rebind_selected(account, generation, character["id"])
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                        (second_entry["instance_id"], character["id"]),
                    ).fetchone()["status"],
                    "returned",
                )

            positions.release(account, generation, character["id"])
            live.clear()
            self.store.select_character(account, generation, next_character["id"])
            selected = self.store.character(account, next_character["id"])
            self.assertEqual((selected["map_id"], selected["instance_id"]), (527, 0))
            self.store.select_character(account, generation, character["id"])
            selected = self.store.character(account, character["id"])
            self.assertEqual(
                tuple(
                    selected[key] for key in ("map_id", "instance_id", "x", "y", "z")
                ),
                (546, 0, -4, -8, 3),
            )
        finally:
            dungeon_instances._ROUTES = previous_routes


if __name__ == "__main__":
    import unittest

    unittest.main()
