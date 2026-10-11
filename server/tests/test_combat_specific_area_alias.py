"""eQb accepts IsSpecific and IsSpecificArea as the identical token."""
import unittest
from unittest.mock import patch
from wakfu_server.combat.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class SpecificAreaAliasTests(unittest.TestCase):
    def setUp(self):
        aliases = patch(
            "wakfu_server.combat.combat_conditions.canonical_aliases", return_value={}
        )
        aliases.start()
        self.addCleanup(aliases.stop)

    def test_alias_uses_same_callback_and_exact_reference(self):
        calls = []

        def query(name, reference):
            calls.append((name, reference))
            return reference == 1361

        context = ConditionContext({}, area_identity_query=query)
        for spelling in ("IsSpecific", "IsSpecificArea"):
            self.assertTrue(
                evaluate_condition(f"{spelling}(1360) or {spelling}(1361)", context)
            )
        self.assertEqual(
            calls, [("IsSpecificArea", 1360), ("IsSpecificArea", 1361)] * 2
        )

    def test_missing_authority_and_invalid_signature_remain_rejected(self):
        for criterion in ("IsSpecific(1360)", "IsSpecific()", "IsSpecific(1360, 1361)"):
            with self.subTest(criterion=criterion), self.assertRaises(UnknownCondition):
                evaluate_condition(criterion, ConditionContext({}))
