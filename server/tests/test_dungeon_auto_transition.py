import copy
import unittest
from types import SimpleNamespace

from postgres_case import PostgresCase
import test_dungeon_instances
from wakfu_server.maps import dungeon_auto_transition
from wakfu_server.maps.dungeon_progression import (
    bind_encounter,
    initialize_run,
    settle_encounter,
)
from wakfu_server.dungeon_auto_transition import next_anchor


class AutomaticDungeonAnchorTests(unittest.TestCase):
    def setUp(self):
        self.result = dict(victory=True, completed=False, current_room=2, revision=1)
        self.topology = dict(
            asset_map_id=3,
            rooms=[dict(order=1, anchor=(0, 0, 0)), dict(order=2, anchor=(10, 0, 0))],
            doors=[dict(source_room=1, destination_room=2, anchor=(10, 0, 0))],
        )

    def test_verified_next_anchor(self):
        self.assertEqual(
            dict(map_id=3, x=10, y=0, z=0), next_anchor(self.result, self.topology)
        )

    def test_final_victory_never_moves_to_a_fabricated_room(self):
        self.result["completed"] = True
        self.assertIsNone(next_anchor(self.result, self.topology))

    def test_defeat_cannot_move_party(self):
        self.result["victory"] = False
        with self.assertRaises(ValueError):
            next_anchor(self.result, self.topology)

    def test_duplicate_forward_link_rejected(self):
        self.topology["doors"].append(copy.deepcopy(self.topology["doors"][0]))
        with self.assertRaises(ValueError):
            next_anchor(self.result, self.topology)

    def test_disagreeing_room_and_door_anchors_rejected(self):
        self.topology["rooms"][1]["anchor"] = (99, 0, 0)
        with self.assertRaises(ValueError):
            next_anchor(self.result, self.topology)

    def test_missing_next_room_rejected(self):
        self.result["current_room"] = 3
        with self.assertRaises(ValueError):
            next_anchor(self.result, self.topology)

    def test_generated_local_policy_accepts_native_accessible_room_anchor(self):
        topology = {
            "asset_map_id": 1086,
            "policy": "local_accessible_anchor_policy",
            "rooms": [
                {"order": 1, "anchor": (0, 0, 0), "cells": [(0, 0, 0)]},
                {"order": 2, "anchor": (10, 0, 0), "cells": [(10, 0, 0), (11, 0, 0)]},
            ],
            "doors": [],
            "auto_edges": [
                {"source_room": 1, "destination_room": 2, "anchor": (10, 0, 0)}
            ],
        }
        self.assertEqual(
            {"map_id": 1086, "x": 10, "y": 0, "z": 0},
            next_anchor(self.result, topology),
        )

    def test_generated_local_policy_rejects_anchor_outside_native_cells(self):
        topology = {
            "asset_map_id": 1086,
            "policy": "local_accessible_anchor_policy",
            "rooms": [
                {"order": 1, "anchor": (0, 0, 0), "cells": [(0, 0, 0)]},
                {"order": 2, "anchor": (10, 0, 0), "cells": [(11, 0, 0)]},
            ],
            "doors": [],
            "auto_edges": [
                {"source_room": 1, "destination_room": 2, "anchor": (10, 0, 0)}
            ],
        }
        with self.assertRaisesRegex(ValueError, "not in its native accessible cells"):
            next_anchor(self.result, topology)

    def test_auto_edges_without_explicit_local_policy_are_rejected(self):
        topology = {
            "asset_map_id": 1086,
            "rooms": [
                {"order": 1, "anchor": (0, 0, 0)},
                {"order": 2, "anchor": (10, 0, 0)},
            ],
            "doors": [],
            "auto_edges": [
                {"source_room": 1, "destination_room": 2, "anchor": (10, 0, 0)}
            ],
        }
        with self.assertRaisesRegex(ValueError, "require an explicit local policy"):
            next_anchor(self.result, topology)

    def test_local_policy_rejects_native_door_claims(self):
        topology = {
            "asset_map_id": 1086,
            "policy": "local_accessible_anchor_policy",
            "rooms": [
                {"order": 1, "anchor": (0, 0, 0), "cells": [(0, 0, 0)]},
                {"order": 2, "anchor": (10, 0, 0), "cells": [(10, 0, 0)]},
            ],
            "doors": [{"source_room": 1, "destination_room": 2, "anchor": (10, 0, 0)}],
            "auto_edges": [
                {"source_room": 1, "destination_room": 2, "anchor": (10, 0, 0)}
            ],
        }
        with self.assertRaisesRegex(ValueError, "cannot claim native doors"):
            next_anchor(self.result, topology)


