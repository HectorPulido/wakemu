"""Isolated SQL proof for hard-score settlement through native13952 abandon."""

from copy import deepcopy
import json
import os
from pathlib import Path

from psycopg.types.json import Jsonb
from unittest import TestCase

from postgres_case import PostgresCase
from wakfu_server.achievements import mission_toolkit, storage
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server import (
    combat_abandon,
    native_order_trial_admission,
    native_order_trial_checkpoint,
    native_order_trial_encounter,
)
from test_combat_abandon import setup_abandon_state
from test_native_order_trial_checkpoint import prepared_fixture, stage_fixture


ROOT = Path(__file__).resolve().parents[1]
PROFILE = (
    ROOT / "wakfu_server/achievements/mission_profiles/astrub-pizzlarva-score.json"
)
ORDERS = (("blue", "tomato"), ("red", "cheese"), ("green", "pepper"))


def _score_accepted_sidecar(fight, generation):
    """Prepare a typed hard-mode checkpoint with explicit test-only weights."""
    checkpoint = native_order_trial_checkpoint
    from wakfu_server.achievements import native_order_trials as kernel

    prepared_fixture(fight, generation=generation)
    proof, _old_rules, _state = checkpoint.validate(
        fight.native_order_trial, encounter_id=fight.id
    )
    capability = native_order_trial_admission.document()
    capability["enabled"] = True
    delattr(fight, checkpoint.FIELD)
    rules = kernel.OrderRules(
        tuple((recipe, 150) for recipe in sorted(kernel.RECIPES)),
        score_threshold=400,
    )
    state = kernel.start(
        owner_id=proof.owner_id,
        encounter_id=fight.id,
        hard_mode=True,
        orders=ORDERS,
    )
    checkpoint.install(
        fight,
        proof,
        state,
        rules,
        capability=capability,
        provenance={
            "kind": "reviewed_reconstruction",
            "evidence": "isolated test-only score matrix; not recovered native weights",
        },
    )
    for index, (color, ingredient) in enumerate(ORDERS, start=1):
        target = -300 - index
        for action, args in (
            ("spawn", {"target_id": target, "color": color}),
            ("pickup", {"ingredient": ingredient}),
            ("tenderize", {"target_id": target}),
            ("garnish", {"target_id": target}),
            ("bake", {"target_id": target}),
        ):
            stage_fixture(fight, action, **args)
    proof, rules, scored = checkpoint.validate(
        fight.native_order_trial, encounter_id=fight.id
    )
    if not scored.hard_mode or scored.score != 450 or scored.finished:
        raise AssertionError("test sidecar is not an active qualifying hard score")
    policy = native_order_trial_encounter.ConstructorPolicy(
        owner_id=proof.owner_id,
        account_id=proof.account_id,
        instance_id=proof.instance_id,
        encounter_id=fight.id,
        mode="hard",
        source_sha256=proof.source_sha256,
        admission_sha256=proof.profile_sha256,
        map_id=885,
        player_team=1,
        npc_team=0,
    )
    fight.native_order_trial_constructor = policy
    return proof, rules, scored


class NativeOrderTrialAbandonPostgresTests(PostgresCase):
    def test_native_abandon_settles_accepted_hard_score_once_and_defers_hud(self):
        from wakfu_server.achievements import native_order_trial_settlement

        runtime = __import__("wakfu_server.postgres", fromlist=["Database"]).Database(
            os.environ["WAKFU_DATABASE_URL"],
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        self.addCleanup(runtime.close)
        with runtime.connection() as source:
            release = source.execute(
                "SELECT revision,source_sha256,source_export,definition_count "
                "FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1"
            ).fetchone()
            native_row = source.execute(
                "SELECT data FROM native_quest_metadata_definitions "
                "WHERE revision=%s AND definition_id=2149",
                (release["revision"],),
            ).fetchone()
        self.assertIsNotNone(native_row)
        native = native_row["data"]["native"]
        profile = json.loads(PROFILE.read_text())

        (
            store,
            account,
            generation,
            character,
            fight,
            runtime_messages,
        ) = setup_abandon_state(self.store)
        actor = fight.actors[character["id"]]
        actor.team = 1
        fight.placement = {1: {(0, 0, 0)}, 0: {(1, 0, 0)}}
        fight.phase = "active"
        fight.winner = None
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (fight.id,)
            )
            db.execute(
                "UPDATE combat_fight_participants SET team=1 WHERE fight_id=%s AND character_id=%s",
                (fight.id, character["id"]),
            )
            db.execute(
                "UPDATE characters SET level=6,map_id=885,instance_id=99,x=0,y=0,z=0 WHERE id=%s",
                (character["id"],),
            )
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            db.execute(
                "INSERT INTO native_quest_metadata_releases "
                "(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    release["revision"],
                    Jsonb(release["source_sha256"]),
                    release["source_export"],
                    release["definition_count"],
                ),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) "
                "VALUES(%s,2149,%s)",
                (release["revision"], Jsonb(native_row["data"])),
            )
            mission_toolkit.install(db, profile, activate=True)
            accepted = storage.load_locked(db, character["id"])
            accepted["running"] = [2149]
            accepted["active"] = [2149]
            accepted["tracking"] = [2149]
            accepted.setdefault("active_periods", {})
            accepted.setdefault("active_unknown", [])
            storage.store(db, character["id"], accepted)

        character = store.character(account, character["id"])
        proof, _rules, scored = _score_accepted_sidecar(fight, generation)
        self.assertEqual((proof.account_id, proof.owner_id), (account, character["id"]))
        self.assertGreaterEqual(scored.score, 400)
        Checkpoints(store).save(account, generation, fight)
        before_xp = character["xp"]

        result = combat_abandon.prepare(
            store, account, generation, character, runtime_messages, b""
        )
        self.assertTrue(result["applied"])
        self.assertEqual(fight.phase, "finished")
        self.assertEqual(fight.winner, None)
        self.assertEqual(result["packets"][0][0], 12238)
        self.assertTrue(getattr(fight, "post_combat_progression", {}).get(account))
        with store.connection() as db:
            status = db.execute(
                "SELECT f.status,c.status AS checkpoint_status,h.generation "
                "FROM combat_fights f JOIN fight_checkpoints c ON c.fight_id=f.id "
                "JOIN fight_health_exits h ON h.fight_id=f.id AND h.character_id=%s "
                "WHERE f.id=%s",
                (character["id"], fight.id),
            ).fetchone()
            self.assertEqual(
                (status["status"], status["checkpoint_status"], status["generation"]),
                ("aborted", "active", generation),
            )
            settled = storage.load_locked(db, character["id"])
            self.assertIn(2149, settled["completed"])
            self.assertIn(4261, settled["objectives"])
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM character_quest_items WHERE character_id=%s AND reference=12686",
                    (character["id"],),
                ).fetchone()["quantity"],
                8,
            )
            xp_after = store.character(account, character["id"], db)["xp"]
            self.assertGreater(xp_after, before_xp)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND achievement_id=2149",
                    (character["id"],),
                ).fetchone()["n"],
                2,
            )
        deferred = fight.post_combat_progression[account]
        self.assertTrue(deferred[4])
        from wakfu_server.combat_progression_delivery import after_return

        self.assertEqual(
            after_return(fight, account, generation, character["id"]), deferred[4]
        )
        replay = combat_abandon.prepare(
            store, account, generation, character, runtime_messages, b""
        )
        self.assertFalse(replay["applied"])
        self.assertEqual(replay["packets"], [])
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND achievement_id=2149",
                    (character["id"],),
                ).fetchone()["n"],
                2,
            )


