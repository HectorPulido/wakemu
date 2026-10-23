"""The real terminal settlement keeps consumable outcome and rewards atomic."""
import unittest
from random import Random

from postgres_case import PostgresCase
import test_combat_rewards as reward_fixture
from wakfu_server.combat_lifecycle import prepare_finish
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    server_runtime,
)
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_rewards import Policy
from wakfu_server.paths import DATA_ROOT
from wakfu_server.spells import encode_deck


class CombatConsumableSettlementTests(PostgresCase):
    def setUp(self):
        super().setUp()
        (
            self.store,
            self.account,
            self.character,
            self.generation,
            base,
        ) = reward_fixture.setup_reward_state(self.store)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (base.id,)
            )
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s WHERE fight_id=%s",
                (self.generation, base.id),
            )

        from test_combat_spell_transaction import SpellTransactionTests

        (
            native_character,
            native_monster,
            fight,
        ) = SpellTransactionTests().native_server_fixture(
            self.character["breed"],
            self.character["level"],
            native_qi=True,
        )
        # Rebind the isolated native actor identities to the actual PostgreSQL
        # participant and durable encounter IDs used by prepare_finish.
        player = fight.actors.pop(7)
        player.id = self.character["id"]
        player.owner_id = self.account
        player.state_ledger = StateLedger(player.id)
        player.native_departure_flags["actor_id"] = player.id
        enemy = fight.actors.pop(-7)
        enemy.id = -200
        enemy.state_ledger = StateLedger(enemy.id)
        enemy.native_departure_flags["actor_id"] = enemy.id
        fight.actors[player.id] = player
        fight.actors[enemy.id] = enemy
        fight.order = [
            player.id if uid == 7 else -200 if uid == -7 else uid for uid in fight.order
        ]
        fight.ready_owners = {self.account}
        for row in fight.native_qi_slots:
            if row is not None and row["identity"] == ["actor", 7]:
                row["identity"] = ["actor", player.id]
            elif row is not None and row["identity"] == ["actor", -7]:
                row["identity"] = ["actor", enemy.id]
        # Recreate the fixture's fresh participant registry with the remapped
        # identities; the test is not exercising identity-transfer behavior.
        fight.__dict__.pop("native_global_pv_collections", None)
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.id = base.id

        self.character_native = dict(
            native_character,
            id=self.character["id"],
            account_id=self.account,
            name=self.character["name"],
        )
        self.monsters = {-200: dict(id=-200, ref=5525, map_id=1134)}
        self.deck = encode_deck([], [])
        catalog = __import__("json").loads(
            (DATA_ROOT / "native-consumable-actions.json").read_text()
        )
        plan = next(row["plan"] for row in catalog["items"] if row["item_ref"] == 18351)
        self.character_native["consumable_states"] = [
            dict(
                uid=41_001 + index,
                state_id=state["state_id"],
                level=state["level"],
                clock=state["clock"],
                duration_ms=state["duration_ms"],
                remaining_ms=state["duration_ms"],
                effect_ids=tuple(state["effect_ids"]),
                metadata=state["metadata"],
            )
            for index, state in enumerate(plan["states"])
        ]
        fight, _packets = prepare_server_initialization(
            self.character_native,
            self.monsters,
            fight,
            self.account,
            self.deck,
            action_id=1,
            rng=Random(1),
            fight_start=False,
        )
        fight.phase = "finished"
        fight.winner = 0
        self.fight = fight
        self.runtime = RuntimeMessages(
            fight,
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                self.character_native,
                self.monsters,
                self.deck,
                action_id=action_id,
                critical=False,
            )[0],
        )
        self.metadata = {
            self.character["id"]: dict(
                kind="player",
                account_id=self.account,
                name=self.character["name"],
                breed=self.character["breed"],
                is_male=True,
            ),
            -200: dict(kind="monster", ref=5525),
        }

    def _finish(self, *, loot_resolver=None):
        return prepare_finish(
            self.store,
            self.account,
            self.generation,
            self.character,
            self.runtime,
            self.metadata,
            duration_ms=100,
            fight_instance_id=self.fight.id,
            policy=Policy(0, 0),
            loot_resolver=loot_resolver,
        )

    def test_failed_settlement_rolls_back_outcome_then_retry_applies_once(self):
        character_id = self.character["id"]
        actor = self.fight.actors[character_id]
        before = actor.effect_stats.get(36, 0)
        self.assertEqual(
            1, len(self.fight.native_consumable_initializations[character_id])
        )
        self.assertFalse(
            getattr(self.fight, "native_consumable_outcome_delivered", False)
        )
        self.runtime.action_id = 9
        self.runtime.awaiting_ack = 19
        self.runtime.pending = [(900, b"pending")]
        before_pending = list(self.runtime.pending)

        def fail_after_outcome(db, reward):
            self.assertEqual(
                self.fight.actors[character_id].effect_stats.get(36, 0), before + 40
            )
            self.assertTrue(self.fight.native_consumable_outcome_delivered)
            self.assertTrue(reward["awarded"])
            raise ValueError("injected settlement failure")

        with self.assertRaisesRegex(ValueError, "injected settlement failure"):
            self._finish(loot_resolver=fail_after_outcome)

        self.assertEqual(actor.effect_stats.get(36, 0), before)
        self.assertFalse(
            getattr(self.fight, "native_consumable_outcome_delivered", False)
        )
        self.assertEqual(self.runtime.action_id, 9)
        self.assertEqual(
            (self.runtime.awaiting_ack, self.runtime.pending), (19, before_pending)
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (self.fight.id,)
                ).fetchone()["status"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (self.fight.id,),
                ).fetchone()["n"],
                0,
            )

        def accept_after_retry(db, reward):
            self.assertEqual(
                self.fight.actors[character_id].effect_stats.get(36, 0), before + 40
            )
            self.assertTrue(self.fight.native_consumable_outcome_delivered)
            return {"loots": [], "packets": []}

        result = self._finish(loot_resolver=accept_after_retry)
        self.assertEqual(
            self.fight.actors[character_id].effect_stats.get(36, 0), before + 40
        )
        self.assertTrue(self.fight.native_consumable_outcome_delivered)
        self.assertGreater(self.runtime.action_id, 9)
        self.assertTrue(result["reward"]["awarded"])

        repeated = self._finish(
            loot_resolver=lambda db, reward: {"loots": [], "packets": []}
        )
        self.assertEqual(
            self.fight.actors[character_id].effect_stats.get(36, 0), before + 40
        )
        self.assertFalse(repeated["reward"]["awarded"])


if __name__ == "__main__":
    unittest.main()
