"""Isolated real outbox consumer for scenario facts; terminal earning is separate."""
from postgres_case import PostgresCase
import test_encounter_objective_contract as contracts
from wakfu_server.combat_encounter_objective_facts import objective_result_payload
from wakfu_server.objectives import repository


class EncounterObjectiveConsumerPostgresTests(PostgresCase):
    def test_scenario_fact_exact_filters_retry_progress_and_rollback(self):
        account = self.store.register("scene-objective-owner", "local-password")["id"]
        character = self.store.create_character(account, "Scene Objective")["id"]
        payload = objective_result_payload(
            contracts.EncounterObjectiveContractTests().receipt()
        )
        definition = dict(
            key="test.scene-objective",
            title="Scene objective",
            description="Earn native exit",
            kind="achievement",
            enabled=True,
            objectives=[
                dict(
                    key="exit",
                    event=payload["kind"],
                    filters={
                        k: payload[k]
                        for k in (
                            "objective_key",
                            "outcome_policy",
                            "outcome_version",
                            "reference",
                        )
                    },
                    target=1,
                )
            ],
            schedule=dict(type="once", timezone="UTC"),
            rewards=[],
        )
        with self.store.connection() as db:
            repository.put_definition(db, definition, 0)
        # A rolled-back source transaction cannot leak an event or progression.
        with self.assertRaisesRegex(RuntimeError, "rollback source"):
            with self.store.connection() as db:
                repository.enqueue(db, account, character, "scenario-rollback", payload)
                raise RuntimeError("rollback source")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM objectives_events WHERE event_key=%s",
                    ("scenario-rollback",),
                ).fetchone()["n"],
                0,
            )
            first = repository.enqueue(db, account, character, "scenario-paid", payload)
        self.assertFalse(first["replayed"])
        with self.store.connection() as db:
            result = repository.process_batch(db)
            self.assertEqual((result["processed"], result["failed"]), (1, 0), result)
            progress = repository.list_progress(db, character)
            own = [p for p in progress if p["definition_key"] == definition["key"]]
            self.assertEqual(len(own), 1)
            self.assertEqual(own[0]["counters"], {"exit": 1})
            self.assertIsNotNone(own[0]["completed_at"])
            replay = repository.enqueue(
                db, account, character, "scenario-paid", payload
            )
            self.assertTrue(replay["replayed"])
            self.assertEqual(repository.process_batch(db)["processed"], 0)
            with db.transaction():
                for key in ("reference", "outcome_version"):
                    bad = {**payload, key: payload[key] + 1}
                    repository.enqueue(db, account, character, "wrong-" + key, bad)
            self.assertEqual(repository.process_batch(db)["failed"], 0)
            own = [
                p
                for p in repository.list_progress(db, character)
                if p["definition_key"] == definition["key"]
            ]
            self.assertEqual(own[0]["counters"], {"exit": 1})

    def test_adapter_requires_durable_winner_and_owner_before_real_enqueue(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from unittest.mock import patch
        from psycopg.types.json import Jsonb
        from wakfu_server.combat_encounter_objective_facts import (
            enqueue_objective_results,
        )

        account = self.store.register("scene-adapter-owner", "local-password")["id"]
        character = self.store.create_character(account, "Scene Adapter")["id"]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES ('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES (%s,%s,%s,0)",
                (fight_id, character, account),
            )
            db.execute(
                "INSERT INTO boss_score_encounters(fight_id,snapshot) VALUES (%s,%s)",
                (fight_id, Jsonb({})),
            )
            db.execute(
                "INSERT INTO boss_score_terminal_receipts(fight_id,snapshot,score) VALUES (%s,%s,500)",
                (fight_id, Jsonb({"winning_team": 0})),
            )
        receipt = replace(
            contracts.EncounterObjectiveContractTests().receipt(),
            fight_id=fight_id,
            boundary_actor_id=character,
        )
        player = SimpleNamespace(owner_id=account, pve_withdrawn=False)
        fight = SimpleNamespace(
            id=fight_id,
            phase="finished",
            winner=0,
            native_encounter_objective_policy={},
            native_encounter_objective_results={receipt.policy: receipt.to_record()},
            boss_score_profile={"player_team": 0, "player_ids": [character]},
            actors={character: player},
            _in_play=lambda actor: True,
        )
        # Earning this receipt is independently qualified in the native terminal
        # fixture. This component replaces only that authority check; settlement,
        # membership, durable winner, and all repository operations remain real.
        module = "wakfu_server.combat_encounter_objective_facts"
        with patch(module + ".observe_native_terminal"), patch(
            module + ".verify_scene_terminal_intent", return_value=receipt
        ):
            with self.store.connection() as db:
                result = enqueue_objective_results(db, fight)
                self.assertEqual(len(result), 1)
                self.assertFalse(result[0]["result"]["replayed"])
                replay = enqueue_objective_results(db, fight)
                self.assertTrue(replay[0]["result"]["replayed"])
            fight.winner = 1
            with self.store.connection() as db:
                with self.assertRaises(ValueError):
                    enqueue_objective_results(db, fight)
            fight.winner = 0
            player.owner_id = account + 100000
            with self.store.connection() as db:
                with self.assertRaises(ValueError):
                    enqueue_objective_results(db, fight)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM objectives_events WHERE character_id=%s",
                    (character,),
                ).fetchone()["n"],
                1,
            )
