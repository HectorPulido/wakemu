"""Durable exterior returns retain pending delivery after a run closes."""

import struct
from unittest.mock import patch

from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as Fixture
from wakfu_server import dungeon_instances
from wakfu_server.maps import dungeon_exit
from wakfu_server.maps.dungeon_hydration import prepare_transition


class DungeonExitTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)

    install_context_policy = Fixture.install_context_policy
    player = Fixture.player
    party = Fixture.party
    enter = Fixture.enter

    def test_automatic_exit_preserves_party_and_rejects_combat(self):
        members, _ = self.party(2)
        run = self.enter(members[0])
        member = members[0]
        character_id = member["character"]["id"]
        character = self.store.character(member["account"], character_id)
        configuration = {
            "topology": {
                "policy": "local_accessible_anchor_policy",
                "asset_map_id": character["map_id"],
                "completion_destination": {
                    "map_id": 527,
                    "x": -245,
                    "y": -89,
                    "z": 0,
                    "provenance": {"policy": "native_entry_approved_walkable_approach"},
                },
            }
        }
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            return_value=(None, configuration),
        ) as lookup:
            with self.assertRaises(ValueError):
                dungeon_exit.leave_automatic(
                    self.store,
                    member["account"],
                    member["generation"],
                    character_id,
                    in_fight=lambda identity: True,
                )
            lookup.assert_not_called()
            result = dungeon_exit.leave_automatic(
                self.store,
                member["account"],
                member["generation"],
                character_id,
                in_fight=lambda identity: False,
            )
        self.assertEqual(result["instance_id"], 0)
        self.assertEqual(result["x"], -245)
        self.assertEqual(
            self.store.character(members[1]["account"], members[1]["character"]["id"])[
                "instance_id"
            ],
            run["instance_id"],
        )
        events = dungeon_instances.pending_transitions(
            self.store, member["account"], member["generation"], character_id
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["transition_kind"], "exit")

    def test_automatic_destination_rejects_unowned_or_unproven_exit(self):
        configuration = {
            "topology": {
                "policy": "local_accessible_anchor_policy",
                "asset_map_id": 1086,
                "completion_destination": {
                    "map_id": 527,
                    "x": -245,
                    "y": -89,
                    "z": 0,
                    "provenance": {"policy": "native_entry_approved_walkable_approach"},
                },
            }
        }
        for character, run in (
            ({"map_id": 1087}, {"entry_map_id": 527}),
            ({"map_id": 1086}, {"entry_map_id": 528}),
        ):
            with self.assertRaises(ValueError):
                dungeon_exit.automatic_destination(character, run, configuration)
        configuration["topology"]["completion_destination"]["provenance"] = {}
        with self.assertRaises(ValueError):
            dungeon_exit.automatic_destination(
                {"map_id": 1086}, {"entry_map_id": 527}, configuration
            )

    def leave(self, member, **callbacks):
        return dungeon_exit.leave(
            self.store,
            member["account"],
            member["generation"],
            member["character"]["id"],
            struct.pack(">qiBi", 26843, 2505, 0, 2),
            source_allowed=callbacks.get(
                "source_allowed", lambda character, source: True
            ),
            in_fight=callbacks.get("in_fight", lambda character_id: False),
        )

    def test_last_exit_remains_deliverable_after_run_closes(self):
        members, party_id = self.party(2)
        run = self.enter(members[0])
        first = self.leave(members[0])
        self.assertEqual(first["instance_id"], 0)
        self.assertEqual(
            self.store.character(members[1]["account"], members[1]["character"]["id"])[
                "instance_id"
            ],
            run["instance_id"],
        )
        self.leave(members[1])
        for member in members:
            events = dungeon_instances.pending_transitions(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
            )
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["transition_kind"], "exit")
            plan = prepare_transition(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                events[0],
            )
            self.assertEqual(plan.character["map_id"], 527)
            self.assertTrue(
                dungeon_instances.acknowledge_transition(
                    self.store,
                    member["account"],
                    member["generation"],
                    member["character"]["id"],
                    events[0]["event_id"],
                )
            )
            self.assertFalse(
                dungeon_instances.acknowledge_transition(
                    self.store,
                    member["account"],
                    member["generation"],
                    member["character"]["id"],
                    events[0]["event_id"],
                )
            )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                (run["instance_id"],),
            ).fetchone()
        self.assertEqual(row["status"], "closed")

    def test_combat_or_denied_source_preserves_private_location(self):
        members, _ = self.party(2)
        run = self.enter(members[0])
        for callbacks in (
            dict(in_fight=lambda character_id: True),
            dict(source_allowed=lambda character, source: False),
        ):
            with self.assertRaises(ValueError):
                self.leave(members[0], **callbacks)
            self.assertEqual(
                self.store.character(
                    members[0]["account"], members[0]["character"]["id"]
                )["instance_id"],
                run["instance_id"],
            )

    def test_initializer_failure_rolls_back_entry_and_outbox(self):
        members, _ = self.party(2)

        def fail(db, session):
            raise ValueError("Initializer failed")

        from wakfu_server import dungeon_transport

        with self.assertRaisesRegex(ValueError, "Initializer failed"):
            dungeon_transport.enter(
                self.store,
                members[0]["account"],
                members[0]["generation"],
                members[0]["character"]["id"],
                527,
                struct.pack(">qiBi", 26842, 2504, 0, 2),
                criterion_allowed=lambda character, criterion: True,
                source_allowed=lambda character, source: True,
                initialize_instance=fail,
            )
        for member in members:
            self.assertEqual(
                self.store.character(member["account"], member["character"]["id"])[
                    "instance_id"
                ],
                0,
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox"
                ).fetchone()["n"],
                0,
            )