class AutomaticDungeonTransitionPostgresTests(PostgresCase):
    """Exercise party auto-travel using disposable PostgreSQL schemas."""

    install_context_policy = (
        test_dungeon_instances.DungeonInstanceTests.install_context_policy
    )
    player = test_dungeon_instances.DungeonInstanceTests.player
    party = test_dungeon_instances.DungeonInstanceTests.party
    enter = test_dungeon_instances.DungeonInstanceTests.enter

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)
        self.members, self.party_id = self.party(2)
        self.instance_id = self.enter(self.members[0])["instance_id"]
        monster = SimpleNamespace(
            ref_id=1,
            count=1,
            native_min_level=1,
            native_max_level=5,
            role="monster",
        )
        plan = SimpleNamespace(
            roster_ready=True,
            document_sha256="c" * 64,
            rooms=tuple(
                SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
            ),
        )
        with self.store.connection() as db:
            initialize_run(db, self.instance_id, self.party_id, plan)

    @property
    def topology(self):
        return {
            "asset_map_id": 1086,
            "rooms": [
                {"order": 1, "anchor": (4, -12, 0)},
                {"order": 2, "anchor": (152, -10, 0)},
            ],
            "doors": [
                {
                    "source_room": 1,
                    "destination_room": 2,
                    "anchor": (152, -10, 0),
                }
            ],
        }

    def make_fight(self):
        member = self.members[0]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (fight_id, member["character"]["id"], member["account"]),
            )
            bind_encounter(
                db,
                self.instance_id,
                self.party_id,
                member["character"]["id"],
                fight_id,
                player_team=0,
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            result = settle_encounter(
                db, SimpleNamespace(id=fight_id, phase="finished", winner=0)
            )
        return fight_id, result

    def advance(self, fight_id, *, in_fight=lambda _character_id: False):
        return dungeon_auto_transition.advance(
            self.store,
            self.instance_id,
            fight_id,
            topology=self.topology,
            in_fight=in_fight,
        )

    def locations(self):
        ids = [member["character"]["id"] for member in self.members]
        with self.store.connection() as db:
            return db.execute(
                "SELECT id,map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s) "
                "ORDER BY id",
                (ids,),
            ).fetchall()

    def pending_outbox(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT character_id,session_generation,source_instance_id,source_x,"
                "source_y,source_z,destination_map_id,destination_instance_id,"
                "destination_x,destination_y,destination_z,transition_kind,status "
                "FROM dungeon_transition_outbox WHERE instance_id=%s "
                "AND transition_kind='door' ORDER BY character_id,event_id",
                (self.instance_id,),
            ).fetchall()

    def test_success_moves_all_members_and_stores_leases_result_and_outbox(self):
        fight_id, settled = self.make_fight()
        self.assertTrue(settled["victory"])
        before = self.locations()
        moved = self.advance(fight_id)
        self.assertFalse(moved["replay"])
        self.assertEqual(tuple(sorted(row["id"] for row in before)), moved["members"])
        self.assertEqual(2, moved["revision"])
        self.assertEqual(
            {(1086, self.instance_id, 152, -10, 0)},
            {
                (row["map_id"], row["instance_id"], row["x"], row["y"], row["z"])
                for row in self.locations()
            },
        )
        events = self.pending_outbox()
        self.assertEqual(2, len(events))
        expected_generations = {
            member["character"]["id"]: member["generation"] for member in self.members
        }
        for event in events:
            self.assertEqual(
                expected_generations[event["character_id"]], event["session_generation"]
            )
            self.assertEqual(
                (
                    self.instance_id,
                    1086,
                    self.instance_id,
                    152,
                    -10,
                    0,
                    "door",
                    "pending",
                ),
                (
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
            saved = db.execute(
                "SELECT result FROM dungeon_room_encounters WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()["result"]
            self.assertEqual(moved["revision"], saved["auto_transition_revision"])

    def test_deferred_member_and_replay_never_partially_move_or_duplicate(self):
        fight_id, _ = self.make_fight()
        before = self.locations()
        deferred = self.advance(
            fight_id,
            in_fight=lambda character_id: character_id
            == self.members[1]["character"]["id"],
        )
        self.assertTrue(deferred["deferred"])
        self.assertEqual(before, self.locations())
        self.assertEqual([], self.pending_outbox())
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT result FROM dungeon_room_encounters WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()["result"]
        self.assertNotIn("auto_transition_revision", saved)

        moved = self.advance(fight_id)
        replay = self.advance(fight_id)
        self.assertFalse(moved["replay"])
        self.assertTrue(replay["replay"])
        self.assertEqual(moved["revision"], replay["revision"])
        self.assertEqual(2, len(self.pending_outbox()))

    def test_wrong_instance_member_is_deferred_without_partial_move(self):
        fight_id, _ = self.make_fight()
        member_id = self.members[1]["character"]["id"]
        with self.store.connection() as db:
            db.execute("UPDATE characters SET instance_id=0 WHERE id=%s", (member_id,))
        before = self.locations()
        result = self.advance(fight_id)
        self.assertTrue(result["deferred"])
        self.assertEqual("members_not_ready", result["reason"])
        self.assertEqual(before, self.locations())
        self.assertEqual([], self.pending_outbox())

    def test_defeat_cannot_move_members_or_create_award_side_effects(self):
        member = self.members[0]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (fight_id, member["character"]["id"], member["account"]),
            )
            bind_encounter(
                db,
                self.instance_id,
                self.party_id,
                member["character"]["id"],
                fight_id,
                player_team=0,
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            settled = settle_encounter(
                db, SimpleNamespace(id=fight_id, phase="finished", winner=1)
            )
        before = self.locations()
        self.assertFalse(settled["victory"])
        with self.assertRaisesRegex(ValueError, "committed dungeon victory"):
            self.advance(fight_id)
        self.assertEqual(before, self.locations())
        self.assertEqual([], self.pending_outbox())
        with self.store.connection() as db:
            run = db.execute(
                "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()
            result = db.execute(
                "SELECT result FROM dungeon_room_encounters WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()["result"]
        self.assertEqual(1, run["current_room"])
        self.assertFalse(result["victory"])
        self.assertNotIn("auto_transition_revision", result)

    def test_outbox_failure_rolls_back_all_positions_revision_and_receipt(self):
        fight_id, _ = self.make_fight()
        before = self.locations()
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_auto_transition_outbox() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'auto outbox rejected'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_auto_transition_outbox BEFORE INSERT ON "
                "dungeon_transition_outbox FOR EACH ROW EXECUTE FUNCTION "
                "reject_auto_transition_outbox()"
            )
        with self.assertRaisesRegex(Exception, "auto outbox rejected"):
            self.advance(fight_id)
        self.assertEqual(before, self.locations())
        self.assertEqual([], self.pending_outbox())
        with self.store.connection() as db:
            run = db.execute(
                "SELECT revision FROM dungeon_instances WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()
            receipt = db.execute(
                "SELECT result FROM dungeon_room_encounters WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()["result"]
            self.assertEqual(1, run["revision"])
            self.assertNotIn("auto_transition_revision", receipt)
            db.execute(
                "DROP TRIGGER reject_auto_transition_outbox ON dungeon_transition_outbox"
            )
            db.execute("DROP FUNCTION reject_auto_transition_outbox()")
        self.assertFalse(self.advance(fight_id)["replay"])
