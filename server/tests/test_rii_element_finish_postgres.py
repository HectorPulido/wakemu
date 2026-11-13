"""Verify lesson grant cleanup shares the durable fight finish transaction."""
from unittest.mock import patch

from postgres_case import PostgresCase
from tests import test_combat_rewards
from wakfu_server import rii_lesson_grants
from wakfu_server.combat_lifecycle import prepare_finish
from wakfu_server.combat_rewards import Policy
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_spell_grant import granted_spells


class ElementalFinishPostgresTests(PostgresCase):
    def make_finished(self, winning=True):
        (
            store,
            account,
            character,
            generation,
            fight,
        ) = test_combat_rewards.setup_reward_state(self.store)
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (fight.id,)
            )
        fight.phase = "active"
        fight.native_effect_uid_next = 1000
        fight.rii_element_lesson_contract = {"owner": character["id"], "target": -200}
        packets = []
        with patch(
            "wakfu_server.combat_spell_grant.native_spell_references",
            return_value=frozenset(rii_lesson_grants.SPELLS),
        ), patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={
                str(i): {"maximum_level": 200} for i in rii_lesson_grants.SPELLS
            },
        ):
            uids = rii_lesson_grants.install(
                fight,
                character["id"],
                packets,
                action_id=1,
                allocate_uid=fight.allocate_effect_uid,
            )
        fight.rii_element_lesson_contract.update(initialized=True, grant_uids=uids)
        fight.phase, fight.winner = "finished", 0 if winning else 1
        runtime = RuntimeMessages(fight)
        metadata = {
            character["id"]: {
                "kind": "player",
                "account_id": account,
                "name": character["name"],
                "breed": character["breed"],
                "is_male": character["sex"] == 0,
            },
            -200: {"kind": "monster", "ref": 5466},
        }
        return store, account, character, generation, fight, runtime, metadata

    def assert_finish_removes_grants(self, winning):
        (
            store,
            account,
            character,
            generation,
            fight,
            runtime,
            metadata,
        ) = self.make_finished(winning)
        result = prepare_finish(
            store,
            account,
            generation,
            character,
            runtime,
            metadata,
            duration_ms=1000,
            fight_instance_id=7,
            policy=Policy(0, 0),
        )
        self.assertEqual([op for op, _ in result["packets"]].count(13560), 4)
        self.assertFalse(granted_spells(fight, character["id"]))

    def test_win_removes_four_grants(self):
        self.assert_finish_removes_grants(True)

    def test_loss_removes_four_grants(self):
        self.assert_finish_removes_grants(False)

    def test_late_failure_restores_grants_and_durable_fight(self):
        (
            store,
            account,
            character,
            generation,
            fight,
            runtime,
            metadata,
        ) = self.make_finished()
        with patch(
            "wakfu_server.combat_results.finish_messages",
            side_effect=ValueError("late failure"),
        ):
            with self.assertRaisesRegex(ValueError, "late failure"):
                prepare_finish(
                    store,
                    account,
                    generation,
                    character,
                    runtime,
                    metadata,
                    duration_ms=1000,
                    fight_instance_id=7,
                    policy=Policy(0, 0),
                )
        self.assertEqual(
            set(granted_spells(fight, character["id"])), set(rii_lesson_grants.SPELLS)
        )
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "active",
            )
