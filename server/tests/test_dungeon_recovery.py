"""Selected lease recovery preserves private location and fences old delivery."""

import ast
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as Fixture
from wakfu_server import dungeon_instances
from wakfu_server.dungeon_recovery import (
    DungeonLoginRecoveryDeferred,
    has_persisted_context,
    prepare_selected_room,
    resume_member,
)


class DungeonRecoveryTests(PostgresCase):
    install_context_policy = Fixture.install_context_policy
    player = Fixture.player
    party = Fixture.party
    enter = Fixture.enter

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)

    def test_new_selected_generation_rebinds_only_owned_member(self):
        members, _ = self.party(2)
        run = self.enter(members[0])
        actor = members[0]
        before = self.store.character(actor["account"], actor["character"]["id"])
        generation = self.store.begin_session(actor["account"], ttl=10000)
        self.store.select_character(
            actor["account"], generation, actor["character"]["id"]
        )
        result = resume_member(
            self.store,
            actor["account"],
            generation,
            actor["character"]["id"],
            run["instance_id"],
        )
        self.assertTrue(result["rebound"])
        self.assertIsNotNone(
            dungeon_instances.authorize_member(
                self.store,
                actor["account"],
                generation,
                actor["character"]["id"],
                run["instance_id"],
            )
        )
        after = self.store.character(actor["account"], actor["character"]["id"])
        self.assertEqual(
            tuple(before[key] for key in ("map_id", "instance_id", "x", "y", "z")),
            tuple(after[key] for key in ("map_id", "instance_id", "x", "y", "z")),
        )
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT character_id,session_generation FROM dungeon_instance_members ORDER BY character_id"
            ).fetchall()
            old = db.execute(
                "SELECT status FROM dungeon_transition_outbox WHERE character_id=%s",
                (actor["character"]["id"],),
            ).fetchone()
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(
            next(
                row["session_generation"]
                for row in rows
                if row["character_id"] == members[1]["character"]["id"]
            ),
            members[1]["generation"],
        )
        self.assertFalse(
            resume_member(
                self.store,
                actor["account"],
                generation,
                actor["character"]["id"],
                run["instance_id"],
            )["rebound"]
        )

    def test_stale_membership_recovers_to_pinned_exterior_and_fences_old_entry(self):
        for defect in ("social_missing", "returned", "closed"):
            with self.subTest(defect=defect):
                members, _ = self.party(2)
                run = self.enter(members[0])
                actor = members[0]
                identity = actor["character"]["id"]
                with self.store.connection() as db:
                    if defect == "social_missing":
                        db.execute(
                            "UPDATE player_parties SET leader_id=%s WHERE id=%s",
                            (members[1]["character"]["id"], run["party_id"]),
                        )
                        db.execute(
                            "DELETE FROM player_party_members WHERE character_id=%s",
                            (identity,),
                        )
                    elif defect == "returned":
                        db.execute(
                            "UPDATE dungeon_instance_members SET status='returned',ended_at=CURRENT_TIMESTAMP WHERE character_id=%s",
                            (identity,),
                        )
                    else:
                        db.execute(
                            "UPDATE dungeon_instances SET status=%s,ended_at=CURRENT_TIMESTAMP WHERE instance_id=%s",
                            (defect, run["instance_id"]),
                        )
                configuration = {
                    "topology": {
                        "policy": "local_accessible_anchor_policy",
                        "asset_map_id": 1086,
                        "completion_destination": {
                            "map_id": 527,
                            "x": -245,
                            "y": -89,
                            "z": 0,
                            "provenance": {
                                "policy": "native_entry_approved_walkable_approach"
                            },
                        },
                    }
                }
                with patch(
                    "wakfu_server.dungeon_runtime.configuration_for_instance",
                    return_value=(None, configuration),
                ):
                    result = resume_member(
                        self.store,
                        actor["account"],
                        actor["generation"],
                        identity,
                        run["instance_id"],
                    )
                self.assertTrue(result["recovered_exterior"])
                after = self.store.character(actor["account"], identity)
                self.assertEqual(
                    (after["map_id"], after["instance_id"], after["x"], after["y"]),
                    (527, 0, -245, -89),
                )
                with self.store.connection() as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT status FROM dungeon_transition_outbox WHERE character_id=%s ORDER BY event_id DESC LIMIT 1",
                            (identity,),
                        ).fetchone()["status"],
                        "superseded",
                    )
                companion = self.store.character(
                    members[1]["account"], members[1]["character"]["id"]
                )
                self.assertEqual(companion["instance_id"], run["instance_id"])

    def test_completed_run_keeps_owned_postboss_location_and_rebinds(self):
        members, _ = self.party(2)
        run = self.enter(members[0])
        actor = members[0]
        identity = actor["character"]["id"]
        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_instances SET status='completed',ended_at=CURRENT_TIMESTAMP "
                "WHERE instance_id=%s",
                (run["instance_id"],),
            )
        before = self.store.character(actor["account"], identity)
        self.assertTrue(has_persisted_context(self.store, before))
        generation = self.store.begin_session(actor["account"], ttl=10000)
        self.store.select_character(actor["account"], generation, identity)
        result = resume_member(
            self.store, actor["account"], generation, identity, run["instance_id"]
        )
        self.assertTrue(result["rebound"])
        self.assertNotIn("recovered_exterior", result)
        after = self.store.character(actor["account"], identity)
        for key in ("map_id", "instance_id", "x", "y", "z"):
            self.assertEqual(before[key], after[key])

    def test_closed_run_invalid_configuration_recovers_recorded_source_and_position(
        self,
    ):
        from wakfu_server.position_buffer import Positions

        members, _ = self.party(2)
        actor = members[0]
        identity = actor["character"]["id"]
        before = self.store.character(actor["account"], identity)
        run = self.enter(actor)
        character = self.store.character(actor["account"], identity)
        positions = Positions(self.store, lease_active=lambda *args: True)
        positions.attach(actor["account"], actor["generation"], character)
        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_instances SET status='closed',ended_at=CURRENT_TIMESTAMP "
                "WHERE instance_id=%s",
                (run["instance_id"],),
            )
        self.assertTrue(has_persisted_context(self.store, character))
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            side_effect=ValueError("Pinned room configuration is unavailable"),
        ), patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(
                cells={(before["x"], before["y"], before["z"])}
            ),
        ):
            result = resume_member(
                self.store,
                actor["account"],
                actor["generation"],
                identity,
                run["instance_id"],
                positions=positions,
            )
        self.assertTrue(result["recovered_exterior"])
        after = self.store.character(actor["account"], identity)
        for key in ("map_id", "instance_id", "x", "y", "z"):
            self.assertEqual(before[key], after[key])
        entry = positions.entries[(actor["account"], actor["generation"], identity)]
        self.assertEqual(entry["current"]["instance_id"], 0)
        self.assertEqual(entry["persisted"]["instance_id"], 0)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                    (run["instance_id"], identity),
                ).fetchone()["status"],
                "returned",
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM dungeon_transition_outbox WHERE character_id=%s AND status='pending'",
                    (identity,),
                ).fetchone()
            )
        self.assertEqual(
            self.store.character(members[1]["account"], members[1]["character"]["id"])[
                "instance_id"
            ],
            run["instance_id"],
        )

    def test_recorded_source_must_remain_walkable(self):
        members, _ = self.party(2)
        actor = members[0]
        identity = actor["character"]["id"]
        run = self.enter(actor)
        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_instances SET status='closed',ended_at=CURRENT_TIMESTAMP "
                "WHERE instance_id=%s",
                (run["instance_id"],),
            )
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            side_effect=ValueError("Pinned room configuration is unavailable"),
        ), patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(cells=set()),
        ), self.assertRaisesRegex(
            DungeonLoginRecoveryDeferred, "no verified public"
        ):
            resume_member(
                self.store,
                actor["account"],
                actor["generation"],
                identity,
                run["instance_id"],
            )
        self.assertEqual(
            self.store.character(actor["account"], identity)["instance_id"],
            run["instance_id"],
        )

    def test_public_return_repairs_company_lock_before_selection_and_creation(self):
        members, _ = self.party(2)
        actor = members[0]
        identity = actor["character"]["id"]
        alternate = self.store.create_character(actor["account"], "Recovered Alternate")
        run = self.enter(actor)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=-245,y=-90,z=2 WHERE id=%s",
                (identity,),
            )
        generation = self.store.begin_session(actor["account"], ttl=10000)
        selected = self.store.select_character(
            actor["account"], generation, alternate["id"]
        )
        self.assertEqual(selected["id"], alternate["id"])
        created = self.store.create_character(
            actor["account"], "Recovered New", selection_generation=generation
        )
        self.assertGreater(created["id"], 0)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                    (run["instance_id"], identity),
                ).fetchone()["status"],
                "returned",
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM dungeon_transition_outbox WHERE character_id=%s AND status='pending'",
                    (identity,),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                    (run["instance_id"], members[1]["character"]["id"]),
                ).fetchone()["status"],
                "active",
            )

    def test_active_broken_room_can_recover_without_moving_other_account(self):
        members, _ = self.party(2)
        actor = members[0]
        identity = actor["character"]["id"]
        run = self.enter(actor)
        before = actor["character"]
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            side_effect=ValueError("Broken runtime configuration"),
        ), patch(
            "wakfu_server.dungeon_runtime.ensure_current_room",
            side_effect=ValueError("Broken room geometry"),
        ), patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(
                cells={(before["x"], before["y"], before["z"])}
            ),
        ):
            result = prepare_selected_room(
                self.store,
                SimpleNamespace(lock=threading.RLock()),
                actor["account"],
                actor["generation"],
                identity,
                positions=None,
                in_fight=lambda _: False,
                geometry_provider=lambda _: SimpleNamespace(cells=set()),
            )
        self.assertEqual(result["instance_id"], 0)
        self.assertEqual(
            self.store.character(actor["account"], identity)["instance_id"], 0
        )
        self.assertEqual(
            self.store.character(members[1]["account"], members[1]["character"]["id"])[
                "instance_id"
            ],
            run["instance_id"],
        )

    def test_live_combat_reconnect_never_rehydrates_or_moves_room(self):
        members, _ = self.party(2)
        actor = members[0]
        identity = actor["character"]["id"]
        run = self.enter(actor)
        with patch(
            "wakfu_server.dungeon_runtime.ensure_current_room",
            side_effect=AssertionError("Live combat owns its actors"),
        ):
            result = prepare_selected_room(
                self.store,
                None,
                actor["account"],
                actor["generation"],
                identity,
                positions=None,
                in_fight=lambda _: True,
                geometry_provider=lambda _: self.fail("Live combat geometry"),
            )
        self.assertEqual(result["instance_id"], run["instance_id"])

    def test_missing_social_party_during_live_combat_preserves_private_location(self):
        members, _ = self.party(2)
        run = self.enter(members[0])
        actor = members[0]
        identity = actor["character"]["id"]
        with self.store.connection() as db:
            db.execute(
                "UPDATE player_parties SET leader_id=%s WHERE id=%s",
                (members[1]["character"]["id"], run["party_id"]),
            )
            db.execute(
                "DELETE FROM player_party_members WHERE character_id=%s", (identity,)
            )
        result = resume_member(
            self.store,
            actor["account"],
            actor["generation"],
            identity,
            run["instance_id"],
            in_fight=lambda _: True,
        )
        self.assertEqual(result["instance_id"], run["instance_id"])
        self.assertNotIn("recovered_exterior", result)

    def test_forged_instance_or_unselected_new_session_is_rejected(self):
        members, _ = self.party(2)
        run = self.enter(members[0])
        actor = members[0]
        with self.assertRaises(ValueError):
            resume_member(
                self.store,
                actor["account"],
                actor["generation"],
                actor["character"]["id"],
                run["instance_id"] + 1,
            )
        generation = self.store.begin_session(actor["account"], ttl=10000)
        with self.assertRaises(ValueError):
            resume_member(
                self.store,
                actor["account"],
                generation,
                actor["character"]["id"],
                run["instance_id"],
            )


class DungeonLoginRecoveryDispatchTests(unittest.TestCase):
    def test_selection_uses_persisted_context_before_active_room_check(self):
        source = ast.parse(
            Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("local_game_server.py")
            .read_text()
        )
        calls = [
            node
            for node in ast.walk(source)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "has_persisted_context"
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].func.value.id, "dungeon_recovery")
        resumes = [
            node
            for node in ast.walk(source)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "resume_member"
        ]
        self.assertTrue(
            any(keyword.arg == "positions" for keyword in resumes[0].keywords)
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "prepare_selected_room"
                for node in ast.walk(source)
            )
        )
