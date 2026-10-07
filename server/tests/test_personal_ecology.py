import struct
import math
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from postgres_case import PostgresCase
from psycopg.errors import CheckViolation, RaiseException
from wakfu_server import personal_ecology
from wakfu_server.characters.ecology_progression import native_score


class PersonalEcologyTests(PostgresCase):
    def setUp(self):
        super().setUp()
        account = self.store.register("ecology-owner", "test-password")["id"]
        self.character = self.store.create_character(account, "Ecology One")
        self.second_character = self.store.create_character(account, "Ecology Two")
        self.account = account

    def _apply(self, character_id, operation, delta, evidence=None):
        with self.store.connection() as db:
            return personal_ecology.apply(
                db,
                character_id,
                operation=operation,
                delta=delta,
                evidence={"source": operation} if evidence is None else evidence,
            )

    def _state(self, character_id):
        with self.store.connection() as db:
            return db.execute(
                "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s",
                (character_id,),
            ).fetchone()

    def test_basis_points_saturate_and_packets_encode_native_absolute_score(self):
        character_id = self.character["id"]
        positive = self._apply(character_id, "positive", 6000)
        self.assertFalse(positive["duplicate"])
        self.assertEqual(
            (13574, struct.pack(">qi", character_id, native_score(6000))),
            positive["packet"],
        )
        negative = self._apply(character_id, "negative", -9000)
        self.assertEqual(
            (13574, struct.pack(">qi", character_id, native_score(-3000))),
            negative["packet"],
        )
        self.assertEqual(
            {"ecology_value": -3000, "ecology_revision": 2},
            dict(self._state(character_id)),
        )

        self._apply(character_id, "upper-saturate-1", 9900)
        self._apply(character_id, "upper-saturate-2", 9900)
        self.assertEqual(9900, self._state(character_id)["ecology_value"])
        self._apply(character_id, "lower-step", -9900)
        self._apply(character_id, "lower-saturate", -9900)
        self.assertEqual(-9900, self._state(character_id)["ecology_value"])

    def test_native_curve_roundtrip_stays_within_point_zero_seven_percentage_points(
        self,
    ):
        # Native score is integral; reconstructing the UI percentage from its
        # inverse must remain within the native rounding envelope.
        from wakfu_server.characters.ecology_progression import LIMIT

        for basis in range(-LIMIT, LIMIT + 1, 17):
            score = native_score(basis)
            displayed = (
                math.copysign(100 * (1 - 2 ** (-abs(score) / 500)), score)
                if score
                else 0.0
            )
            reconstructed = basis / 100
            self.assertLessEqual(abs(displayed - reconstructed), 0.07)

    def test_same_operation_replays_without_increment_and_reports_current_value(self):
        character_id = self.character["id"]
        evidence = {"kind": "plant", "resource_uid": 27}
        first = self._apply(character_id, "action-a", 7, evidence)
        self.assertEqual(native_score(7), struct.unpack(">qi", first["packet"][1])[1])
        self._apply(character_id, "action-b", -3, {"kind": "harvest"})

        replay = self._apply(character_id, "action-a", 7, evidence)
        self.assertTrue(replay["duplicate"])
        self.assertEqual(native_score(4), struct.unpack(">qi", replay["packet"][1])[1])
        self.assertEqual(
            {"ecology_value": 4, "ecology_revision": 2}, dict(self._state(character_id))
        )

    def test_reused_operation_with_different_delta_or_evidence_is_rejected(self):
        character_id = self.character["id"]
        evidence = {"kind": "plant", "resource_uid": 88}
        self._apply(character_id, "same-op", 4, evidence)
        for delta, changed_evidence in (
            (5, evidence),
            (4, {"kind": "plant", "resource_uid": 89}),
        ):
            with self.subTest(delta=delta, evidence=changed_evidence):
                with self.assertRaisesRegex(ValueError, "reused"):
                    self._apply(character_id, "same-op", delta, changed_evidence)
        self.assertEqual(
            {"ecology_value": 4, "ecology_revision": 1}, dict(self._state(character_id))
        )

    def test_invalid_database_values_and_receipts_are_rejected_by_constraints(self):
        character_id = self.character["id"]
        for value, revision in ((10001, 0), (-10001, 0), (0, -1)):
            with self.subTest(value=value, revision=revision):
                with self.assertRaises(CheckViolation):
                    with self.store.connection() as db:
                        db.execute(
                            "UPDATE characters SET ecology_value=%s,ecology_revision=%s WHERE id=%s",
                            (value, revision, character_id),
                        )
        with self.assertRaises(CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO personal_ecology_receipts(character_id,operation,requested_delta,"
                    "before_value,after_value,revision,evidence) VALUES(%s,'bad',0,0,0,0,'{}')",
                    (character_id,),
                )
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._state(character_id))
        )

    def test_caller_transaction_rolls_back_receipt_and_character_update(self):
        character_id = self.character["id"]
        with self.assertRaisesRegex(RuntimeError, "abort caller transaction"):
            with self.store.connection() as db:
                result = personal_ecology.apply(
                    db,
                    character_id,
                    operation="rolled-back",
                    delta=9,
                    evidence={"kind": "test"},
                )
                self.assertEqual(
                    native_score(9), struct.unpack(">qi", result["packet"][1])[1]
                )
                raise RuntimeError("abort caller transaction")
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._state(character_id))
        )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM personal_ecology_receipts WHERE character_id=%s AND operation='rolled-back'",
                    (character_id,),
                ).fetchone()
            )

    def test_receipt_or_character_update_sql_failure_rolls_back_both_rows(self):
        character_id = self.character["id"]
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_ecology_write() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'forced ecology write failure'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_ecology_receipt BEFORE INSERT ON personal_ecology_receipts "
                "FOR EACH ROW EXECUTE FUNCTION reject_ecology_write()"
            )
        with self.assertRaises(RaiseException):
            self._apply(character_id, "receipt-failure", 12)
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._state(character_id))
        )
        with self.store.connection() as db:
            db.execute(
                "DROP TRIGGER reject_ecology_receipt ON personal_ecology_receipts"
            )
            db.execute(
                "CREATE TRIGGER reject_ecology_character BEFORE UPDATE OF ecology_value "
                "ON characters FOR EACH ROW EXECUTE FUNCTION reject_ecology_write()"
            )
        with self.assertRaises(RaiseException):
            self._apply(character_id, "update-failure", 12)
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._state(character_id))
        )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM personal_ecology_receipts WHERE character_id=%s AND operation='update-failure'",
                    (character_id,),
                ).fetchone()
            )

    def test_concurrent_operations_serialize_without_lost_update(self):
        character_id = self.character["id"]
        barrier = threading.Barrier(2)

        def apply_operation(operation):
            barrier.wait(timeout=10)
            return self._apply(character_id, operation, 1)

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(
                workers.map(apply_operation, ("concurrent-a", "concurrent-b"))
            )
        self.assertEqual(
            {native_score(1), native_score(2)},
            {struct.unpack(">qi", result["packet"][1])[1] for result in results},
        )
        self.assertEqual(
            {"ecology_value": 2, "ecology_revision": 2}, dict(self._state(character_id))
        )

    def test_different_characters_keep_independent_values(self):
        first = self._apply(self.character["id"], "first", 31)
        second = self._apply(self.second_character["id"], "second", -17)
        self.assertEqual(native_score(31), struct.unpack(">qi", first["packet"][1])[1])
        self.assertEqual(
            native_score(-17), struct.unpack(">qi", second["packet"][1])[1]
        )
        self.assertEqual(31, self._state(self.character["id"])["ecology_value"])
        self.assertEqual(-17, self._state(self.second_character["id"])["ecology_value"])


if __name__ == "__main__":
    unittest.main()
