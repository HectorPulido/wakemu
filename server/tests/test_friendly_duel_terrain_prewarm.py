"""PostgreSQL regressions for preparing duel terrain outside row locks."""
import struct
import unittest

import test_friendly_duels as duel_fixtures
from wakfu_server.friendly_duels import answer_challenge


class FriendlyDuelTerrainPrewarmTests(unittest.TestCase):
    def setUp(self):
        # Keep this fixture behind a module reference so unittest does not
        # rediscover FriendlyDuelStoreTests as a second test class here.
        self.fixture = duel_fixtures.FriendlyDuelStoreTests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def answer_body(self, *, accepted=True):
        return struct.pack(">qBB", self.fixture.char_a["id"], int(accepted), 0)

    def test_acceptance_prewarms_before_character_locks_and_forwards_terrain(self):
        fixture = self.fixture
        fixture.challenge()
        terrain = object()
        phases = []

        def prewarm(map_id):
            self.assertEqual(map_id, 1134)
            # The callback opens a separate connection and must be able to
            # acquire both character rows with NOWAIT before acceptance locks.
            with fixture.store.connection() as db:
                rows = db.execute(
                    "SELECT id FROM characters WHERE id=ANY(%s) "
                    "ORDER BY id FOR UPDATE NOWAIT",
                    ([fixture.char_a["id"], fixture.char_b["id"]],),
                ).fetchall()
            self.assertEqual(len(rows), 2)
            phases.append("prewarm")
            return terrain

        def prepare(db, fight_id, invitation, source, target, *, prepared_terrain):
            self.assertIs(prepared_terrain, terrain)
            phases.append("prepare")
            return {"fight_id": fight_id}, lambda: None

        result = answer_challenge(
            fixture.store,
            fixture.session_b,
            self.answer_body(),
            prepare_duel=prepare,
            prewarm_duel=prewarm,
        )

        self.assertTrue(result["accepted"])
        self.assertEqual(phases, ["prewarm", "prepare"])

    def test_decline_does_not_prewarm_or_prepare(self):
        fixture = self.fixture
        fixture.challenge()
        result = answer_challenge(
            fixture.store,
            fixture.session_b,
            self.answer_body(accepted=False),
            prepare_duel=lambda *_: self.fail("prepare callback ran on decline"),
            prewarm_duel=lambda *_: self.fail("prewarm ran on decline"),
        )
        self.assertFalse(result["accepted"])

    def test_stale_acceptance_uses_prewarmer_only_as_a_hint(self):
        fixture = self.fixture
        fixture.challenge()
        fixture.store.end_session(fixture.account_a, fixture.generation_a)
        warmed_maps = []

        result = answer_challenge(
            fixture.store,
            fixture.session_b,
            self.answer_body(),
            prepare_duel=lambda *_: self.fail("stale duel runtime was prepared"),
            prewarm_duel=lambda map_id: warmed_maps.append(map_id) or object(),
        )

        self.assertFalse(result["accepted"])
        self.assertIsNone(result["fight_id"])
        self.assertEqual(warmed_maps, [1134])

    def test_prepare_failure_after_prewarm_rolls_back_acceptance(self):
        fixture = self.fixture
        fixture.challenge()
        terrain = object()
        received_terrain = []

        def prepare(*args, prepared_terrain=None):
            received_terrain.append(prepared_terrain)
            self.assertIs(prepared_terrain, terrain)
            raise ValueError("prepared duel failed")

        with self.assertRaisesRegex(ValueError, "prepared duel failed"):
            answer_challenge(
                fixture.store,
                fixture.session_b,
                self.answer_body(),
                prepare_duel=prepare,
                prewarm_duel=lambda _map_id: terrain,
            )

        self.assertEqual(received_terrain, [terrain])
        with fixture.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM combat_fights").fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute("SELECT status FROM friendly_duel_invitations").fetchone()[
                    "status"
                ],
                "pending",
            )


if __name__ == "__main__":
    unittest.main()
