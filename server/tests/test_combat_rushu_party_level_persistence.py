"""Actual PostgreSQL immutability for Rushu's frozen level-policy receipt."""
from copy import deepcopy
from types import SimpleNamespace

from postgres_case import PostgresCase
from wakfu_server.maps import boss_score
from wakfu_server.combat_boss_score_policy import RUSHU_SCORE


class RushuPartyLevelPersistenceTests(PostgresCase):
    def test_new_profiles_require_level_authority_and_frozen_receipts_cannot_drift(
        self,
    ):
        from wakfu_server.combat_boss_party_level_policy import freeze_level_profile

        profile = dict(
            policy=boss_score.POLICY,
            encounter_controller=RUSHU_SCORE.name,
            bosses={"-200": dict(reference=5306, round_limit=20)},
            player_ids=[7],
            player_team=0,
            round_limit=20,
            minimum_score=3000000,
        )
        actors = {
            7: SimpleNamespace(id=7, controlled=True, team=0, effective_level=245)
        }
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        with self.assertRaisesRegex(
            ValueError, "party-level authority"
        ), self.store.connection() as db:
            boss_score.freeze_snapshot(db, fight_id, profile)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT snapshot FROM boss_score_encounters WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()
            )
        profile.update(freeze_level_profile(profile, actors))
        with self.store.connection() as db:
            self.assertEqual(boss_score.freeze_snapshot(db, fight_id, profile), profile)
            self.assertEqual(boss_score.freeze_snapshot(db, fight_id, profile), profile)
        forged = deepcopy(profile)
        forged["outgoing_level_factor_bp"] = 10000
        with self.assertRaises(ValueError), self.store.connection() as db:
            boss_score.freeze_snapshot(db, fight_id, forged)
        changed = deepcopy(profile)
        changed.update(
            freeze_level_profile(
                changed,
                {
                    7: SimpleNamespace(
                        id=7, controlled=True, team=0, effective_level=230
                    )
                },
            )
        )
        with self.assertRaisesRegex(
            ValueError, "authority changed"
        ), self.store.connection() as db:
            boss_score.freeze_snapshot(db, fight_id, changed)
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT snapshot FROM boss_score_encounters WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()["snapshot"]
            self.assertEqual(saved, profile)
            self.assertEqual(saved["outgoing_level_factor_bp"], 12000)
        # An identical old receipt may be read again, but never upgraded or
        # fabricated by this compatibility path.
        from psycopg.types.json import Jsonb

        historical = {
            key: value
            for key, value in profile.items()
            if key
            not in (
                "party_effective_levels",
                "max_effective_level",
                "outgoing_level_factor_bp",
                "outgoing_level_policy",
                "outgoing_level_source",
            )
        }
        with self.store.connection() as db:
            previous_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO boss_score_encounters(fight_id,snapshot) VALUES(%s,%s)",
                (previous_id, Jsonb(historical)),
            )
            self.assertEqual(
                boss_score.freeze_snapshot(db, previous_id, historical), historical
            )
        changed_history = dict(historical, minimum_score=4000000)
        with self.assertRaisesRegex(
            ValueError, "party-level authority"
        ), self.store.connection() as db:
            boss_score.freeze_snapshot(db, previous_id, changed_history)
