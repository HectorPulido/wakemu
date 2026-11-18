"""Real SQL coverage for the atomic Wild Estate 714 -> 723 handoff."""

import json
from pathlib import Path
import struct
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import dungeon_instances, dungeon_runtime_config
from wakfu_server.achievements import storage


ROOT = Path(__file__).resolve().parents[1] / "wakfu_server/maps/owned_story_profiles"


class WildEstateBrakTransferPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.present = json.loads(
            (ROOT / "wild-estate-brak-714.configuration.json").read_text()
        )
        self.past = json.loads(
            (ROOT / "wild-estate-brak-723.configuration.json").read_text()
        )

    def _install_native_definitions(self, db):
        rows = json.loads(
            (
                Path(__file__).parent / "fixtures/native_wild_estate_brak_journal.json"
            ).read_text()
        )
        revision = "b" * 64
        db.execute(
            "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) "
            "VALUES(%s,%s,%s,%s) ON CONFLICT(revision) DO NOTHING",
            (
                revision,
                Jsonb({"fixture": revision}),
                b"wild-estate-brak-focused-test",
                len(rows),
            ),
        )
        for row in rows:
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) "
                "VALUES(%s,%s,%s) ON CONFLICT(revision,definition_id) DO NOTHING",
                (
                    revision,
                    row["quest_id"],
                    Jsonb({"native": row["native_definition"]}),
                ),
            )

    def _install(self, db, config):
        dungeon_runtime_config.install_configuration(db, config)

    def _source_run(self, label):
        account = self.store.register(f"brak-transfer-{label}", "isolated-password")[
            "id"
        ]
        character = self.store.create_character(account, f"Brak Transfer {label}")
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            self._install_native_definitions(db)
            self._install(db, self.present)
            self._install(db, self.past)
            state = storage.load_locked(db, character["id"])
            state["completed"] = [1620]
            state["running"] = [1621, 1622]
            storage.store(db, character["id"], state)
            party_id = db.execute(
                "INSERT INTO player_parties(leader_id,dungeon_solo) VALUES(%s,true) RETURNING id",
                (character["id"],),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (character["id"], party_id),
            )
            run = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,"
                "template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,"
                "start_map_id,context_route_key,context_policy_version) "
                "VALUES(%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING instance_id",
                (
                    party_id,
                    character["id"],
                    self.present["route"]["template_id"],
                    self.present["route"]["definition_id"],
                    self.present["route"]["entry_map_id"],
                    self.present["route"]["entry_object_id"],
                    self.present["route"]["destination_id"],
                    self.present["route"]["start_map_id"],
                    self.present["route"]["key"],
                    self.present["version"],
                ),
            ).fetchone()["instance_id"]
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,"
                "session_generation,party_revision,role) VALUES(%s,%s,%s,%s,1,'leader')",
                (run, party_id, character["id"], generation),
            )
            db.execute(
                "UPDATE characters SET level=50,map_id=714,instance_id=%s,x=10,y=-7,z=0 WHERE id=%s",
                (run, character["id"]),
            )
        return account, generation, character["id"], run, party_id

    def _record_real_inscription(self, account, generation, character_id):
        from wakfu_server import owned_story_controller, owned_story_mechanics

        character = self.store.character(account, character_id)
        with self.store.connection() as db:
            outcome = owned_story_controller.interact(
                db,
                self.store,
                character,
                struct.pack(">qHH", 20539, 0, 0),
                apply_effects=owned_story_mechanics.executor(
                    self.present["topology"]["owned_story_controller"]
                ),
            )
        self.assertTrue(outcome["applied"])
        with self.store.connection() as db:
            self.assertIn(3021, storage.load_locked(db, character_id)["objectives"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=9,y=-3,z=0 WHERE id=%s", (character_id,)
            )

    def test_source_step_and_real_leave_roll_back_on_target_failure_then_commit_once(
        self,
    ):
        from wakfu_server import owned_story_generic_transfer as transfer
        from wakfu_server.maps.dungeon_instances import EntryRoute

        target = self.past["route"]
        route = EntryRoute(
            key=target["key"],
            template_id=target["template_id"],
            definition_id=target["definition_id"],
            entry_map_id=target["entry_map_id"],
            entry_object_id=target["entry_object_id"],
            destination_id=target["destination_id"],
            start_map_id=target["start_map_id"],
            criterion=target["criterion"],
        )
        routes = {route.key: route}
        with patch.object(dungeon_instances, "_ROUTES", routes):
            for label, fail in (("rollback", True), ("commit", False)):
                (
                    account,
                    generation,
                    character_id,
                    source_run,
                    source_party,
                ) = self._source_run(label)
                self._record_real_inscription(account, generation, character_id)
                before = self.store.character(account, character_id)

                def reject_target(*_args, **_kwargs):
                    raise ValueError("forced target admission rejection")

                with self.subTest(fail=fail):
                    if fail:
                        with self.assertRaisesRegex(
                            ValueError, "forced target admission rejection"
                        ):
                            transfer.enter(
                                self.store,
                                account,
                                generation,
                                before,
                                struct.pack(">qHH", 20427, 0, 0),
                                loaded=True,
                                blocked=False,
                                allowed_position_accounts={account},
                                initialize_instance=reject_target,
                            )
                        after = self.store.character(account, character_id)
                        self.assertEqual(after["instance_id"], source_run)
                        with self.store.connection() as db:
                            state = storage.load_locked(db, character_id)
                            self.assertIn(3021, state["objectives"])
                            self.assertEqual(
                                db.execute(
                                    "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                                    (source_run, character_id),
                                ).fetchone()["status"],
                                "active",
                            )
                            self.assertEqual(
                                db.execute(
                                    "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                                    (source_run,),
                                ).fetchone()["status"],
                                "active",
                            )
                            self.assertEqual(
                                db.execute(
                                    "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                                    (source_party,),
                                ).fetchone()["n"],
                                1,
                            )
                    else:
                        result = transfer.enter(
                            self.store,
                            account,
                            generation,
                            before,
                            struct.pack(">qHH", 20427, 0, 0),
                            loaded=True,
                            blocked=False,
                            allowed_position_accounts={account},
                        )
                        after = self.store.character(account, character_id)
                        self.assertGreater(after["instance_id"], 0)
                        self.assertEqual(
                            (after["map_id"], after["x"], after["y"], after["z"]),
                            (723, 9, -3, 0),
                        )
                        with self.store.connection() as db:
                            self.assertEqual(
                                db.execute(
                                    "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                                    (source_run, character_id),
                                ).fetchone()["status"],
                                "returned",
                            )
                            self.assertEqual(
                                db.execute(
                                    "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                                    (source_run,),
                                ).fetchone()["status"],
                                "closed",
                            )
                            self.assertEqual(
                                db.execute(
                                    "SELECT source_instance_id,status FROM dungeon_transition_outbox WHERE instance_id=%s AND character_id=%s AND status='pending'",
                                    (result["instance_id"], character_id),
                                ).fetchone(),
                                {"source_instance_id": source_run, "status": "pending"},
                            )
                            self.assertEqual(
                                db.execute(
                                    "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                                    (source_party,),
                                ).fetchone()["n"],
                                0,
                            )
                            state = storage.load_locked(db, character_id)
                            self.assertIn(3022, state["objectives"])


if __name__ == "__main__":
    import unittest

    unittest.main()
