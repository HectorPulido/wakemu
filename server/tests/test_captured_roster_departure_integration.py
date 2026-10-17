"""Detached owned teardown and availability save share the withdrawal transaction."""
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from postgres_case import PostgresCase
from psycopg.pq import TransactionStatus
from test_combat_pve_withdraw import WithdrawalPlanTests
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.combat_captured_roster_lifecycle import restore_departing_roster
from wakfu_server.combat_pve_withdraw_store import persist


def character():
    slots = [None] * 10
    slots[3] = CapturedCreature(3, 5347, "Owned")
    return dict(
        id=10,
        account_id=1,
        breed=2,
        captured_roster=OwnedCapturedRoster(
            10, tuple(slots), (False,) * 10, 3
        ).to_record(),
    )


class CapturedDepartureIntegrationTests(unittest.TestCase):
    def fixture(self):
        fixture = WithdrawalPlanTests()
        fixture.setUp()
        registry, shared, _ = fixture.registry()
        return fixture, registry, shared

    def test_candidate_reset_commits_without_changing_original_health_or_component(
        self,
    ):
        fixture, registry, shared = self.fixture()
        owner = character()
        fixture.fight.native_captured_rosters = {"10": owner["captured_roster"]}

        def teardown(candidate):
            self.assertIsNot(candidate, fixture.fight)
            restore_departing_roster(candidate, owner)

        def save(original):
            self.assertIs(original, fixture.fight)
            self.assertEqual(original.actors[10].hp, 45)
            self.assertFalse(original.native_captured_rosters["10"]["available"][3])
            return {"character": owner}

        registry.withdraw_pve(fixture.session, persist=save, owned_teardown=teardown)
        self.assertEqual(
            shared.fight.native_captured_roster_updates["10"]["available"], [True] * 10
        )
        self.assertFalse(fixture.fight.native_captured_rosters["10"]["available"][3])

    def test_persistence_failure_preserves_original_unavailable_slot_and_outboxes(self):
        fixture, registry, shared = self.fixture()
        owner = character()
        fixture.fight.native_captured_rosters = {"10": owner["captured_roster"]}

        def fail(original):
            raise RuntimeError("rollback")

        with self.assertRaisesRegex(RuntimeError, "rollback"):
            registry.withdraw_pve(
                fixture.session,
                persist=fail,
                owned_teardown=lambda candidate: restore_departing_roster(
                    candidate, owner
                ),
            )
        self.assertIs(shared.fight, fixture.fight)
        self.assertFalse(fixture.fight.native_captured_rosters["10"]["available"][3])
        self.assertFalse(shared.outboxes[2])
        self.assertEqual(shared.withdrawals, {})


