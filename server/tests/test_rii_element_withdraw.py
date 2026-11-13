"""Withdrawing the lesson owner cleans only its private encounter grants."""
import unittest
from unittest.mock import patch

import test_combat_pve_withdraw as withdraw_fixture
from wakfu_server import rii_lesson_grants
from wakfu_server.combat_pve_withdraw import plan
from wakfu_server.combat_spell_grant import granted_spells


class ElementalWithdrawalTests(unittest.TestCase):
    def test_owner_withdrawal_cleans_candidate_without_mutating_source(self):
        fixture = withdraw_fixture.WithdrawalPlanTests()
        fixture.setUp()
        fight = fixture.fight
        fight.native_effect_uid_next = 1000
        fight.rii_element_lesson_contract = {"owner": 10, "target": -200}
        with patch(
            "wakfu_server.combat_spell_grant.native_spell_references",
            return_value=frozenset(rii_lesson_grants.SPELLS),
        ), patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={
                str(i): {"maximum_level": 200} for i in rii_lesson_grants.SPELLS
            },
        ), patch(
            "wakfu_server.combat_retained_runtime.native_retained_metadata",
            return_value={
                "effects": {
                    "347172": {
                        "effect_class": 649,
                        "definition_type": 2,
                        "definition_dispellable": False,
                        "subscription": False,
                    }
                }
            },
        ):
            uids = rii_lesson_grants.install(
                fight, 10, [], action_id=1, allocate_uid=fight.allocate_effect_uid
            )
        fight.rii_element_lesson_contract.update(initialized=True, grant_uids=uids)
        result = plan(fixture.session, fight, fixture.runtime)
        self.assertFalse(granted_spells(result.fight, 10))
        self.assertFalse(hasattr(result.fight, "rii_element_lesson_contract"))
        self.assertEqual([op for op, _ in result.public_packets].count(13560), 4)
        self.assertEqual(set(granted_spells(fight, 10)), set(rii_lesson_grants.SPELLS))
        self.assertEqual(result.fight.phase, "active")
