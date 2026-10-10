"""Selected lease recovery preserves private location and fences old delivery."""

from unittest.mock import patch

from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as Fixture
from wakfu_server import dungeon_instances
from wakfu_server.maps.dungeon_recovery import resume_member


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
        for defect in ("social_missing", "returned", "completed", "closed"):
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
