"""PostgreSQL checks for the proof-gated historical abandon repair."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path
import uuid
import unittest

from postgres_case import PostgresCase
from wakfu_server.combat import combat_historical_abandon_health as historical


class HistoricalAbandonHealthTests(PostgresCase):
    original_fight = 335
    failed_fights = (336, 337, 338)
    boot_id = "historical-proof-test-boot"

    @staticmethod
    def at(hour, minute=0, second=0, microsecond=0):
        return datetime(2026, 10, 17, hour, minute, second, microsecond, timezone.utc)

    @staticmethod
    def dead_state(character_id, maximum):
        return {
            "character": {"id": character_id, "hp": 0, "max_hp": maximum},
            "fight": None,
        }

    def request_rows(
        self,
        records,
        request_id,
        opcode,
        connection_id,
        started_at,
        ended_at,
        *,
        status="completed",
        state_before=None,
        state_after=None,
        rejections=None,
    ):
        common = dict(
            server_boot_id=self.boot_id,
            request_id=request_id,
            connection_id=connection_id,
            request_opcode=opcode,
            account_id=self.account,
            character_id=self.character_id,
        )
        records.append(
            dict(
                common,
                time=started_at.isoformat(),
                event="request_started",
                **({} if state_before is None else {"state_before": state_before}),
            )
        )
        records.append(
            dict(
                common,
                time=ended_at.isoformat(),
                event="request_finished",
                status=status,
                rejections=[]
                if rejections is None and status == "completed"
                else rejections,
                **({} if state_before is None else {"state_before": state_before}),
                **({} if state_after is None else {"state_after": state_after}),
            )
        )

    def selected(self, records, request_id, connection_id, when):
        records.append(
            dict(
                time=when.isoformat(),
                server_boot_id=self.boot_id,
                request_id=request_id,
                connection_id=connection_id,
                event="character_selected",
                account_id=self.account,
                character_id=self.character_id,
            )
        )

    def make_proof(self):
        username = "hab" + uuid.uuid4().hex[:12]
        self.account = self.store.register(username, "test-password")["id"]
        letters = str.maketrans("0123456789", "abcdefghij")
        name = ("H" + uuid.uuid4().hex[:10]).translate(letters)
        character = self.store.create_character(self.account, name)
        self.character_id = character["id"]
        self.maximum = character["max_hp"]
        generation = self.store.begin_session(self.account, ttl=10000)
        self.generation = generation
        self.store.select_character(self.account, generation, self.character_id)
        receipt_at = self.at(12)
        baseline_at = self.at(12, 50, 1)

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=0,hp_damage=max_hp,health_dead=true WHERE id=%s",
                (self.character_id,),
            )
            db.execute(
                "INSERT INTO character_regeneration"
                "(character_id,initial_hp,started_at,coefficient,last_at,initial_damage) "
                "VALUES(%s,0,%s,0,%s,%s)",
                (self.character_id, baseline_at, baseline_at, self.maximum),
            )
            for fight_id in (self.original_fight, *self.failed_fights):
                created = (
                    receipt_at - timedelta(seconds=1)
                    if fight_id == self.original_fight
                    else self.at(13, fight_id - 335)
                )
                db.execute(
                    "INSERT INTO combat_fights(id,status,created_at) OVERRIDING SYSTEM VALUE "
                    "VALUES(%s,'aborted',%s)",
                    (fight_id, created),
                )
                db.execute(
                    "INSERT INTO combat_fight_participants"
                    "(fight_id,character_id,account_id,team,session_generation) "
                    "VALUES(%s,%s,%s,0,%s)",
                    (fight_id, self.character_id, self.account, generation),
                )
            db.execute(
                "INSERT INTO fight_health_exits"
                "(fight_id,character_id,generation,reason,created_at) "
                "VALUES(%s,%s,%s,'abort',%s)",
                (self.original_fight, self.character_id, generation, receipt_at),
            )

        dead = self.dead_state(self.character_id, self.maximum)
        finished = {
            "character": {"id": self.character_id, "hp": 0, "max_hp": self.maximum},
            "fight": {"id": self.original_fight, "phase": "finished"},
        }
        records = []
        original_connection = "connection-original"
        self.selected(records, "select-original", original_connection, self.at(12, 20))
        self.request_rows(
            records,
            "abandon-original",
            13952,
            original_connection,
            self.at(12, 30),
            self.at(12, 30, 1),
        )
        records.append(
            dict(
                time=self.at(12, 30, 1, 500000).isoformat(),
                server_boot_id=self.boot_id,
                request_id="abandon-original",
                connection_id=original_connection,
                event="shared_pve_abandoned_waiting_return",
                actor_id=self.character_id,
                fight_id=self.original_fight,
            )
        )
        self.request_rows(
            records,
            "ack-original",
            12925,
            original_connection,
            self.at(12, 35),
            self.at(12, 35, 1),
            state_before=finished,
            state_after=dead,
        )
        self.request_rows(
            records,
            "move-after-ack",
            13331,
            original_connection,
            self.at(12, 36),
            self.at(12, 36, 1),
            state_before=dead,
            state_after=dead,
        )
        relogin_connection = "connection-relogin"
        self.request_rows(
            records,
            "relogin",
            23664,
            relogin_connection,
            self.at(12, 50),
            self.at(12, 50, 2),
            state_after=dead,
        )
        self.selected(records, "relogin", relogin_connection, self.at(12, 50, 2))

        allocations = []
        for offset, fight_id in enumerate(self.failed_fights):
            connection_id = "connection-failed-" + str(fight_id)
            request_id = "failed-attack-" + str(fight_id)
            start = self.at(13, offset + 1)
            end = start + timedelta(seconds=1)
            selection_id = "selected-" + str(fight_id)
            self.request_rows(
                records,
                selection_id,
                23664,
                connection_id,
                start - timedelta(seconds=10),
                start - timedelta(seconds=2),
                state_after=dead,
            )
            self.selected(
                records, selection_id, connection_id, start - timedelta(seconds=1)
            )
            rejections = [
                {
                    "event": "combat_test_attack_rejected",
                    "reason": "Invalid actor team or resources",
                }
            ]
            self.request_rows(
                records,
                request_id,
                13130,
                connection_id,
                start,
                end,
                status="rejected",
                state_before=dead,
                state_after=dead,
                rejections=rejections,
            )
            records.append(
                dict(
                    time=(start + timedelta(milliseconds=500)).isoformat(),
                    server_boot_id=self.boot_id,
                    request_id=request_id,
                    connection_id=connection_id,
                    event="combat_test_attack_rejected",
                    actor_id=self.character_id,
                    reason="Invalid actor team or resources",
                )
            )
            allocations.append(dict(fight_id=fight_id, request_id=request_id))

        with self.store.connection() as db:
            return historical.prepare(
                db,
                records,
                account_id=self.account,
                character_id=self.character_id,
                fight_id=self.original_fight,
                ack_request_id="ack-original",
                failed_allocations=allocations,
                sources=[dict(name="synthetic-raw-proof.log", sha256="a" * 64)],
            )

    def rows(self):
        with self.store.connection() as db:
            character = dict(
                db.execute(
                    "SELECT id,account_id,hp,max_hp,hp_damage,health_dead FROM characters WHERE id=%s",
                    (self.character_id,),
                ).fetchone()
            )
            regeneration = dict(
                db.execute(
                    "SELECT initial_hp,initial_damage,started_at,coefficient,last_at "
                    "FROM character_regeneration WHERE character_id=%s",
                    (self.character_id,),
                ).fetchone()
            )
            receipt = dict(
                db.execute(
                    "SELECT reason,created_at,return_acknowledged_at,"
                    "abandon_return_acknowledged_at FROM fight_health_exits "
                    "WHERE fight_id=%s AND character_id=%s",
                    (self.original_fight, self.character_id),
                ).fetchone()
            )
        return character, regeneration, receipt

    def test_valid_raw_proof_repairs_one_hp_native_coefficient_and_ack_once(self):
        proof = self.make_proof()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "before.json"
            with self.store.connection() as db:
                result = historical.repair(db, proof, backup=backup)
            character, regeneration, receipt = self.rows()

        self.assertTrue(result["applied"])
        self.assertEqual(character["hp"], 1)
        self.assertEqual(character["hp_damage"], self.maximum - 1)
        self.assertFalse(character["health_dead"])
        self.assertEqual(regeneration["initial_hp"], 1)
        self.assertEqual(
            regeneration["coefficient"], (self.maximum * 4000 + 119999) // 120000
        )
        self.assertEqual(regeneration["started_at"], regeneration["last_at"])
        self.assertEqual(receipt["reason"], "abort")
        self.assertEqual(
            receipt["created_at"].isoformat(), proof["guards"]["exits"][0]["created_at"]
        )
        self.assertEqual(
            receipt["abandon_return_acknowledged_at"].isoformat(), proof["ack_time"]
        )
        self.assertIsNone(receipt["return_acknowledged_at"])
        self.assertEqual(
            historical.qualify(proof, proof["guards"])["fight_id"], self.original_fight
        )

    def test_already_acknowledged_replay_does_not_heal_or_reset_new_regeneration(self):
        proof = self.make_proof()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "before.json"
            with self.store.connection() as db:
                historical.repair(db, proof, backup=backup)
            later = self.at(14)
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET hp=0,hp_damage=max_hp,health_dead=true WHERE id=%s",
                    (self.character_id,),
                )
                db.execute(
                    "UPDATE character_regeneration SET initial_hp=0,started_at=%s,"
                    "coefficient=0,last_at=%s WHERE character_id=%s",
                    (later, later, self.character_id),
                )
            before = self.rows()
            with self.store.connection() as db:
                result = historical.repair(db, proof, backup=backup)
            after = self.rows()

        self.assertFalse(result["applied"])
        self.assertTrue(result["already_acknowledged"])
        self.assertEqual(after, before)

    def test_skip_already_alive_preserves_health_regeneration_and_unacknowledged_receipt(
        self,
    ):
        proof = self.make_proof()
        later = self.at(14)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=37,hp_damage=max_hp-37,health_dead=false WHERE id=%s",
                (self.character_id,),
            )
            db.execute(
                "UPDATE character_regeneration SET initial_hp=29,initial_damage=%s-29,"
                "started_at=%s,coefficient=17,last_at=%s WHERE character_id=%s",
                (self.maximum, later, later, self.character_id),
            )
        before = self.rows()

        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "must-not-exist.json"
            with self.store.connection() as db:
                result = historical.repair(
                    db, proof, backup=backup, skip_already_alive=True
                )
            after = self.rows()

        self.assertEqual(result["outcome"], "already_alive")
        self.assertFalse(result["applied"])
        self.assertFalse(result["ack_written"])
        self.assertFalse(result["health_written"])
        self.assertFalse(result["regeneration_written"])
        self.assertEqual(after, before)
        self.assertIsNone(after[2]["abandon_return_acknowledged_at"])
        self.assertFalse(backup.exists())

    def test_skip_already_alive_rejects_new_fight_history(self):
        proof = self.make_proof()
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=37,hp_damage=max_hp-37,health_dead=false WHERE id=%s",
                (self.character_id,),
            )
            db.execute(
                "INSERT INTO combat_fights(id,status,created_at) OVERRIDING SYSTEM VALUE "
                "VALUES(339,'aborted',%s)",
                (self.at(13, 4),),
            )
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(339,%s,%s,0,%s)",
                (self.character_id, self.account, self.generation),
            )
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "must-not-exist.json"
            with self.assertRaisesRegex(ValueError, "ownership or fight history"):
                with self.store.connection() as db:
                    historical.repair(db, proof, backup=backup, skip_already_alive=True)
            self.assertFalse(backup.exists())

    def test_ack_cas_failure_rolls_back_hp_and_regeneration_update(self):
        proof = self.make_proof()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "before.json"
            before = self.rows()
            with self.assertRaisesRegex(RuntimeError, "ack CAS failure"):
                with self.store.connection() as db:

                    class FailAck:
                        def __init__(self, connection):
                            self.connection = connection
                            self.info = connection.info

                        def execute(self, statement, *args, **kwargs):
                            if statement.startswith(
                                "UPDATE fight_health_exits SET abandon_return_acknowledged_at"
                            ):
                                raise RuntimeError("ack CAS failure")
                            return self.connection.execute(statement, *args, **kwargs)

                    historical.repair(FailAck(db), proof, backup=backup)
            after = self.rows()
            self.assertTrue(backup.is_file())

        self.assertEqual(after, before)

    def test_wrong_owner_actor_fight_and_missing_original_ack_are_rejected(self):
        proof = self.make_proof()
        cases = []
        wrong_owner = deepcopy(proof)
        wrong_owner["account_id"] += 1
        cases.append(wrong_owner)
        wrong_actor = deepcopy(proof)
        wrong_actor["character_id"] += 1
        cases.append(wrong_actor)
        wrong_fight = deepcopy(proof)
        wrong_fight["fight_id"] = self.failed_fights[0]
        cases.append(wrong_fight)
        foreign_proof = deepcopy(proof)
        foreign_proof["guards"]["character"]["account_id"] += 1
        cases.append(foreign_proof)
        missing_ack = deepcopy(proof)
        missing_ack["witness"] = [
            row
            for row in proof["witness"]
            if not (
                row.get("request_id") == proof["ack_request_id"]
                and row.get("event") == "request_finished"
            )
        ]
        cases.append(missing_ack)
        unlisted = deepcopy(proof)
        unlisted["failed_allocations"] = unlisted["failed_allocations"][:-1]
        cases.append(unlisted)
        for candidate in cases:
            with self.subTest(candidate=candidate["fight_id"]):
                with self.assertRaises(ValueError):
                    historical.qualify(candidate, candidate["guards"])

    def test_changed_health_rejects_proof_and_prevents_database_repair(self):
        proof = self.make_proof()
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=1,hp_damage=max_hp-1,health_dead=false WHERE id=%s",
                (self.character_id,),
            )
            changed = historical.capture(db, self.character_id)
        with self.assertRaisesRegex(ValueError, "canonical dead casualty"):
            historical.qualify(proof, changed)
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "must-not-exist.json"
            with self.assertRaisesRegex(ValueError, "proof is stale"):
                with self.store.connection() as db:
                    historical.repair(db, proof, backup=backup)
            self.assertFalse(backup.exists())

    def test_unlisted_later_allocation_and_active_fight_are_rejected(self):
        proof = self.make_proof()
        cases = (
            (339, "aborted", "Unlisted newer fight allocation"),
            (340, "active", "active fight"),
        )
        for fight_id, status, message in cases:
            with self.subTest(status=status):
                with self.store.connection() as db:
                    db.execute(
                        "INSERT INTO combat_fights(id,status,created_at) OVERRIDING SYSTEM VALUE "
                        "VALUES(%s,%s,%s)",
                        (fight_id, status, self.at(13, 4)),
                    )
                    db.execute(
                        "INSERT INTO combat_fight_participants"
                        "(fight_id,character_id,account_id,team,session_generation) "
                        "VALUES(%s,%s,%s,0,%s)",
                        (fight_id, self.character_id, self.account, self.generation),
                    )
                    guards = historical.capture(db, self.character_id)
                with self.assertRaisesRegex(ValueError, message):
                    historical.qualify(proof, guards)
                with self.store.connection() as db:
                    db.execute(
                        "DELETE FROM combat_fight_participants WHERE fight_id=%s",
                        (fight_id,),
                    )
                    db.execute("DELETE FROM combat_fights WHERE id=%s", (fight_id,))

    def test_malformed_return_reason_cannot_replace_abort_receipt(self):
        proof = self.make_proof()
        with self.store.connection() as db:
            db.execute(
                "UPDATE fight_health_exits SET reason='return' WHERE fight_id=%s AND character_id=%s",
                (self.original_fight, self.character_id),
            )
            guards = historical.capture(db, self.character_id)
        with self.assertRaisesRegex(ValueError, "provenance differs"):
            historical.qualify(proof, guards)

    def test_failed_allocations_require_the_original_rejection_and_no_footprints(self):
        proof = self.make_proof()
        failed_request = proof["failed_allocations"][0]["request_id"]
        mutations = (
            lambda records: records.__setitem__(
                slice(None),
                [
                    row
                    for row in records
                    if not (
                        row.get("request_id") == failed_request
                        and row.get("event") == "combat_test_attack_rejected"
                    )
                ],
            ),
            lambda records: next(
                row
                for row in records
                if row.get("request_id") == failed_request
                and row.get("event") == "combat_test_attack_rejected"
            ).__setitem__("reason", "different rejection"),
            lambda records: next(
                row
                for row in records
                if row.get("request_id") == failed_request
                and row.get("event") == "request_started"
            )["state_before"]["character"].__setitem__("hp", 1),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                candidate = deepcopy(proof)
                mutate(candidate["witness"])
                with self.assertRaises(ValueError):
                    historical.qualify(candidate, candidate["guards"])

        with self.store.connection() as db:
            db.execute(
                "INSERT INTO fight_checkpoints"
                "(fight_id,account_id,generation,revision,status,snapshot,updated_at) "
                "VALUES(%s,%s,%s,0,'aborted','{}'::jsonb,%s)",
                (self.failed_fights[0], self.account, self.generation, self.at(13, 4)),
            )
            guards = historical.capture(db, self.character_id)
        with self.assertRaisesRegex(ValueError, "rejected constructor"):
            historical.qualify(proof, guards)

    def test_stale_dead_regeneration_baseline_cannot_create_backup_or_write(self):
        proof = self.make_proof()
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_regeneration SET coefficient=1 WHERE character_id=%s",
                (self.character_id,),
            )
        before = self.rows()
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "must-not-exist.json"
            with self.assertRaisesRegex(ValueError, "proof is stale"):
                with self.store.connection() as db:
                    historical.repair(db, proof, backup=backup)
            after = self.rows()
            self.assertFalse(backup.exists())
        self.assertEqual(after, before)

    def test_later_health_exit_supersedes_the_historical_return(self):
        proof = self.make_proof()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO fight_health_exits(fight_id,character_id,generation,reason,created_at) "
                "VALUES(%s,%s,%s,'return',%s)",
                (
                    self.failed_fights[0],
                    self.character_id,
                    self.generation,
                    self.at(13, 10),
                ),
            )
            guards = historical.capture(db, self.character_id)
        with self.assertRaisesRegex(ValueError, "later health exit superseded"):
            historical.qualify(proof, guards)


if __name__ == "__main__":
    unittest.main()
