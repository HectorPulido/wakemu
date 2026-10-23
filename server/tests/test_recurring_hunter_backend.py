"""One isolated compound backend qualification; no World acceptance authority claim."""
from datetime import datetime, timezone, timedelta
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from psycopg import DatabaseError
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from test_guild_service_postgres import GuildServicePostgresTests
from wakfu_server.achievements import storage, service
from wakfu_server.objectives import environmental_recurring_storage as recurring


class RecurringHunterBackendTests(PostgresCase):
    _player = GuildServicePostgresTests._player

    def setUp(self):
        super().setUp()
        with self.store.connection() as db:
            if (
                db.execute(
                    "SELECT to_regclass('recurring_hunter_contracts') AS found"
                ).fetchone()["found"]
                is None
            ):
                db.execute(
                    Path(
                        "server/migrations/287_environmental_recurring_contracts.sql"
                    ).read_text()
                )
        self.owner = self._player("Hunter Owner")
        self.foreign = self._player("Other Hunter")
        self.character = self.store.character(
            self.owner["account"], self.owner["character"]
        )
        with self.store.connection() as db:
            rule = db.execute(
                "SELECT version,minimum_level FROM recurring_hunter_contracts "
                "WHERE definition_id=3766 ORDER BY version DESC LIMIT 1"
            ).fetchone()
            self.version, self.level = rule["version"], rule["minimum_level"]
            # Eligibility fixture uses the native version's real-level minimum;
            # it does not manufacture combat stats or acceptance authority.
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s",
                (self.level, self.character["id"]),
            )

    def receipt(self, db, key, *, timestamp=None):
        storage.record_event(
            db,
            self.character["id"],
            key,
            dict(
                kind="native_recurring_acceptance",
                definition_id=3766,
                real_level=self.level,
                source_kind="npc_dialogue",
                source_reference=777,
                action_id=888,
            ),
        )
        if timestamp is not None:
            db.execute(
                "UPDATE character_achievement_events SET created_at=%s WHERE character_id=%s AND event_key=%s",
                (timestamp, self.character["id"], key),
            )

    def fight(self, db, references, *, bosses=True):
        identity = db.execute(
            "INSERT INTO combat_fights(status,fight_kind) VALUES('finished','pve') RETURNING id"
        ).fetchone()["id"]
        db.execute(
            "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
            (identity, self.character["id"], self.character["account_id"]),
        )
        if not hasattr(self, "party"):
            self.party = db.execute(
                "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING id",
                (self.character["id"],),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (self.character["id"], self.party),
            )
        party = self.party
        db.execute(
            "UPDATE dungeon_instance_members SET status='returned',ended_at=CURRENT_TIMESTAMP "
            "WHERE character_id=%s AND status='active'",
            (self.character["id"],),
        )
        # Match dungeon recovery/exit: an empty prior run is closed only
        # after its last active member has durably returned.
        db.execute(
            "UPDATE dungeon_instances i SET status='closed',ended_at=CURRENT_TIMESTAMP "
            "WHERE i.party_id=%s AND i.status IN ('active','completed') AND NOT EXISTS "
            "(SELECT 1 FROM dungeon_instance_members m WHERE m.instance_id=i.instance_id "
            "AND m.status='active')",
            (party,),
        )
        instance = db.execute(
            "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id) VALUES(%s,1,%s,1,1,1134,1,1,1134) RETURNING instance_id",
            (party, self.character["id"]),
        ).fetchone()["instance_id"]
        db.execute(
            "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) VALUES(%s,%s,%s,%s,1,'leader')",
            (instance, party, self.character["id"], self.owner["generation"]),
        )
        rooms = [
            dict(
                order=1,
                monsters=[
                    dict(ref_id=r, role="boss" if bosses else "monster")
                    for r in references
                ],
            )
        ]
        db.execute(
            "INSERT INTO dungeon_room_runs(instance_id,party_id,catalog_hash,rooms,status) VALUES(%s,%s,%s,%s,'completed')",
            (instance, party, "a" * 64, Jsonb(rooms)),
        )
        db.execute(
            "INSERT INTO dungeon_room_encounters(fight_id,instance_id,room_order,player_team,status,result_revision,result) VALUES(%s,%s,1,0,'victory',1,%s)",
            (identity, instance, Jsonb(dict(completed=True))),
        )
        actors = {
            self.character["id"]: SimpleNamespace(
                controlled=True, owner_id=self.character["account_id"], team=0, hp=1
            )
        }
        original = []
        for i, reference in enumerate(references):
            actors[-i - 1] = SimpleNamespace(controlled=False, team=1, hp=0)
            original.append(dict(id=-i - 1, ref=reference))
        fight = SimpleNamespace(
            id=identity,
            phase="finished",
            winner=0,
            actors=actors,
            native_summon_registrations={},
        )
        event = service._event(db, self.character, fight, original)
        storage.record_event(db, self.character["id"], "fight:" + str(identity), event)
        return fight, event

    def test_source_gated_acceptance_multi_boss_receipt_period_reward_and_rollback(
        self,
    ):
        with self.store.connection() as db, patch.object(
            recurring, "drain_rewards", return_value=[]
        ):
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(DISTINCT definition_id) AS n FROM recurring_hunter_contracts WHERE period_ms=604800000"
                ).fetchone()["n"],
                16,
            )
            from wakfu_server.objectives.environmental_recurring_offers import (
                compile_hunter_offers,
            )

            native_path = (
                Path(__file__).resolve().parents[1] / "protocol/npc-dialogues.json.gz"
            )
            with gzip.open(native_path, "rt") as stream:
                nodes = json.load(stream)["nodes"]
            rows = db.execute(
                "SELECT o.*,c.minimum_level AS contract_minimum "
                "FROM recurring_hunter_native_offers o JOIN recurring_hunter_contracts c "
                "USING(definition_id,version) ORDER BY o.definition_id"
            ).fetchall()
            self.assertEqual(len(rows), 16)
            offers = compile_hunter_offers(nodes, {r["definition_id"] for r in rows})
            for r in rows:
                original = offers[r["definition_id"]]
                self.assertEqual(
                    (
                        r["node_id"],
                        r["choice_id"],
                        r["minimum_level"],
                        r["category_id"],
                        r["criterion"],
                    ),
                    (
                        original.node_id,
                        original.choice_id,
                        original.minimum_level,
                        original.category_id,
                        original.criterion,
                    ),
                )
                self.assertEqual(
                    (r["version"], r["contract_minimum"]), (2, original.minimum_level)
                )
            self.assertEqual(
                sorted(r["minimum_level"] for r in rows), list(range(6, 232, 15))
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS n FROM recurring_hunter_acceptance_sources"
                ).fetchone()["n"],
                0,
            )
            self.receipt(db, "accept:first")
            with self.assertRaisesRegex(ValueError, "not been recovered"):
                recurring.accept_from_receipt(
                    db, self.store, self.character, 3766, receipt_key="accept:first"
                )
            # A test-only source binding exercises the generic backend; it does
            # not recover or activate any real hunter NPC dialogue action.
            db.execute(
                "INSERT INTO recurring_hunter_acceptance_sources VALUES(3766,%s,'npc_dialogue',777,888,'isolated-test-only-authority')",
                (self.version,),
            )
            other = self.store.character(
                self.foreign["account"], self.foreign["character"], db
            )
            with self.assertRaisesRegex(ValueError, "Missing durable owned"):
                recurring.accept_from_receipt(
                    db, self.store, other, 3766, receipt_key="accept:first"
                )
            with self.assertRaisesRegex(RuntimeError, "rollback"):
                with db.transaction():
                    self.assertTrue(
                        recurring.accept_from_receipt(
                            db,
                            self.store,
                            self.character,
                            3766,
                            receipt_key="accept:first",
                        )["applied"]
                    )
                    raise RuntimeError("rollback")
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS n FROM recurring_hunter_acceptances"
                ).fetchone()["n"],
                0,
            )
            accepted = recurring.accept_from_receipt(
                db, self.store, self.character, 3766, receipt_key="accept:first"
            )
            self.assertTrue(accepted["applied"])
            self.assertEqual([p[0] for p in accepted["packets"]], [13312])
            self.assertFalse(
                recurring.accept_from_receipt(
                    db, self.store, self.character, 3766, receipt_key="accept:first"
                )["applied"]
            )
            fight, event = self.fight(db, [1259, 2157])
            self.assertEqual(
                len(
                    recurring.settle_combat(
                        db, self.store, self.character, fight, event
                    )["credited"]
                ),
                2,
            )
            self.assertEqual(
                recurring.settle_combat(db, self.store, self.character, fight, event)[
                    "credited"
                ],
                [],
            )
            fight, event = self.fight(db, [1259])
            self.assertEqual(
                recurring.settle_combat(db, self.store, self.character, fight, event)[
                    "completed"
                ],
                [],
            )
            fight, event = self.fight(db, [4012], bosses=False)
            self.assertEqual(
                recurring.settle_combat(db, self.store, self.character, fight, event)[
                    "credited"
                ],
                [],
            )
            fight, event = self.fight(db, [44])
            self.assertEqual(
                recurring.settle_combat(db, self.store, self.character, fight, event)[
                    "completed"
                ],
                [3766],
            )
            self.assertEqual(
                recurring.settle_combat(db, self.store, self.character, fight, event)[
                    "completed"
                ],
                [],
            )
            pending = storage.pending_rewards(db, self.character["id"])
            self.assertEqual(len(pending), 2)
            self.assertEqual(
                sorted((r["payload"]["aeV"], r["payload"]["ckl"]) for r in pending),
                [(5, [12686, 80]), (6, [103099])],
            )
            _, contract, _ = recurring._load(db, 3766)
            next_ms = (
                contract.anchor_ms
                + (accepted["period"] + 1) * contract.period_ms
                + 1000
            )
            next_date = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
                milliseconds=next_ms
            )
            with patch.object(recurring, "_now", return_value=next_ms):
                self.assertIn(
                    13205,
                    [
                        p[0]
                        for p in recurring.synchronize(db, self.store, self.character)
                    ],
                )
                self.assertNotIn(
                    3766, storage.load_locked(db, self.character["id"])["completed"]
                )
                self.assertEqual(
                    len(storage.pending_rewards(db, self.character["id"])), 2
                )
                self.receipt(db, "accept:next", timestamp=next_date)
                self.assertTrue(
                    recurring.accept_from_receipt(
                        db, self.store, self.character, 3766, receipt_key="accept:next"
                    )["applied"]
                )
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS n FROM recurring_hunter_acceptances"
                    ).fetchone()["n"],
                    2,
                )
            with self.assertRaises(DatabaseError):
                with db.transaction():
                    db.execute(
                        "UPDATE recurring_hunter_contracts SET minimum_level=2 WHERE definition_id=3766"
                    )
