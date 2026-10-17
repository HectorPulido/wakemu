"""Source integrity and strict native predicate boundaries; no catalog required."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from wakfu_server.characters.owned_social_context import (
    OwnedSocialContext,
    pin,
    current,
)
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_reproduction_state import encode_state, decode_state


class OwnedSocialContextTests(unittest.TestCase):
    def receipt(self, actor=7, account=2, nation=30):
        # A validator/selection fixture, not proof that SQL admission happened.
        return OwnedSocialContext(actor, account, nation, None, 0, "validator-only")

    def context(self, receipt=None, actor=7, account=2):
        return ConditionContext(
            actors={
                "caster": ConditionActor(
                    actor_id=actor,
                    is_player=True,
                    is_native_fighter=True,
                    is_native_ehg=True,
                    native_account_id=account,
                    native_social_context=receipt,
                )
            }
        )

    def test_known_empty_guild_and_nation_require_explicit_typed_source(self):
        self.assertTrue(
            evaluate_condition(
                "GetGuildLevel() == 0 and GetNationId() == 30",
                self.context(self.receipt()),
            )
        )
        for value in (None, {"guild_native": None}):
            with self.subTest(value=value), self.assertRaises(UnknownCondition):
                evaluate_condition("GetGuildLevel() == 0", self.context(value))

    def test_foreign_actor_account_and_bool_identity_reject(self):
        for actor, account in ((8, 2), (7, 3), (True, 2), (7, True)):
            with self.subTest(actor=actor, account=account), self.assertRaises(
                UnknownCondition
            ):
                evaluate_condition(
                    "GetNationId() == 30", self.context(self.receipt(), actor, account)
                )

    def test_owned_caster_and_explicit_target_have_distinct_components(self):
        own = self.context(self.receipt()).actors["caster"]
        other = replace(own, actor_id=8, native_social_context=self.receipt(8, 2, 31))
        context = ConditionContext(actors={"caster": own, "target": other})
        self.assertTrue(
            evaluate_condition(
                'GetNationId() == 30 and GetNationId("target") == 31', context
            )
        )
        self.assertTrue(evaluate_condition("GetGuildLevel() == 0", context))
        for criterion in (
            'GetGuildLevel("target") == 0',
            "GetNationId(0) == 0",
            "IsProtectorInFight()",
        ):
            with self.subTest(criterion=criterion), self.assertRaises(UnknownCondition):
                evaluate_condition(criterion, context)

    def test_checkpoint_integrity_and_typed_reproduction_preserve_revision(self):
        receipt = self.receipt()
        record = receipt.to_record()
        self.assertEqual(OwnedSocialContext.from_record(record), receipt)
        recovered = decode_state(encode_state(receipt))
        self.assertIs(type(recovered), OwnedSocialContext)
        self.assertEqual(recovered, receipt)
        record["nation_id"] = 31
        with self.assertRaisesRegex(ValueError, "integrity"):
            OwnedSocialContext.from_record(record)
        corrupted = deepcopy(receipt)
        object.__setattr__(corrupted, "nation_id", 31)
        with self.assertRaisesRegex(ValueError, "digest"):
            corrupted.validate()

    def test_admission_snapshot_does_not_refresh_or_accept_foreign_owner(self):
        receipt = self.receipt()
        fight = SimpleNamespace(actors={7: SimpleNamespace(controlled=True)})
        source = dict(id=7, account_id=2, native_social_context=receipt.to_record())
        pin(fight, source)
        later = self.receipt(nation=31)
        pin(fight, dict(source, native_social_context=later.to_record()))
        self.assertEqual(current(fight, source), receipt)
        preview = deepcopy(fight)
        self.assertEqual(current(preview, source), receipt)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            current(preview, dict(source, account_id=3))
        self.assertEqual(current(fight, source), receipt)

    def test_authority_observer_preserves_canonical_source_without_changing_input(self):
        from wakfu_server.combat_input_observation import (
            observe_combat_inputs,
            observe_authority,
        )

        receipt = self.receipt()
        source = dict(native_social_context=receipt.to_record())
        with observe_combat_inputs() as observation:
            self.assertIs(observe_authority("social-source", source), source)
        captured = observation.snapshot()
        self.assertEqual(captured["incomplete"], [])
        self.assertEqual(
            captured["events"][0]["value"]["native_social_context"], receipt.to_record()
        )
        self.assertEqual(source["native_social_context"], receipt.to_record())
