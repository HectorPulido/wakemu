"""Legacy dead return reconciliation uses durable authority, never an HP clamp."""
import copy
import unittest
from datetime import datetime, timezone
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import acknowledged_return_health as recovery


def proof():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    character = dict(
        id=10, account_id=20, hp=0, max_hp=60, hp_damage=60, health_dead=True
    )
    evidence = dict(
        participant=dict(
            fight_id=30,
            status="finished",
            fight_kind="pve",
            team=0,
            session_generation="owned",
            entry_hp=40,
            entry_max_hp=60,
            entry_hp_damage=20,
            entry_health_dead=False,
        ),
        exit=dict(
            fight_id=30,
            reason="return",
            generation="owned",
            created_at=now,
            return_acknowledged_at=now,
        ),
        checkpoint=dict(
            status="ended",
            phase="finished",
            actor=dict(id=10, owner_id=20, hp=0, max_hp=60, team=0, controlled=True),
        ),
        regeneration=dict(
            initial_hp=0, initial_damage=60, coefficient=0, started_at=now, last_at=now
        ),
        tails=[],
        active=None,
    )
    return character, evidence


class ReturnEligibilityTests(unittest.TestCase):
    def test_generic_character_and_fight_ids_are_eligible(self):
        character, evidence = proof()
        self.assertTrue(recovery.eligible(character, 60, evidence))

    def test_zero_entry_failed_admission_is_not_a_new_real_fight(self):
        character, evidence = proof()
        evidence["tails"] = [
            dict(
                status="aborted",
                fight_kind="pve",
                entry_hp=0,
                entry_max_hp=60,
                entry_hp_damage=60,
                entry_health_dead=True,
                health_exit=False,
                reward=False,
                checkpoint=False,
            )
        ]
        self.assertTrue(recovery.eligible(character, 60, evidence))
        for name in ("health_exit", "reward", "checkpoint"):
            changed = copy.deepcopy(evidence)
            changed["tails"][0][name] = True
            self.assertFalse(recovery.eligible(character, 60, changed))

    def test_unacknowledged_abort_active_and_changed_wounds_are_not_recovered(self):
        character, evidence = proof()
        for target, name, value in (
            ("exit", "reason", "abort"),
            ("exit", "return_acknowledged_at", None),
            ("participant", "status", "active"),
            ("regeneration", "coefficient", 2),
        ):
            changed = copy.deepcopy(evidence)
            changed[target][name] = value
            self.assertFalse(recovery.eligible(character, 60, changed))
        self.assertFalse(recovery.eligible(dict(character, hp_damage=61), 60, evidence))
        self.assertFalse(recovery.eligible(character, 70, evidence))
        self.assertFalse(
            recovery.eligible(character, 60, dict(evidence, active={"fight_id": 31}))
        )


