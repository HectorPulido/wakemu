"""Final-victory party return is atomic and idempotent in isolated PostgreSQL."""
from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase
from test_dungeon_progression import DungeonProgressionPostgresTests as Fixture
from wakfu_server.maps import dungeon_auto_exit


class AutomaticDungeonExitContractTests(unittest.TestCase):
    def setUp(self):
        self.topology = {
            "asset_map_id": 1086,
            "policy": "local_accessible_anchor_policy",
            "completion_destination": {
                "map_id": 527,
                "x": -245,
                "y": -89,
                "z": 0,
                "provenance": {
                    "policy": "native_entry_approved_walkable_approach",
                },
            },
        }
        self.completed_result = {
            "victory": True,
            "completed": True,
            "current_room": 3,
            "revision": 3,
        }

    def test_local_policy_uses_only_native_entry_approach_and_strict_policy_returns_none(
        self,
    ):
        self.assertEqual(
            {"map_id": 527, "x": -245, "y": -89, "z": 0},
            dungeon_auto_exit.completion_destination(
                self.completed_result, self.topology
            ),
        )
        strict_native = dict(self.topology, policy="verified_native_door_topology")
        self.assertIsNone(
            dungeon_auto_exit.completion_destination(
                self.completed_result, strict_native
            )
        )

    def test_local_exit_rejects_nonfinal_or_unverified_destinations(self):
        for result in (
            dict(self.completed_result, victory=False),
            dict(self.completed_result, completed=False),
        ):
            with self.subTest(result=result), self.assertRaises(ValueError):
                dungeon_auto_exit.completion_destination(result, self.topology)
        bad = dict(self.topology)
        bad["completion_destination"] = dict(
            self.topology["completion_destination"],
            provenance={"policy": "guessed_coordinates"},
        )
        with self.assertRaisesRegex(ValueError, "native provenance"):
            dungeon_auto_exit.completion_destination(self.completed_result, bad)


