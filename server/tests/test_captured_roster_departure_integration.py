"""Detached owned teardown and availability save share the withdrawal transaction."""
from types import SimpleNamespace
from unittest.mock import patch
import unittest
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

    def test_owned_reset_saved_in_same_transaction_with_original_hp(self):
        fixture, _, _ = self.fixture()
        owner = character()
        candidate = SimpleNamespace(id=77, actors=fixture.fight.actors)
        restore_departing_roster(candidate, owner)
        rows = iter(
            (
                {"status": "active"},
                {"session_generation": fixture.session.generation},
                {"id": 10, "account_id": 1, "breed": 2},
                {"record": owner["captured_roster"]},
                None,
            )
        )
        db = SimpleNamespace(
            info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        )

        def execute(sql, params):
            value = next(rows)
            return SimpleNamespace(fetchone=lambda: value, rowcount=1)

        db.execute = execute
        store = SimpleNamespace(now=lambda: 123)
        with patch(
            "wakfu_server.combat_pve_withdraw_store.combat_health.persist",
            return_value={"character": {**owner, "hp": 45}},
        ) as health, patch(
            "wakfu_server.combat_captured_roster_checkpoint.save"
        ) as save:
            result = persist(
                store,
                fixture.session,
                owner,
                fixture.fight,
                db=db,
                captured_departure_fight=candidate,
            )
        self.assertIs(health.call_args.args[4], fixture.fight)
        self.assertIs(health.call_args.kwargs["db"], db)
        self.assertIs(save.call_args.args[0], db)
        self.assertEqual(result["character"]["hp"], 45)
        self.assertEqual(
            result["character"]["captured_roster"]["available"], [True] * 10
        )
        self.assertFalse(owner["captured_roster"]["available"][3])


if __name__ == "__main__":
    unittest.main()