class ReturnSelectionTests(PostgresCase):
    def state(self):
        store = self.store
        account = store.register("return-reconcile", "local-password")["id"]
        character = store.create_character(account, "Return Legacy")
        generation = store.begin_session(account)
        store.select_character(account, generation, character["id"])
        now = store.now()
        with store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,"
                "session_generation,entry_hp,entry_max_hp,entry_hp_damage,entry_health_dead) "
                "VALUES(%s,%s,%s,0,%s,40,60,20,false)",
                (fight, character["id"], account, generation),
            )
            db.execute(
                "INSERT INTO fight_health_exits(fight_id,character_id,generation,reason,created_at,return_acknowledged_at) "
                "VALUES(%s,%s,%s,'return',%s,%s)",
                (fight, character["id"], generation, now, now),
            )
            actor = dict(
                id=character["id"],
                owner_id=account,
                controlled=True,
                team=0,
                hp=0,
                max_hp=60,
            )
            db.execute(
                "INSERT INTO fight_checkpoints(fight_id,account_id,generation,revision,status,snapshot,updated_at) "
                "VALUES(%s,%s,%s,1,'ended',%s,%s)",
                (
                    fight,
                    account,
                    generation,
                    Jsonb(
                        dict(
                            id=fight,
                            phase="finished",
                            actors={str(character["id"]): actor},
                        )
                    ),
                    now,
                ),
            )
            db.execute(
                "UPDATE characters SET hp=0,hp_damage=60,health_dead=true WHERE id=%s",
                (character["id"],),
            )
            db.execute(
                "INSERT INTO character_regeneration(character_id,initial_hp,started_at,last_at,coefficient) "
                "VALUES(%s,0,%s,%s,0) ON CONFLICT(character_id) DO UPDATE SET "
                "initial_hp=excluded.initial_hp,started_at=excluded.started_at,"
                "last_at=excluded.last_at,coefficient=0",
                (character["id"], now, now),
            )
        return store, account, generation, character, fight

    def test_owned_selection_recovers_once_and_starts_normal_regeneration(self):
        from wakfu_server import health_store

        store, account, generation, character, fight = self.state()
        before = store.character(account, character["id"])
        result = health_store.initialize(
            store, account, generation, character["id"], exploration=True
        )
        self.assertEqual(
            (result["hp"], result["hp_damage"], result["health_dead"]), (1, 59, False)
        )
        for key in (
            "x",
            "y",
            "z",
            "direction",
            "level",
            "xp",
            "kamas",
            "inventory_items",
            "builds",
        ):
            self.assertEqual(result[key], before[key])
        with store.connection() as db:
            regen = db.execute(
                "SELECT * FROM character_regeneration WHERE character_id=%s",
                (character["id"],),
            ).fetchone()
            self.assertEqual(
                (regen["initial_hp"], regen["initial_damage"], regen["coefficient"]),
                (1, 59, 2),
            )
            audit = db.execute(
                "SELECT count(*) AS n FROM admin_panel_audit WHERE action=%s",
                (recovery.AUDIT_ACTION,),
            ).fetchone()
            self.assertEqual(audit["n"], 1)
        second = health_store.initialize(
            store, account, generation, character["id"], exploration=True
        )
        self.assertEqual(second["hp"], 1)

    def test_live_reconnect_never_reconciles_exploration_health(self):
        from wakfu_server import health_store

        store, account, generation, character, _ = self.state()
        result = health_store.initialize(
            store, account, generation, character["id"], exploration=False
        )
        self.assertEqual((result["hp"], result["health_dead"]), (0, True))

    def test_existing_reconciliation_receipt_does_not_heal_a_later_death(self):
        from wakfu_server import health_store

        store, account, generation, character, _ = self.state()
        health_store.initialize(
            store, account, generation, character["id"], exploration=True
        )
        now = store.now()
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=0,hp_damage=60,health_dead=true WHERE id=%s",
                (character["id"],),
            )
            db.execute(
                "UPDATE character_regeneration SET initial_hp=0,started_at=%s,last_at=%s,coefficient=0 WHERE character_id=%s",
                (now, now, character["id"]),
            )
        result = health_store.initialize(
            store, account, generation, character["id"], exploration=True
        )
        self.assertEqual((result["hp"], result["health_dead"]), (0, True))

    def test_failed_health_initialization_rolls_back_reconciliation_and_audit(self):
        from unittest.mock import patch
        from wakfu_server import health_store

        store, account, generation, character, _ = self.state()
        with patch(
            "wakfu_server.health_policy.reconfigure",
            side_effect=RuntimeError("failed initialization"),
        ):
            with self.assertRaises(RuntimeError):
                health_store.initialize(
                    store, account, generation, character["id"], exploration=True
                )
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        with store.connection() as db:
            count = db.execute(
                "SELECT count(*) AS n FROM admin_panel_audit WHERE action=%s",
                (recovery.AUDIT_ACTION,),
            ).fetchone()["n"]
            self.assertEqual(count, 0)

    def test_stale_lease_does_not_recover_health(self):
        from wakfu_server import health_store

        store, account, generation, character, _ = self.state()
        store.begin_session(account)
        with self.assertRaises(ValueError):
            health_store.initialize(
                store, account, generation, character["id"], exploration=True
            )
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