class AutomaticDungeonExitPostgresTests(PostgresCase):
    """Run only against per-test schemas on the explicit migration-test DB."""

    install_context_policy = Fixture.install_context_policy
    player = Fixture.player
    party = Fixture.party
    create = Fixture.create
    make_fight = Fixture.make_fight
    bind = Fixture.bind
    finish = Fixture.finish

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy()
        self.members, self.party_id = self.party(2)
        self.instance_id = self.create(self.members[0])["instance_id"]
        with self.store.connection() as db:
            for member in self.members:
                db.execute(
                    "UPDATE characters SET map_id=1086,instance_id=%s,x=4,y=-12,z=0 WHERE id=%s",
                    (self.instance_id, member["character"]["id"]),
                )
        monster = SimpleNamespace(
            ref_id=1,
            count=1,
            native_min_level=1,
            native_max_level=5,
            role="monster",
        )
        rooms = tuple(
            SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
        )
        with self.store.connection() as db:
            from wakfu_server.maps.dungeon_progression import initialize_run

            initialize_run(
                db,
                self.instance_id,
                self.party_id,
                SimpleNamespace(
                    roster_ready=True, document_sha256="e" * 64, rooms=rooms
                ),
            )

    @property
    def topology(self):
        return {
            "asset_map_id": 1086,
            "policy": "local_accessible_anchor_policy",
            "rooms": [
                {"order": 1, "anchor": (4, -12, 0), "cells": [(4, -12, 0)]},
                {"order": 2, "anchor": (152, -10, 0), "cells": [(152, -10, 0)]},
            ],
            "doors": [],
            "auto_edges": [
                {"source_room": 1, "destination_room": 2, "anchor": (152, -10, 0)}
            ],
            "completion_destination": {
                "map_id": 527,
                "x": -245,
                "y": -89,
                "z": 0,
                "provenance": {"policy": "native_entry_approved_walkable_approach"},
            },
        }

    def final_victory(self):
        first = self.make_fight(self.members[0])
        self.bind(first)
        self.assertTrue(self.finish(first)["victory"])
        final = self.make_fight(self.members[0])
        self.bind(final)
        result = self.finish(final)
        self.assertTrue(result["victory"])
        self.assertTrue(result["completed"])
        self.assertEqual(2, result["current_room"])
        return final, result

    def complete(
        self, fight_id, *, in_fight=lambda _character_id: False, topology=None
    ):
        return dungeon_auto_exit.complete(
            self.store,
            self.instance_id,
            fight_id,
            topology=self.topology if topology is None else topology,
            in_fight=in_fight,
        )

    def party_state(self):
        ids = [member["character"]["id"] for member in self.members]
        with self.store.connection() as db:
            instance = db.execute(
                "SELECT status,revision,ended_at FROM dungeon_instances WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()
            progress = db.execute(
                "SELECT status,current_room,revision,rooms FROM dungeon_room_runs WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()
            members = db.execute(
                "SELECT character_id,status,session_generation FROM dungeon_instance_members "
                "WHERE instance_id=%s ORDER BY character_id",
                (self.instance_id,),
            ).fetchall()
            characters = db.execute(
                "SELECT id,map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s) ORDER BY id",
                (ids,),
            ).fetchall()
            outbox = db.execute(
                "SELECT character_id,session_generation,source_map_id,source_instance_id,"
                "destination_map_id,destination_instance_id,destination_x,destination_y,destination_z,"
                "transition_kind,status FROM dungeon_transition_outbox WHERE instance_id=%s "
                "AND transition_kind='exit' ORDER BY character_id,event_id",
                (self.instance_id,),
            ).fetchall()
        return instance, progress, members, characters, outbox

    def test_final_settlement_leaves_instance_active_then_returns_whole_party_once(
        self,
    ):
        fight_id, _ = self.final_victory()
        with self.store.connection() as db:
            before = db.execute(
                "SELECT status,revision,ended_at FROM dungeon_instances WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()
        self.assertEqual("active", before["status"])
        self.assertIsNone(before["ended_at"])
        self.assertEqual(1, before["revision"])

        result = self.complete(fight_id)
        self.assertFalse(result["replay"])
        self.assertEqual(0, result["instance_id"])
        self.assertEqual(
            tuple(sorted(m["character"]["id"] for m in self.members)), result["members"]
        )
        self.assertEqual(2, result["revision"])

        instance, progress, members, characters, outbox = self.party_state()
        self.assertEqual(("closed", 2), (instance["status"], instance["revision"]))
        self.assertIsNotNone(instance["ended_at"])
        self.assertEqual(
            ("completed", 2, 3),
            (progress["status"], progress["current_room"], progress["revision"]),
        )
        self.assertEqual(["returned", "returned"], [row["status"] for row in members])
        self.assertEqual(
            {(527, 0, -245, -89, 0)},
            {
                (row["map_id"], row["instance_id"], row["x"], row["y"], row["z"])
                for row in characters
            },
        )
        self.assertEqual(2, len(outbox))
        expected_generations = {
            m["character"]["id"]: m["generation"] for m in self.members
        }
        for event in outbox:
            self.assertEqual(
                expected_generations[event["character_id"]], event["session_generation"]
            )
            self.assertEqual(
                (1086, self.instance_id, 527, 0, -245, -89, 0, "exit", "pending"),
                (
                    event["source_map_id"],
                    event["source_instance_id"],
                    event["destination_map_id"],
                    event["destination_instance_id"],
                    event["destination_x"],
                    event["destination_y"],
                    event["destination_z"],
                    event["transition_kind"],
                    event["status"],
                ),
            )
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT result FROM dungeon_room_encounters WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()["result"]
        self.assertEqual(2, receipt["auto_exit_revision"])

        replay = self.complete(fight_id)
        self.assertTrue(replay["replay"])
        self.assertEqual(2, replay["revision"])
        self.assertEqual(2, len(self.party_state()[-1]))

    def test_strict_native_topology_does_not_auto_exit_or_mutate(self):
        fight_id, _ = self.final_victory()
        before = self.party_state()
        strict = dict(self.topology, policy="verified_native_door_topology")
        self.assertIsNone(self.complete(fight_id, topology=strict))
        self.assertEqual(before, self.party_state())

    def test_live_combat_or_stale_member_lease_defers_without_partial_exit(self):
        fight_id, _ = self.final_victory()
        before = self.party_state()
        second_id = self.members[1]["character"]["id"]
        deferred = self.complete(
            fight_id, in_fight=lambda character_id: character_id == second_id
        )
        self.assertTrue(deferred["deferred"])
        self.assertEqual("members_not_ready", deferred["reason"])
        self.assertEqual(before, self.party_state())

        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET generation='stale-generation' WHERE account_id=%s",
                (self.members[1]["account"],),
            )
        before_stale = self.party_state()
        stale = self.complete(fight_id)
        self.assertTrue(stale["deferred"])
        self.assertEqual("members_not_ready", stale["reason"])
        self.assertEqual(before_stale, self.party_state())

    def test_outbox_failure_rolls_back_locations_membership_run_and_receipt(self):
        fight_id, _ = self.final_victory()
        before = self.party_state()
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_automatic_dungeon_exit() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "IF NEW.transition_kind='exit' THEN RAISE EXCEPTION 'automatic exit rejected'; END IF; "
                "RETURN NEW; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_automatic_dungeon_exit BEFORE INSERT ON dungeon_transition_outbox "
                "FOR EACH ROW EXECUTE FUNCTION reject_automatic_dungeon_exit()"
            )
        with self.assertRaisesRegex(Exception, "automatic exit rejected"):
            self.complete(fight_id)
        self.assertEqual(before, self.party_state())
        with self.store.connection() as db:
            db.execute(
                "DROP TRIGGER reject_automatic_dungeon_exit ON dungeon_transition_outbox"
            )
            db.execute("DROP FUNCTION reject_automatic_dungeon_exit()")


del Fixture


if __name__ == "__main__":
    unittest.main()
