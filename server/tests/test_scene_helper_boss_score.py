"""Declared helper score attribution and real PostgreSQL receipt compatibility.

The runtime controller proof producer is tested separately. These tests keep
the real frozen-proof validator, staging, persistence and replay arithmetic.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.maps import boss_score, boss_score_runtime
from wakfu_server.combat_encounter_scene_helpers import SCHEMA, SPIRIT_POLICY
from wakfu_server.combat_quest_scene_authority import canonical_digest


def fixture(fight_id=77, owner=7, account=3):
    source = dict(
        schema=SCHEMA,
        version=1,
        policy=SPIRIT_POLICY,
        authority="explicit_source_backed_wakemu_reconstruction",
        map_id=1134,
        originals=[dict(id=-200, reference=5848)],
        helpers=[
            dict(
                actor_id=-201,
                reference=5849,
                level=110,
                team_role="player",
                controller_role="principal",
            ),
            dict(
                actor_id=-202,
                reference=5850,
                level=110,
                team_role="player",
                controller_role="principal",
            ),
        ],
    )
    manifest = dict(source=source, source_digest=canonical_digest(source))
    scope = dict(
        fight_id=fight_id,
        manifest=manifest,
        ready_digest="a" * 64,
        ready_owners={str(owner): account},
        catalog_revision="b" * 64,
        births={"-201": "c" * 64, "-202": "d" * 64},
    )
    profile = dict(
        policy=boss_score.POLICY,
        bosses={"-200": dict(reference=5848)},
        player_ids=[owner],
        player_team=0,
        round_limit=13,
        scene_helper_score_scope=scope,
    )
    proof = dict(
        schema="wakemu.scene-helper-score-owner.v1",
        source="declared_initial_scene_npc.current_human_controller.v1",
        owner_actor_id=owner,
        current_controller_id=owner,
        account_id=account,
        native_birth_digest="c" * 64,
        actor_id=-201,
        reference=5849,
        descriptor_level=110,
        source_policy=SPIRIT_POLICY,
        source_digest=manifest["source_digest"],
        fight_id=fight_id,
        map_id=1134,
        catalog_revision="b" * 64,
        ready_digest="a" * 64,
    )
    actors = {
        owner: SimpleNamespace(id=owner, team=0),
        -201: SimpleNamespace(id=-201, team=0),
        -200: SimpleNamespace(id=-200, team=1),
    }
    fight = SimpleNamespace(
        id=fight_id,
        actors=actors,
        boss_score_profile=profile,
        boss_score_events={},
        native_timeline_round=1,
    )
    return fight, proof


class SceneHelperScoreStagingTests(unittest.TestCase):
    def stage(self, fight, proof):
        with patch(
            "wakfu_server.combat_encounter_scene_helpers.helper_score_owner_receipt",
            return_value=proof,
        ):
            boss_score_runtime.stage_damage(
                fight,
                action_id=5,
                runner_uid=9,
                source=fight.actors[-201],
                target=fight.actors[-200],
                result=dict(
                    hp_requested=100, virtual_hp_absorbed=30, armor_absorbed=20
                ),
            )

    def test_helper_contributes_actual_paid_damage_once_without_summon_impersonation(
        self,
    ):
        fight, proof = fixture()
        self.stage(fight, proof)
        self.stage(fight, proof)
        self.assertEqual(len(fight.boss_score_events), 1)
        self.assertEqual(boss_score_runtime.staged_score(fight), 150)
        row = next(iter(fight.boss_score_events.values()))
        self.assertFalse(row["source_is_registered_summon"])
        self.assertEqual(row["source_scene_helper"], proof)
        self.assertEqual(row["owner_actor_id"], 7)
        with patch.object(
            boss_score_runtime.boss_score, "freeze_snapshot"
        ), patch.object(boss_score_runtime.boss_score, "record_damage") as record:
            boss_score_runtime.persist(object(), fight)
        self.assertEqual(record.call_args.kwargs["source_scene_helper"], proof)
        self.assertFalse(record.call_args.kwargs["source_is_registered_summon"])

    def test_foreign_controller_or_changed_source_cannot_credit_helper_damage(self):
        for field, value in (
            ("owner_actor_id", 99),
            ("current_controller_id", 99),
            ("account_id", 99),
            ("native_birth_digest", "f" * 64),
            ("source_digest", "f" * 64),
            ("ready_digest", "f" * 64),
        ):
            fight, proof = fixture()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.stage(fight, {**proof, field: value})
            self.assertEqual(fight.boss_score_events, {})
        fight, _ = fixture()
        self.stage(fight, None)  # Runtime denied actual controller ownership.
        self.assertEqual(fight.boss_score_events, {})

    def test_enemy_team_and_old_player_events_retain_existing_shape(self):
        fight, proof = fixture()
        fight.actors[-201].team = 1
        self.stage(fight, proof)
        self.assertEqual(fight.boss_score_events, {})
        boss_score_runtime.stage_damage(
            fight,
            action_id=6,
            runner_uid=10,
            source=fight.actors[7],
            target=fight.actors[-200],
            result=dict(hp_requested=10, virtual_hp_absorbed=0, armor_absorbed=0),
        )
        row = next(iter(fight.boss_score_events.values()))
        self.assertNotIn("source_scene_helper", row)
        self.assertEqual(boss_score_runtime.staged_score(fight), 10)


class SceneHelperScorePostgresTests(PostgresCase):
    def make(self):
        account = self.store.register("scene-score-owner", "local-password")["id"]
        owner = self.store.create_character(account, "SceneScoreOwner")["id"]
        with self.store.connection() as db:
            identity = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            fight, proof = fixture(identity, owner, account)
            boss_score.freeze_snapshot(db, identity, fight.boss_score_profile)
        return fight, proof

    def record(self, db, fight, proof, *, event="helper:5:9", source=-201):
        return boss_score.record_damage(
            db,
            fight.id,
            event_id=event,
            source_id=source,
            target_id=-200,
            owner_actor_id=fight.boss_score_profile["player_ids"][0],
            post_mitigation_damage=130,
            armor_absorbed=20,
            round_number=1,
            source_is_registered_summon=False,
            source_scene_helper=proof,
        )

    def test_real_receipt_deduplication_and_old_payload_compatibility(self):
        fight, proof = self.make()
        with self.store.connection() as db:
            self.assertTrue(self.record(db, fight, proof))
            self.assertTrue(self.record(db, fight, deepcopy(proof)))
            row = db.execute(
                "SELECT snapshot,amount FROM boss_score_damage_receipts WHERE fight_id=%s",
                (fight.id,),
            ).fetchone()
            self.assertEqual(row["amount"], 150)
            self.assertFalse(row["snapshot"]["registered_summon"])
            self.assertEqual(row["snapshot"]["scene_helper"], proof)
            owner = fight.boss_score_profile["player_ids"][0]
            self.assertTrue(
                self.record(db, fight, None, event="old-player", source=owner)
            )
            old = db.execute(
                "SELECT snapshot FROM boss_score_damage_receipts WHERE fight_id=%s AND event_id='old-player'",
                (fight.id,),
            ).fetchone()["snapshot"]
            self.assertNotIn("scene_helper", old)
            self.assertEqual(
                set(old),
                {
                    "source_id",
                    "target_id",
                    "owner_actor_id",
                    "damage",
                    "armor",
                    "round_number",
                    "registered_summon",
                },
            )
            total = db.execute(
                "SELECT count(*) AS n,sum(amount) AS amount FROM boss_score_damage_receipts WHERE fight_id=%s",
                (fight.id,),
            ).fetchone()
            self.assertEqual((total["n"], total["amount"]), (2, 300))

    def test_forged_helper_proof_or_rollback_never_publishes_damage(self):
        fight, proof = self.make()
        with self.assertRaisesRegex(
            RuntimeError, "discard"
        ), self.store.connection() as db:
            self.record(db, fight, proof)
            raise RuntimeError("discard")
        with self.store.connection() as db:
            for field, value in (
                ("current_controller_id", 99),
                ("account_id", 99),
                ("source_digest", "f" * 64),
            ):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    self.record(db, fight, {**proof, field: value})
            count = db.execute(
                "SELECT count(*) AS n FROM boss_score_damage_receipts WHERE fight_id=%s",
                (fight.id,),
            ).fetchone()["n"]
            self.assertEqual(count, 0)
