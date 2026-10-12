"""Reconciliation reuses exact per-monster passive admission authority."""
import copy
import unittest

from reconcile_monster_offline_reports import passive_reference_proven
from test_monster_passive_initialization import sources, case


class OfflinePassiveReconciliationTests(unittest.TestCase):
    def fixture(self):
        monster, npc, casting = sources()
        authority = dict(
            min_level=monster["min_level"],
            max_level=monster["max_level"],
            spell_ids=[ability["spell_id"] for ability in monster["native_abilities"]],
            initial_state_triples=monster["initial_state_triples"],
        )
        npc["activation_policy"] = {
            "enabled_monsters": {
                str(monster["ref"]): authority,
                "9999": dict(authority, min_level=99, max_level=100),
            }
        }
        observed = case(monster, npc, casting, level=2)
        return monster, npc, casting, observed

    def test_actual_passive_proof_receives_own_descriptor_in_mixed_policy(self):
        monster, npc, casting, observed = self.fixture()
        self.assertTrue(
            passive_reference_proven(
                observed, monster["ref"], npc, ({monster["ref"]: monster}, casting)
            )
        )
        self.assertEqual(observed["successful_targets"], [])
        self.assertEqual(observed["attempts"], 0)

    def test_wrong_reference_or_missing_constructor_receipt_fails_closed(self):
        monster, npc, casting, observed = self.fixture()
        source = ({monster["ref"]: monster}, casting)
        self.assertFalse(passive_reference_proven(observed, 9999, npc, source))
        self.assertFalse(passive_reference_proven(observed, 8888, npc, source))
        observed["initialization_receipts"] = []
        self.assertFalse(
            passive_reference_proven(observed, monster["ref"], npc, source)
        )

    def test_changed_own_descriptor_does_not_borrow_another_policy(self):
        monster, npc, casting, observed = self.fixture()
        npc["activation_policy"]["enabled_monsters"][str(monster["ref"])][
            "max_level"
        ] = 1
        self.assertFalse(
            passive_reference_proven(
                observed, monster["ref"], npc, ({monster["ref"]: monster}, casting)
            )
        )