class NativeOrderTrialAbandonGuardTests(TestCase):
    @staticmethod
    def _constructor(fight, proof):
        owner = fight.actors[proof.owner_id]
        owner.team = 1
        fight.placement = {
            1: {owner.position},
            0: {
                actor.position
                for actor in fight.actors.values()
                if actor.id != proof.owner_id
            },
        }
        fight.native_order_trial_constructor = (
            native_order_trial_encounter.ConstructorPolicy(
                owner_id=proof.owner_id,
                account_id=proof.account_id,
                instance_id=proof.instance_id,
                encounter_id=fight.id,
                mode=proof.mode,
                source_sha256=proof.source_sha256,
                admission_sha256=proof.profile_sha256,
                map_id=885,
                player_team=1,
                npc_team=0,
            )
        )
        fight.phase = "active"
        fight.winner = None

    def test_below_threshold_normal_and_interrupted_abandons_never_award(self):
        from unittest.mock import patch
        from wakfu_server.achievements.native_order_trial_settlement import (
            stage_abandon,
        )
        from test_native_order_trial_settlement import _finished_fight

        class ReceiptDB:
            def __init__(self, row):
                self.row = row
                self.calls = 0

            def execute(self, _sql, _params=()):
                self.calls += 1
                return self

            def fetchone(self):
                return self.row

        class Store:
            pass

        low, low_proof, low_rule = _finished_fight(
            threshold=500, mode="hard", terminal="withdrawal"
        )
        self._constructor(low, low_proof)
        low_db = ReceiptDB(None)
        with patch(
            "wakfu_server.achievements.native_order_trial_settlement._deliver"
        ) as deliver:
            self.assertEqual(
                stage_abandon(
                    low_db,
                    Store(),
                    low,
                    low_rule,
                    account_id=low_proof.account_id,
                    generation=low_proof.generation,
                    character_id=low_proof.owner_id,
                ),
                {},
            )
        self.assertEqual(low_db.calls, 0)
        deliver.assert_not_called()

        normal, normal_proof, normal_rule = _finished_fight(
            mode="normal", terminal="withdrawal"
        )
        self._constructor(normal, normal_proof)
        normal_db = ReceiptDB(None)
        with patch(
            "wakfu_server.achievements.native_order_trial_settlement._deliver"
        ) as deliver:
            self.assertEqual(
                stage_abandon(
                    normal_db,
                    Store(),
                    normal,
                    normal_rule,
                    account_id=normal_proof.account_id,
                    generation=normal_proof.generation,
                    character_id=normal_proof.owner_id,
                ),
                {},
            )
        self.assertEqual(normal_db.calls, 0)
        deliver.assert_not_called()

        interrupted, proof, rule = _finished_fight(terminal="withdrawal")
        self._constructor(interrupted, proof)
        snapshot = {
            "phase": "aborted",
            "native_order_trial": deepcopy(interrupted.native_order_trial),
        }
        interrupted_db = ReceiptDB(
            {
                "fight_status": "aborted",
                "checkpoint_status": "aborted",
                "snapshot": snapshot,
                "account_id": proof.account_id,
                "session_generation": proof.generation,
                "health_generation": proof.generation,
            }
        )
        with patch(
            "wakfu_server.achievements.native_order_trial_settlement._deliver"
        ) as deliver:
            with self.assertRaisesRegex(
                ValueError, "no accepted score and owned native exit"
            ):
                stage_abandon(
                    interrupted_db,
                    Store(),
                    interrupted,
                    rule,
                    account_id=proof.account_id,
                    generation=proof.generation,
                    character_id=proof.owner_id,
                )
        self.assertEqual(interrupted_db.calls, 1)
        deliver.assert_not_called()
