"""Isolated SQL proof for the canonical zero-room archaeology context."""

import json
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import Mock

from postgres_case import PostgresCase
from wakfu_server import dungeon_instances, generic_transports
from wakfu_server.application import owned_object_trial_dispatch
from wakfu_server.maps import (
    dungeon_runtime,
    dungeon_runtime_config,
    owned_physical_entry,
)
from wakfu_server.position_buffer import Positions
from wakfu_server.movement import Movement
from wakfu_server.achievements import storage


CONFIG_PATH = (
    Path(__file__).parents[1]
    / "wakfu_server/maps/owned_object_trial_profiles/archaeology-2698.configuration.json"
)


class ArchaeologyNoncombatContextPostgresTests(PostgresCase):
    def test_canonical_admission_bootstrap_native_exit_and_next_character_selection(
        self,
    ):
        config = json.loads(CONFIG_PATH.read_text())
        account = self.store.register(
            "archaeology-zero-room", "isolated-test-password"
        )["id"]
        actor = self.store.create_character(account, "Archaeology Owner")
        next_actor = self.store.create_character(account, "Archaeology Next")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, actor["id"])
        entry_source = generic_transports.source(1134, 25474)
        entry = next(
            row for row in entry_source["destinations"] if row["destination_id"] == 2290
        )
        self.assertEqual(
            (entry["item_reference"], entry["cyW"], entry["cyX"]), (0, 0, 0)
        )
        entry_character = dict(actor, map_id=1134, instance_id=0, x=-21, y=66, z=-16)

        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, config)
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=0,x=-21,y=66,z=-16 "
                "WHERE id=%s AND account_id=%s",
                (actor["id"], account),
            )

        original_routes = dungeon_instances._ROUTES
        try:
            loaded_routes = dungeon_instances.load_runtime_routes(self.store)
            route = dungeon_instances.route(config["route"]["key"])
            self.assertIn(route, loaded_routes)
            self.assertTrue(owned_physical_entry.qualifies(self.store, route))
            source_allowed = __import__(
                "wakfu_server.teleporter_approach", fromlist=["callback"]
            ).callback(Movement(entry_character), map_id=1134)

            def authorize(current, selected_route):
                return (
                    selected_route == route
                    and source_allowed(current, entry_source)
                    and owned_physical_entry.allowed(
                        self.store, current, selected_route
                    )
                )

            groups = Mock()

            def initialize(db, admitted):
                return dungeon_runtime.initialize_instance(
                    db, admitted, groups=groups, geometry={}, store=self.store
                )

            admitted = dungeon_instances.create_or_reuse(
                self.store,
                account,
                generation,
                actor["id"],
                route.key,
                authorize_entry=authorize,
                transition_destination={
                    key: entry[key] for key in ("map_id", "x", "y", "z")
                },
                initialize_instance=initialize,
            )
            instance_id = admitted["instance_id"]
            self.assertEqual(admitted["transition"]["instance_id"], instance_id)
            groups.assert_not_called()
            with self.store.connection() as db:
                pinned_run, pinned = dungeon_runtime.configuration_for_instance(
                    db, instance_id
                )
                self.assertEqual(
                    pinned_run["context_route_key"], config["route"]["key"]
                )
                self.assertEqual(
                    pinned_run["context_policy_version"], config["version"]
                )
                self.assertEqual(pinned["topology"]["rooms"], [])
                member = db.execute(
                    "SELECT status,session_generation FROM dungeon_instance_members "
                    "WHERE instance_id=%s AND character_id=%s",
                    (instance_id, actor["id"]),
                ).fetchone()
                self.assertEqual(
                    (member["status"], member["session_generation"]),
                    ("active", generation),
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM dungeon_room_runs WHERE instance_id=%s",
                        (instance_id,),
                    ).fetchone()["n"],
                    0,
                )
                current = self.store.character(account, actor["id"], db)
                quest_state = storage.load_locked(db, actor["id"])
            self.assertNotIn(2698, quest_state["running"])
            self.assertNotIn(2698, quest_state["completed"])
            self.assertEqual(
                (
                    current["map_id"],
                    current["instance_id"],
                    current["x"],
                    current["y"],
                    current["z"],
                ),
                (1001, instance_id, -15, -9, 0),
            )

            live = {(account, generation, actor["id"])}
            positions = Positions(
                self.store, lease_active=lambda a, g, c: (a, g, c) in live
            )
            inside = positions.attach(account, generation, current)
            exit_source = generic_transports.source(1001, 31332)
            source_allowed = __import__(
                "wakfu_server.teleporter_approach", fromlist=["callback"]
            ).callback(Movement(inside), map_id=1001, instance_id=instance_id)
            state = SimpleNamespace(
                account_id=account,
                generation=generation,
                character=inside,
                body=struct.pack(">qiBi", 31332, 3943, 0, 2),
                connection=SimpleNamespace(owned_object_trials_active=True),
            )
            session = SimpleNamespace(
                state=state,
                runtime=SimpleNamespace(
                    STORE=self.store,
                    POSITIONS=positions,
                    flush_positions=lambda **kwargs: positions.flush(**kwargs),
                ),
                deliver_dungeon_transitions=Mock(),
            )
            self.assertTrue(
                owned_object_trial_dispatch.handle_travel(
                    session,
                    pinned,
                    source_allowed=source_allowed,
                    in_fight=lambda _id: False,
                )
            )
            session.deliver_dungeon_transitions.assert_called_once_with(
                before_action=True
            )
            self.assertFalse(state.connection.owned_object_trials_active)
            self.assertEqual(
                tuple(
                    positions.entry_snapshot((account, generation, actor["id"]))[
                        "current"
                    ][key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                ),
                (1134, 0, -21, 66, -16),
            )
            with self.store.connection() as db:
                member = db.execute(
                    "SELECT status FROM dungeon_instance_members "
                    "WHERE instance_id=%s AND character_id=%s",
                    (instance_id, actor["id"]),
                ).fetchone()
                pending = db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox "
                    "WHERE instance_id=%s AND character_id=%s AND transition_kind='exit' AND status='pending'",
                    (instance_id, actor["id"]),
                ).fetchone()["n"]
                self.assertEqual(member["status"], "returned")
                self.assertEqual(pending, 1)

            # Selecting a different owned character after the native exit is
            # still a valid bootstrap path; the returned run member stays out.
            self.store.select_character(account, generation, next_actor["id"])
            selected = self.store.character(account, next_actor["id"])
            self.assertEqual((selected["map_id"], selected["instance_id"]), (527, 0))
            live.add((account, generation, next_actor["id"]))
            positions.attach(account, generation, selected)
        finally:
            dungeon_instances._ROUTES = original_routes


if __name__ == "__main__":
    import unittest

    unittest.main()
