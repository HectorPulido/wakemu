"""Player embed credentials and durable action receipts are lease-fenced."""
from datetime import datetime, timezone
import hashlib
import secrets
from urllib.parse import urlsplit, parse_qs
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.objectives import player_auth, player_actions, player_views
from wakfu_server import admin_objectives
from wakfu_server.custom_tasks import player_actions as world_actions
from wakfu_server.characters import heroes

TEST_TRAVEL_ACTIONS = [
    {
        "action_key": "travel.map.527",
        "label": "Travel to Astrub",
        "target": {"map_id": 527, "instance_id": 0, "x": 1, "y": 2, "z": 0},
        "objective_key": "content-v1.map.527",
        "cost_kamas": 0,
    }
]


class ObjectivesPlayerPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("player-portal-owner", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Portal Main")["id"]
        self.other = self.store.create_character(self.account, "Portal Other")["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character)
        self.identity = dict(
            account_id=self.account,
            character_id=self.character,
            generation=self.generation,
        )

    def _launch(self):
        with self.store.connection() as db:
            return player_auth.issue_launch(
                db, self.account, self.character, self.generation
            )

    def _queue(self, request_id="req-one"):
        with self.store.connection() as db, patch(
            "wakfu_server.objectives.player_travel.actions",
            return_value=TEST_TRAVEL_ACTIONS,
        ):
            return player_actions.enqueue(
                db, self.identity, "travel.map.527", request_id
            )

    def test_embed_link_is_hash_only_reusable_for_30_days_across_exchanges(self):
        launch = self._launch()
        self.assertEqual(len(launch), 43)
        token_digest = hashlib.sha256(launch.encode("ascii")).hexdigest()
        with self.store.connection() as db:
            row = db.execute(
                "SELECT * FROM objectives_player_tokens WHERE digest=%s",
                (token_digest,),
            ).fetchone()
            seconds = db.execute(
                "SELECT extract(epoch FROM expires_at-CURRENT_TIMESTAMP) AS seconds FROM objectives_player_tokens WHERE digest=%s",
                (token_digest,),
            ).fetchone()["seconds"]
        self.assertEqual(row["kind"], "embed")
        self.assertIsNone(row["consumed_at"])
        self.assertEqual(
            (row["account_id"], row["character_id"], row["generation"]),
            (self.account, self.character, ""),
        )
        self.assertLessEqual(seconds, 30 * 24 * 60 * 60)
        self.assertGreater(seconds, 30 * 24 * 60 * 60 - 30)
        self.assertNotIn(launch, str(row))

        with patch.dict(
            "os.environ",
            {"WAKFU_OBJECTIVES_PUBLIC_URL": "https://game.example/player/"},
        ):
            with self.store.connection() as db:
                link = world_actions.launch_url(
                    db, self.account, self.character, self.generation
                )
        parsed = urlsplit(link)
        params = parse_qs(parsed.fragment)
        self.assertEqual(parsed.query, "")
        self.assertEqual(set(params), {"token"})
        self.assertEqual(len(params["token"][0]), 43)
        self.assertNotIn(params["token"][0], parsed.query)

        with self.store.connection() as db:
            first = player_auth.exchange_launch(db, launch)
            second = player_auth.exchange_launch(db, launch)
            identity = player_auth.authenticate(db, first["token"])
        self.assertEqual(first["character_id"], self.character)
        self.assertEqual(second["character_id"], self.character)
        self.assertNotEqual(first["token"], second["token"])
        self.assertEqual(
            (identity["account_id"], identity["character_id"], identity["generation"]),
            (self.account, self.character, self.generation),
        )
        self.assertEqual(first["expires_at"], second["expires_at"])
        with self.store.connection() as db:
            row = db.execute(
                "SELECT kind,consumed_at FROM objectives_player_tokens WHERE digest=%s",
                (token_digest,),
            ).fetchone()
        self.assertEqual((row["kind"], row["consumed_at"]), ("embed", None))

    def test_legacy_launch_links_remain_single_use_120_seconds_and_lease_fenced(self):
        expired = secrets.token_urlsafe(32)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO objectives_player_tokens(digest,kind,account_id,character_id,generation,expires_at) VALUES(%s,'launch',%s,%s,%s,CURRENT_TIMESTAMP-INTERVAL '1 second')",
                (
                    player_auth.digest(expired),
                    self.account,
                    self.character,
                    self.generation,
                ),
            )
            with self.assertRaises(player_auth.Unauthorized):
                player_auth.exchange_launch(db, expired)

        stale_character = secrets.token_urlsafe(32)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO objectives_player_tokens(digest,kind,account_id,character_id,generation,expires_at) VALUES(%s,'launch',%s,%s,%s,CURRENT_TIMESTAMP+INTERVAL '120 seconds')",
                (
                    player_auth.digest(stale_character),
                    self.account,
                    self.character,
                    self.generation,
                ),
            )
        self.store.select_character(self.account, self.generation, self.other)
        with self.store.connection() as db:
            with self.assertRaisesRegex(
                player_auth.Unauthorized, "Connect this character"
            ):
                player_auth.exchange_launch(db, stale_character)
        new_generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, new_generation, self.character)
        legacy = secrets.token_urlsafe(32)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO objectives_player_tokens(digest,kind,account_id,character_id,generation,expires_at) VALUES(%s,'launch',%s,%s,%s,CURRENT_TIMESTAMP+INTERVAL '120 seconds')",
                (
                    player_auth.digest(legacy),
                    self.account,
                    self.character,
                    new_generation,
                ),
            )
            exchanged = player_auth.exchange_launch(db, legacy)
            session_row = db.execute(
                "SELECT kind,generation,expires_at FROM objectives_player_tokens WHERE digest=%s",
                (player_auth.digest(exchanged["token"]),),
            ).fetchone()
            seconds = db.execute(
                "SELECT extract(epoch FROM %s::timestamptz-CURRENT_TIMESTAMP) seconds",
                (session_row["expires_at"],),
            ).fetchone()["seconds"]
            with self.assertRaisesRegex(player_auth.Unauthorized, "already used"):
                player_auth.exchange_launch(db, legacy)
        self.assertEqual(
            (session_row["kind"], session_row["generation"]),
            ("session", new_generation),
        )
        self.assertGreater(seconds, 29 * 60)
        self.assertLessEqual(seconds, 30 * 60 + 10)

        # Operator privilege does not change the browser token's scope or kind.
        self.generation = new_generation
        self.identity = dict(
            account_id=self.account,
            character_id=self.character,
            generation=new_generation,
        )
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=true WHERE id=%s", (self.account,))
            launch = player_auth.issue_embed(db, self.account, self.character)
            exchanged_embed = player_auth.exchange_launch(db, launch)
            row = db.execute(
                "SELECT kind,account_id,character_id,generation FROM objectives_player_tokens WHERE digest=%s",
                (player_auth.digest(exchanged_embed["token"]),),
            ).fetchone()
        self.assertEqual(
            (row["kind"], row["account_id"], row["character_id"], row["generation"]),
            ("session", self.account, self.character, ""),
        )

    def test_embed_view_tracks_selected_account_character_and_replays_account_request_id(
        self,
    ):
        embed = self._launch()
        with self.store.connection() as db:
            session = player_auth.exchange_launch(db, embed)
        self.store.select_character(self.account, self.generation, self.other)
        with self.store.connection() as db, patch(
            "wakfu_server.objectives.player_travel.actions",
            return_value=TEST_TRAVEL_ACTIONS,
        ):
            identity = player_auth.authenticate(db, session["token"])
            self.assertEqual(identity["character_id"], self.other)
            self.assertEqual(identity["generation"], self.generation)
            view = player_views.snapshot(db, identity)
            self.assertEqual(view["actor"]["id"], self.other)
            self.assertTrue(view["connection"]["online"])

        travel = [
            {
                "action_key": "travel.map.527",
                "label": "Travel to Astrub",
                "target": {"map_id": 527, "instance_id": 0, "x": 1, "y": 2, "z": 0},
                "objective_key": "content-v1.map.527",
                "cost_kamas": 0,
            }
        ]
        with self.store.connection() as db, patch(
            "wakfu_server.objectives.player_travel.actions", return_value=travel
        ):
            # A forged/stale character field in the credential cannot redirect
            # an action away from the account's currently selected World actor.
            stale_identity = {
                **identity,
                "character_id": self.character,
                "generation": "stale",
            }
            action = player_actions.enqueue(
                db, stale_identity, "travel.map.527", "account-global-request"
            )
            replay = player_actions.enqueue(
                db, identity, "travel.map.527", "account-global-request"
            )
            self.assertEqual(replay["id"], action["id"])
            with self.assertRaisesRegex(
                player_actions.ConflictError, "already belongs"
            ):
                player_actions.enqueue(
                    db, identity, "weekly.return", "account-global-request"
                )
            stored = db.execute(
                "SELECT character_id,request_id FROM objectives_player_actions WHERE id=%s",
                (action["id"],),
            ).fetchone()
            self.assertEqual(
                (stored["character_id"], stored["request_id"]),
                (self.other, "account-global-request"),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM objectives_player_actions WHERE account_id=%s AND request_id=%s",
                    (self.account, "account-global-request"),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                player_actions.receipt(db, identity, str(action["id"]))["id"],
                action["id"],
            )
            self.assertEqual(
                player_actions.receipt(db, stale_identity, str(action["id"]))["id"],
                action["id"],
            )

        outsider = self.store.register(
            "player-portal-dynamic-outsider", "local-password"
        )["id"]
        foreign = self.store.create_character(outsider, "Foreign Character")["id"]
        with self.store.connection() as db:
            self.assertIsNone(
                player_actions.receipt(
                    db,
                    {"account_id": outsider, "character_id": foreign},
                    str(action["id"]),
                )
            )

        # Soft-deleting the original link anchor must not invalidate this
        # account token while another owned character remains.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET deleted_at=CURRENT_TIMESTAMP WHERE id=%s",
                (self.character,),
            )
            db.execute(
                "UPDATE sessions SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE account_id=%s",
                (self.account,),
            )
        with self.store.connection() as db, patch(
            "wakfu_server.objectives.player_travel.actions",
            return_value=TEST_TRAVEL_ACTIONS,
        ):
            fallback_identity = player_auth.authenticate(db, session["token"])
            fallback_view = player_views.snapshot(db, fallback_identity)
        self.assertEqual(fallback_identity["character_id"], self.other)
        self.assertIsNone(fallback_identity["generation"])
        self.assertEqual(fallback_view["actor"]["id"], self.other)
        self.assertFalse(fallback_view["connection"]["online"])
        self.assertFalse(fallback_view["connection"]["actions_available"])
        self.assertTrue(all(not item["enabled"] for item in fallback_view["actions"]))

        new_generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, new_generation, self.other)
        with self.store.connection() as db, patch(
            "wakfu_server.objectives.player_travel.actions",
            return_value=TEST_TRAVEL_ACTIONS,
        ):
            identity = player_auth.authenticate(db, session["token"])
            self.assertEqual(identity["generation"], new_generation)
            view = player_views.snapshot(db, identity)
            self.assertTrue(view["connection"]["online"])
            self.assertTrue(view["connection"]["actions_available"])
            action = player_actions.enqueue(
                db, identity, "travel.map.527", "reconnected-action"
            )
            replay = player_actions.enqueue(
                db, identity, "travel.map.527", "reconnected-action"
            )
            self.assertEqual(replay["id"], action["id"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM objectives_player_actions WHERE account_id=%s AND request_id=%s",
                    (self.account, "reconnected-action"),
                ).fetchone()["n"],
                1,
            )
            with self.assertRaisesRegex(
                player_actions.ConflictError, "already belongs"
            ):
                player_actions.enqueue(
                    db, identity, "weekly.return", "reconnected-action"
                )
        with self.store.connection() as db:
            claimed = world_actions.claim(db, identity)
            self.assertEqual(claimed["generation"], new_generation)
            self.assertIsNone(world_actions.lock_running(db, claimed))
            self.assertTrue(
                world_actions.finish(
                    db, claimed, {"success": True, "message": "current lease executed"}
                )
            )
            receipt = player_actions.receipt(db, identity, str(action["id"]))
        self.assertEqual(receipt["status"], "succeeded")

    def test_admin_issued_link_can_be_created_offline_and_is_character_scoped(self):
        self.store.select_character(self.account, self.generation, self.other)
        with patch.dict(
            "os.environ",
            {"WAKFU_OBJECTIVES_PUBLIC_URL": "https://game.example/player/"},
        ):
            issued = admin_objectives.player_launch(self.store, self.character)
        self.assertEqual(set(issued), {"url", "valid_days"})
        self.assertEqual(issued["valid_days"], 30)
        parsed = urlsplit(issued["url"])
        self.assertEqual(parsed.query, "")
        self.assertEqual(parsed.path, "/player/")
        token = parse_qs(parsed.fragment)["token"][0]
        with self.store.connection() as db:
            row = db.execute(
                "SELECT kind,account_id,character_id,generation,expires_at FROM objectives_player_tokens WHERE digest=%s",
                (player_auth.digest(token),),
            ).fetchone()
            seconds = db.execute(
                "SELECT extract(epoch FROM %s::timestamptz-CURRENT_TIMESTAMP) seconds",
                (row["expires_at"],),
            ).fetchone()["seconds"]
        self.assertEqual(
            (row["kind"], row["account_id"], row["character_id"], row["generation"]),
            ("embed", self.account, self.character, ""),
        )
        self.assertLessEqual(seconds, 30 * 24 * 60 * 60)
        self.assertGreater(seconds, 30 * 24 * 60 * 60 - 30)
        outsider = self.store.register("player-portal-foreign", "local-password")["id"]
        foreign_character = self.store.create_character(outsider, "Foreign")["id"]
        with self.assertRaisesRegex(ValueError, "unavailable"):
            admin_objectives.player_launch(self.store, foreign_character + 1)

    def test_action_request_is_idempotent_allowlisted_and_receipt_is_owner_scoped(self):
        with patch(
            "wakfu_server.objectives.player_travel.actions",
            return_value=TEST_TRAVEL_ACTIONS,
        ):
            with self.store.connection() as db:
                first = player_actions.enqueue(
                    db, self.identity, "travel.map.527", "request-1"
                )
                replay = player_actions.enqueue(
                    db, self.identity, "travel.map.527", "request-1"
                )
                with self.assertRaisesRegex(
                    player_actions.ConflictError, "already belongs"
                ):
                    player_actions.enqueue(
                        db, self.identity, "weekly.return", "request-1"
                    )
                with self.assertRaisesRegex(ValueError, "unavailable"):
                    player_actions.enqueue(
                        db, self.identity, "weekly.return", "request-2"
                    )
                snapshot = player_actions.receipt(db, self.identity, str(first["id"]))
                self.assertEqual(snapshot["status"], "pending")
                self.assertNotIn("target", snapshot)
                self.assertNotIn("generation", snapshot)
                self.assertEqual(first["id"], replay["id"])
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) n FROM objectives_player_actions"
                    ).fetchone()["n"],
                    1,
                )

        with self.store.connection() as db:
            outsider = self.store.register("player-portal-outsider", "local-password")[
                "id"
            ]
        outsider_character = self.store.create_character(outsider, "Portal Outsider")[
            "id"
        ]
        outsider_generation = self.store.begin_session(outsider)
        self.store.select_character(outsider, outsider_generation, outsider_character)
        with self.store.connection() as db:
            self.assertIsNone(
                player_actions.receipt(
                    db,
                    dict(
                        account_id=outsider,
                        character_id=outsider_character,
                        generation=outsider_generation,
                    ),
                    str(first["id"]),
                )
            )

    def test_action_claim_ack_expiry_and_pending_limit(self):
        with patch(
            "wakfu_server.objectives.player_travel.actions",
            return_value=TEST_TRAVEL_ACTIONS,
        ):
            with self.store.connection() as db:
                first = player_actions.enqueue(
                    db, self.identity, "travel.map.527", "pending-1"
                )
                receipt = player_actions.receipt(db, self.identity, str(first["id"]))
                self.assertEqual(receipt["status"], "pending")
            with self.store.connection() as db:
                action = world_actions.claim(db, self.identity)
                self.assertEqual(action["status"], "running")
                self.assertIsNone(world_actions.claim(db, self.identity))
                self.assertIsNone(world_actions.lock_running(db, action))
                self.assertTrue(
                    world_actions.finish(
                        db, action, {"success": True, "message": "done"}
                    )
                )
                saved = player_actions.receipt(db, self.identity, str(first["id"]))
                self.assertEqual(
                    (saved["status"], saved["result"]["success"]), ("succeeded", True)
                )

            with self.store.connection() as db:
                pending = [
                    player_actions.enqueue(
                        db, self.identity, "travel.map.527", f"pending-{i}"
                    )
                    for i in range(2, 5)
                ]
                with self.assertRaisesRegex(
                    player_actions.ConflictError, "already pending"
                ):
                    player_actions.enqueue(
                        db, self.identity, "travel.map.527", "pending-overflow"
                    )
                expired_id = pending[0]["id"]
                db.execute(
                    "UPDATE objectives_player_actions SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE id=%s",
                    (expired_id,),
                )
            with self.store.connection() as db:
                expired = player_actions.receipt(db, self.identity, str(expired_id))
                self.assertEqual(expired["status"], "rejected")
                self.assertIn("could not be confirmed", expired["result"]["error"])
            with self.store.connection() as db:
                claimed = world_actions.claim(db, self.identity)
                self.assertIn(claimed["id"], {item["id"] for item in pending[1:]})
                self.assertNotEqual(claimed["id"], expired_id)
                self.assertFalse(
                    world_actions.finish(
                        db, {**claimed, "generation": "stale"}, {"success": True}
                    )
                )
                db.execute(
                    "UPDATE objectives_player_actions SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE id=%s",
                    (claimed["id"],),
                )
                with self.assertRaisesRegex(
                    ValueError, "expired or is no longer executable"
                ):
                    world_actions.lock_running(db, claimed)

    def test_map_transition_compare_and_set_is_atomic_and_keeps_owned_hero_health(self):
        heroes.add(
            self.store, self.account, self.generation, self.character, self.other
        )
        source = self.store.character(self.account, self.character)
        destination = {"map_id": 555001, "instance_id": 0, "x": 7, "y": -4, "z": 1}
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=51,hp_damage=9 WHERE id=ANY(%s)",
                ([self.character, self.other],),
            )
        with self.store.connection() as db:
            result = self.store.transition_map_in_transaction(
                db, self.account, self.generation, self.character, source, destination
            )
            self.assertEqual(result["map_id"], destination["map_id"])
            positions = db.execute(
                "SELECT id,map_id,instance_id,x,y,z,hp FROM characters WHERE id=ANY(%s) ORDER BY id",
                ([self.character, self.other],),
            ).fetchall()
        self.assertEqual(len(positions), 2)
        for row in positions:
            self.assertEqual(
                tuple(row[key] for key in ("map_id", "instance_id", "x", "y", "z")),
                tuple(
                    destination[key] for key in ("map_id", "instance_id", "x", "y", "z")
                ),
            )
            self.assertEqual(row["hp"], 51)

        # An exception after the transition rolls both the main and followers
        # back, which is the same transaction boundary used by action receipts.
        second_source = self.store.character(self.account, self.character)
        rollback_destination = {
            "map_id": 555002,
            "instance_id": 0,
            "x": 8,
            "y": -3,
            "z": 1,
        }
        with self.assertRaisesRegex(RuntimeError, "rollback fixture"):
            with self.store.connection() as db:
                self.store.transition_map_in_transaction(
                    db,
                    self.account,
                    self.generation,
                    self.character,
                    second_source,
                    rollback_destination,
                )
                raise RuntimeError("rollback fixture")
        for character_id in (self.character, self.other):
            saved = self.store.character(self.account, character_id)
            self.assertEqual(
                tuple(saved[key] for key in ("map_id", "instance_id", "x", "y", "z")),
                tuple(
                    destination[key] for key in ("map_id", "instance_id", "x", "y", "z")
                ),
            )

        with self.assertRaisesRegex(ValueError, "desynchronized"):
            self.store.transition_map(
                self.account,
                self.generation,
                self.character,
                source,
                rollback_destination,
            )
        with self.assertRaisesRegex(ValueError, "Invalid map destination"):
            self.store.transition_map(
                self.account,
                self.generation,
                self.character,
                second_source,
                {**rollback_destination, "x": 1.5},
            )


if __name__ == "__main__":
    unittest.main()
