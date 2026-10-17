"""Recipient reproduction detects graph and reconstructed namespace mutations."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_recipient_reproduction import (
    capture_recipient_request,
    execute_recipient_case,
    record_recipient_expectation,
    compare_recipient_expectation,
)


class RecipientReproductionTests(unittest.TestCase):
    def fixture(self):
        actor = Actor(7, 0, (0, 0, 0), 100, 6, 3, 100, 1, 3, True)
        enemy = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 50, 1)
        fight = Fight(
            88,
            [actor, enemy],
            {actor.position, enemy.position},
            {0: {actor.position}, 1: {enemy.position}},
        )
        shared = SimpleNamespace(
            map_id=1134,
            instance_id=0,
            join_context={},
            runtime=SimpleNamespace(
                native_action_id=41, turn_deadline=None, awaiting_ack=None
            ),
        )
        return capture_recipient_request(
            fight,
            shared,
            role="spectator",
            actor_payloads={7: (b"stats", b"effects")},
            payload_authority="test-placeholder",
            deadline_ms=1700000000000,
            clocks=dict(wall_time_ns=1700000000000000000, monotonic_ns=0),
        )

    def identities(self):
        return (
            patch(
                "wakfu_server.combat_recipient_reproduction.source_identity",
                return_value={"sha256": "source"},
            ),
            patch(
                "wakfu_server.combat_recipient_reproduction.catalog_identity",
                return_value={"revision": "catalog", "inventory_sha256": "inventory"},
            ),
        )

    def test_new_and_deleted_namespace_attributes_cannot_escape_read_only_check(self):
        mutations = (
            lambda fight, shared: setattr(shared, "new_attribute", 1),
            lambda fight, shared: delattr(shared, "map_id"),
            lambda fight, shared: setattr(shared.runtime, "new_attribute", 1),
            lambda fight, shared: delattr(shared.runtime, "awaiting_ack"),
            lambda fight, shared: setattr(fight, "new_attribute", 1),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                source, catalog = self.identities()
                with source, catalog:
                    case = self.fixture()

                    def producer(fight, shared, **kwargs):
                        mutation(fight, shared)
                        return ()

                    with patch(
                        "wakfu_server.combat_spectator_snapshot.current_snapshot",
                        producer,
                    ), self.assertRaisesRegex(
                        ValueError, "mutated its captured input graph"
                    ):
                        execute_recipient_case(case)

    def test_current_expectation_detects_packet_changes_and_rejects_historical_format(
        self,
    ):
        source, catalog = self.identities()
        with source, catalog:
            case = self.fixture()
            with patch(
                "wakfu_server.combat_spectator_snapshot.current_snapshot",
                return_value=((12053, b"current"),),
            ):
                result = execute_recipient_case(case)
            record_recipient_expectation(case, result)
            self.assertTrue(compare_recipient_expectation(case, result)["matches"])
            self.assertTrue(result["input_unchanged"])
            self.assertEqual(result["payload_authority"], "test-placeholder")
            with patch(
                "wakfu_server.combat_spectator_snapshot.current_snapshot",
                return_value=((12053, b"changed"),),
            ):
                changed = execute_recipient_case(case)
            self.assertFalse(compare_recipient_expectation(case, changed)["matches"])
            case["schema"] = "wakemu-combat-recipient-reproduction-v1"
            case["expected"] = {"legacy": None, "shared": None}
            with self.assertRaisesRegex(
                ValueError, "Invalid recipient reproduction capsule"
            ):
                execute_recipient_case(case)


if __name__ == "__main__":
    unittest.main()
