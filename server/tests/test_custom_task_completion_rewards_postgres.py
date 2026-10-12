"""Hector-authorized retroactive kamas and durable random native gear rewards."""
import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server.custom_tasks import service, reward_delivery, completion_rewards
from wakfu_server.achievements import rewards


class CustomTaskCompletionRewardPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("shepherd-reward-owner", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Shepherd Reward")[
            "id"
        ]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character)
        # Isolated native authority fixture, using real installed equipment IDs.
        refs = [2021, 2025, 2026, 5309, 5310]
        raw = json.dumps(
            {
                "items": [
                    {"reference": ref, "name": "Native gear " + str(ref)}
                    for ref in refs
                ]
            }
        ).encode()
        revision = "a" * 64
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_catalog_releases(revision,document_count,source_bytes,complete) "
                "VALUES (%s,1,%s,true)",
                (revision, len(raw)),
            )
            db.execute(
                "INSERT INTO native_catalog_documents "
                "(revision,path,raw,sha256,source_bytes,record_count) VALUES (%s,%s,%s,%s,%s,5)",
                (
                    revision,
                    "item-equipment-effects.json",
                    raw,
                    hashlib.sha256(raw).hexdigest(),
                    len(raw),
                ),
            )
            db.execute(
                "INSERT INTO native_catalog_active(id,revision) VALUES (1,%s)",
                (revision,),
            )
        self.before = self.store.character(self.account, self.character)["kamas"]

    def earn(self, count=20):
        with self.store.connection() as db:
            for number in range(1, count + 1):
                operation = uuid.UUID(int=number).hex
                service.settle(
                    db,
                    self.account,
                    self.character,
                    "planting:" + operation,
                    {
                        "kind": "monster_seed_planted",
                        "operation_id": operation,
                        "family_ids": [68],
                        "seed_reference": 7361,
                        "resource_reference": 192,
                    },
                )

    def deliver(self):
        return reward_delivery.deliver(
            self.store, self.account, self.generation, self.character
        )

    def test_prior_completion_receives_million_and_one_random_set_piece_exactly_once(
        self,
    ):
        self.earn()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_reward_outbox"
                ).fetchone()["n"],
                0,
            )
        with patch.object(
            completion_rewards.secrets, "choice", return_value=2026
        ) as choose:
            result = self.deliver()
            self.assertEqual(result["character"]["kamas"], self.before + 1_000_000)
            self.assertEqual(
                [item["reference"] for item in result["character"]["inventory_items"]],
                [2026],
            )
            self.assertIn(12753, [opcode for opcode, _ in result["packets"]])
            self.assertEqual(len(result["delivered"]), 2)
            self.assertEqual(self.deliver()["delivered"], [])
            choose.assert_called_once()
        restored = self.reopen().character(self.account, self.character)
        self.assertEqual(restored["kamas"], self.before + 1_000_000)
        self.assertEqual(len(restored["inventory_items"]), 1)

    def test_full_bag_retains_selected_piece_without_reroll_or_repeat_kamas(self):
        self.earn()
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_containers SET capacity=1 WHERE character_id=%s AND kind=0",
                (self.character,),
            )
            rewards.grant(
                db,
                self.store,
                self.store.character(self.account, self.character, db),
                {"aeV": 5, "ckl": [2021, 1]},
            )
        with patch.object(
            completion_rewards.secrets, "choice", return_value=5309
        ) as choose:
            blocked = self.deliver()
            self.assertEqual(blocked["character"]["kamas"], self.before + 1_000_000)
            self.assertEqual(len(blocked["capacity_pending"]), 1)
            self.assertEqual(self.deliver()["delivered"], [])
            with self.store.connection() as db:
                snapshot = db.execute(
                    "SELECT snapshot FROM character_custom_task_policy_rewards"
                ).fetchone()["snapshot"]
                self.assertEqual(snapshot["item_reference"], 5309)
                db.execute(
                    "UPDATE inventory_containers SET capacity=2 WHERE character_id=%s AND kind=0",
                    (self.character,),
                )
            result = self.deliver()
            self.assertEqual(result["character"]["kamas"], self.before + 1_000_000)
            self.assertEqual(
                sorted(
                    item["reference"] for item in result["character"]["inventory_items"]
                ),
                [2021, 5309],
            )
            choose.assert_called_once()

    def test_incomplete_and_missing_native_authority_never_grant(self):
        self.earn(19)
        self.assertEqual(self.deliver()["delivered"], [])
        self.earn(20)
        with self.store.connection() as db:
            db.execute("DELETE FROM native_catalog_active")
        with self.assertRaises(ValueError):
            self.deliver()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_policy_rewards"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_reward_outbox"
                ).fetchone()["n"],
                0,
            )
        self.assertEqual(
            self.store.character(self.account, self.character)["kamas"], self.before
        )

    def test_concurrent_delivery_materializes_and_grants_once(self):
        self.earn()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.deliver(), range(2)))
        self.assertEqual(sum(len(result["delivered"]) for result in results), 2)
        saved = self.store.character(self.account, self.character)
        self.assertEqual(saved["kamas"], self.before + 1_000_000)
        self.assertEqual(len(saved["inventory_items"]), 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_policy_rewards"
                ).fetchone()["n"],
                1,
            )
