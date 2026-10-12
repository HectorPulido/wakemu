"""Visibility may hide an action while preserving its complete ownership book."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native_spell_visibility import available_owned_actions, SCHEMA, CONSUMER
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
)


def document(criteria):
    return dict(
        schema=SCHEMA,
        spells={
            str(ref): dict(
                reference=ref,
                visibility_criterion_raw=raw,
                native_criterion_present=bool(raw),
                native_parser="eQe.tz",
                native_consumer=CONSUMER,
            )
            for ref, raw in criteria.items()
        },
    )


class NativeSpellVisibilityQueryTests(unittest.TestCase):
    def setUp(self):
        # These state-only expressions use no characteristic aliases. Keep the
        # unrelated catalog lookup out of this pure query/evaluator regression.
        aliases = patch(
            "wakfu_server.combat_conditions.canonical_aliases", return_value={}
        )
        aliases.start()
        self.addCleanup(aliases.stop)

    def context(self, states):
        actor = ConditionActor(state_ids=states)
        return ConditionContext(dict(caster=actor, target=actor))

    def test_empty_criteria_keep_all_owned_wp_spells_available_without_resource_grants(
        self,
    ):
        owned = [dict(reference=ref, level=8, wp_cost=1) for ref in (7359, 7360, 7361)]
        before = deepcopy(owned)
        result = available_owned_actions(
            owned,
            document({ref: "" for ref in (7359, 7360, 7361)}),
            self.context(frozenset()),
        )
        self.assertEqual(result["owned_actions"], tuple(before))
        self.assertEqual(result["available_actions"], tuple(before))
        self.assertEqual(owned, before)
        self.assertFalse(result["ownership_changed"])
        self.assertFalse(result["castability_evaluated"])

    def test_has_state_visibility_is_dormant_without_removing_owned_spell(self):
        owned = [dict(reference=7395, level=149)]
        visibility = document({7395: "HasState(7129)"})
        absent = available_owned_actions(owned, visibility, self.context(frozenset()))
        present = available_owned_actions(
            owned, visibility, self.context(frozenset({7129}))
        )
        self.assertEqual(absent["owned_actions"], present["owned_actions"])
        self.assertEqual(absent["available_actions"], ())
        self.assertEqual(absent["dormant_actions"], tuple(owned))
        self.assertEqual(present["available_actions"], tuple(owned))

    def test_inverse_tofu_visibility_uses_same_real_actor(self):
        visibility = document({549: "not HasState(7129)"})
        self.assertEqual(
            len(
                available_owned_actions(
                    [dict(reference=549)], visibility, self.context(frozenset())
                )["available_actions"]
            ),
            1,
        )
        self.assertEqual(
            available_owned_actions(
                [dict(reference=549)], visibility, self.context(frozenset({7129}))
            )["available_actions"],
            (),
        )

    def test_missing_state_authority_is_unknown_instead_of_dormant(self):
        with self.assertRaises(UnknownCondition):
            available_owned_actions(
                [dict(reference=7395)],
                document({7395: "HasState(7129)"}),
                self.context(None),
            )

    def test_unknown_criterion_never_becomes_a_silent_visibility_exclusion(self):
        with self.assertRaises(UnknownCondition):
            available_owned_actions(
                [dict(reference=7395)],
                document({7395: "UnsupportedVisibility()"}),
                self.context(frozenset()),
            )

    def test_missing_metadata_cannot_drop_an_owned_spell(self):
        with self.assertRaisesRegex(
            ValueError, "Missing exact native spell visibility"
        ):
            available_owned_actions(
                [dict(reference=7359)], document({}), self.context(frozenset())
            )

    def test_foreign_target_context_rejects_even_empty_criterion(self):
        with self.assertRaisesRegex(ValueError, "same actual source/target"):
            available_owned_actions(
                [dict(reference=7359)],
                document({7359: ""}),
                ConditionContext(
                    dict(
                        caster=ConditionActor(state_ids=frozenset()),
                        target=ConditionActor(state_ids=frozenset()),
                    )
                ),
            )

    def test_generator_book_is_preserved_completely(self):
        result = available_owned_actions(
            (dict(reference=ref) for ref in (7359, 7360)),
            document({7359: "", 7360: ""}),
            self.context(frozenset()),
        )
        self.assertEqual(len(result["owned_actions"]), 2)

    def test_evaluator_unknown_is_not_coerced_to_false(self):
        with self.assertRaisesRegex(ValueError, "did not return a boolean"):
            available_owned_actions(
                [dict(reference=7395)],
                document({7395: "HasState(7129)"}),
                self.context(frozenset()),
                evaluate=lambda raw, context: None,
            )

    def test_wrong_consumer_and_malformed_presence_reject(self):
        for patch in [
            dict(native_consumer="casting_criterion"),
            dict(native_criterion_present=1),
            dict(reference=0),
        ]:
            visibility = document({7359: ""})
            visibility["spells"]["7359"].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                available_owned_actions(
                    [dict(reference=7359)], visibility, self.context(frozenset())
                )


if __name__ == "__main__":
    unittest.main()
