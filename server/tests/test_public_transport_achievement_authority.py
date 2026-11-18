"""Public native gates use the same owned active/running ledger as dungeons."""

import struct
import unittest
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import transport_criteria, dungeon_achievement_authority


class PublicTransportAchievementCriteriaTests(unittest.TestCase):
    def test_all_four_predicates_share_one_owned_request_snapshot(self):
        character = dict(id=7, level=4, running=[999], active=[999])
        snapshot = dungeon_achievement_authority.queries_from_snapshot(
            dict(running=[2158], completed=[2190], objectives=[4328], active=[2158])
        )
        store = unittest.mock.Mock()
        store.clock.return_value = 123456
        with patch.object(
            dungeon_achievement_authority, "queries", return_value=snapshot
        ) as query:
            allowed = transport_criteria.evaluator(store, character)
            self.assertTrue(
                allowed(
                    "IsAchievementActive(2158) and IsAchievementRunning(2158) and IsAchievementComplete(2190) and IsAchievementObjectiveComplete(4328)",
                    character,
                )
            )
            self.assertFalse(allowed("IsAchievementActive(2190)", character))
            self.assertFalse(allowed("IsAchievementRunning(2190)", character))
            self.assertFalse(allowed("IsAchievementActive(999)", character))
            query.assert_called_once_with(store, 7)
            with self.assertRaisesRegex(ValueError, "owner changed"):
                allowed("IsAchievementActive(2158)", dict(character, id=8))

    def test_active_and_running_missing_malformed_and_unknown_fail_closed(self):
        for expression in (
            "IsAchievementActive(2158)",
            "not IsAchievementRunning(2158)",
            "True or Evil()",
            "False and IsAchievementActive(True)",
            "IsAchievementRunning(0)",
            "IsAchievementActive(-1)",
            "IsAchievementRunning(2158,2159)",
            "IsAchievementActive(x=2158)",
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                transport_criteria.evaluate(expression, dict(id=7), now_ms=123)


class PublicTransportAchievementPostgresTests(PostgresCase):
    def test_actual_reserve_gate_uses_independent_owned_active_flag_and_missing_snapshot_rejects(
        self,
    ):
        from wakfu_server import generic_transports, seasonal_transport

        with self.store.connection() as db:
            account = db.execute(
                "INSERT INTO accounts(username,username_key,salt,password_hash) VALUES('publicgate','publicgate',%s,%s) RETURNING id",
                (bytes(16), b"test-hash"),
            ).fetchone()["id"]
            character_id = db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) VALUES(%s,'Public Gate','public gate',8,false,0,0,'[]','{}',60,60) RETURNING id",
                (account,),
            ).fetchone()["id"]
        character = dict(
            id=character_id,
            account_id=account,
            map_id=527,
            instance_id=0,
            x=54,
            y=-11,
            z=0,
            level=4,
            active=[2158],
            running=[2158],
        )
        request = struct.pack(">qiBi", 23616, 2004, 0, 2)
        for snapshot, admitted in (
            (
                dict(running=[2158], completed=[2190], objectives=[], active=[2158]),
                True,
            ),
            (dict(running=[], completed=[2158], objectives=[], active=[]), False),
            (dict(running=[], completed=[2158], objectives=[], active=[2158]), True),
            (dict(running=[], completed=[], objectives=[], active=[]), False),
        ):
            with self.subTest(snapshot=snapshot):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE character_achievement_authority SET snapshot=%s WHERE character_id=%s",
                        (Jsonb(snapshot), character_id),
                    )
                evaluate = seasonal_transport.evaluator(self.store, character)
                if admitted:
                    result = generic_transports.resolve(
                        character,
                        request,
                        source_allowed=lambda *_: True,
                        criterion_evaluator=evaluate,
                    )
                    self.assertEqual(
                        result["destination"],
                        dict(map_id=888, instance_id=0, x=0, y=0, z=0),
                    )
                    self.assertEqual(result["criterion"], "IsAchievementActive(2158)")
                else:
                    with self.assertRaisesRegex(ValueError, "criterion is not met"):
                        generic_transports.resolve(
                            character,
                            request,
                            source_allowed=lambda *_: True,
                            criterion_evaluator=evaluate,
                        )
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM character_achievement_authority WHERE character_id=%s",
                (character_id,),
            )
        with self.assertRaisesRegex(ValueError, "achievement authority"):
            generic_transports.resolve(
                character,
                request,
                source_allowed=lambda *_: True,
                criterion_evaluator=seasonal_transport.evaluator(self.store, character),
            )


if __name__ == "__main__":
    unittest.main()