class CapturedDeparturePersistenceTests(PostgresCase):
    def persisted_fixture(self):
        from copy import deepcopy
        from wakfu_server import health_store
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_shared import Session
        from wakfu_server.characters.captured_roster_store import save

        store = self.store
        store.clock = lambda: 1000
        account = store.register("capture-owner", "local-password")["id"]
        generation = store.begin_session(account)
        owner = store.create_character(account, "Captured Owner", breed=2)
        owner = store.select_character(account, generation, owner["id"])
        owner = health_store.initialize(
            store, account, generation, owner["id"], coefficient=0
        )
        slots = [None] * 10
        slots[3] = CapturedCreature(3, 1152, "Owned")
        roster = OwnedCapturedRoster(owner["id"], tuple(slots), (False,) * 10, 3)
        with store.connection() as db:
            save(db, owner, roster)
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation,entry_hp,"
                "entry_max_hp,entry_hp_damage,entry_health_dead) "
                "VALUES(%s,%s,%s,0,%s,%s,%s,%s,%s)",
                (
                    fight_id,
                    owner["id"],
                    account,
                    generation,
                    owner["hp"],
                    owner["max_hp"],
                    owner["hp_damage"],
                    owner["health_dead"],
                ),
            )
            owner = store.character(account, owner["id"], db)
        self.assertGreaterEqual(owner["max_hp"], 45)
        actor = Actor(
            owner["id"],
            0,
            (0, 0, 0),
            45,
            6,
            3,
            1,
            owner["level"],
            account,
            True,
            max_hp=owner["max_hp"],
        )
        original = Fight(
            fight_id,
            [actor, Actor(-7, 1, (1, 0, 0), 30, 6, 3, 1, 1)],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        original.ready(account)
        original.native_captured_rosters = {str(owner["id"]): roster.to_record()}
        candidate = deepcopy(original)
        self.assertTrue(restore_departing_roster(candidate, owner))
        return (
            Session(account, owner["id"], generation, owner["map_id"], 0),
            owner,
            original,
            candidate,
        )

    def test_owned_reset_saved_in_same_transaction_with_original_hp(self):
        from wakfu_server import combat_health
        from wakfu_server.characters.captured_roster_store import save as actual_save

        session, owner, original, candidate = self.persisted_fixture()
        with self.store.connection() as db:
            self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)
            with db.transaction(), patch.object(
                self.store, "lock_character", wraps=self.store.lock_character
            ) as lock, patch(
                "wakfu_server.combat_pve_withdraw_store.combat_health.persist",
                wraps=combat_health.persist,
            ) as health, patch(
                "wakfu_server.combat_captured_roster_checkpoint.save", wraps=actual_save
            ) as save:
                result = persist(
                    self.store,
                    session,
                    owner,
                    original,
                    db=db,
                    captured_departure_fight=candidate,
                )
                self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)
                lock.assert_any_call(
                    db, session.account_id, session.generation, session.character_id
                )
                self.assertIs(health.call_args.args[4], original)
                self.assertIs(health.call_args.kwargs["db"], db)
                self.assertIs(save.call_args.args[0], db)
                self.assertEqual(result["character"]["hp"], 45)
                self.assertEqual(
                    result["character"]["captured_roster"]["available"], [True] * 10
                )
                self.assertTrue(result["applied"])
        reopened = self.reopen()
        loaded = reopened.character(session.account_id, owner["id"])
        self.assertEqual(loaded["hp"], 45)
        self.assertEqual(loaded["captured_roster"]["available"], [True] * 10)
        self.assertEqual(
            loaded["captured_roster"]["slots"], owner["captured_roster"]["slots"]
        )
        self.assertEqual(loaded["captured_roster"]["selected_slot"], 3)
        self.assertFalse(owner["captured_roster"]["available"][3])
        self.assertFalse(
            original.native_captured_rosters[str(owner["id"])]["available"][3]
        )

    def test_transaction_failure_rolls_back_health_component_and_withdrawal_receipts(
        self,
    ):
        session, owner, original, candidate = self.persisted_fixture()
        with self.assertRaisesRegex(
            RuntimeError, "rollback"
        ), self.store.connection() as db:
            with db.transaction():
                result = persist(
                    self.store,
                    session,
                    owner,
                    original,
                    db=db,
                    captured_departure_fight=candidate,
                )
                self.assertEqual(result["character"]["hp"], 45)
                self.assertEqual(
                    result["character"]["captured_roster"]["available"], [True] * 10
                )
                raise RuntimeError("rollback")
        reopened = self.reopen()
        loaded = reopened.character(session.account_id, owner["id"])
        self.assertEqual(loaded["hp"], owner["hp"])
        self.assertEqual(loaded["captured_roster"], owner["captured_roster"])
        with reopened.connection() as db:
            for table in ("fight_health_exits", "combat_pve_withdrawals"):
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM " + table + " WHERE fight_id=%s",
                        (original.id,),
                    ).fetchone()["count"],
                    0,
                )
        self.assertFalse(
            original.native_captured_rosters[str(owner["id"])]["available"][3]
        )


if __name__ == "__main__":
    unittest.main()
