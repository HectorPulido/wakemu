"""Inert state book entries remain distinct from real cast qualification."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_monster_constructor_spell_representations import (
    constructor_spell_representations,
)


class ConstructorSpellRepresentationsTests(unittest.TestCase):
    def sources(self):
        return (
            dict(
                ref=2867,
                native_abilities=[dict(spell_id=4131)],
                initial_state_triples=[2484, -1, 1],
            ),
            {"4131": dict(levels=[[1, 1, [108802]]])},
            {
                "108802": dict(
                    effect_class=304,
                    variant=0,
                    criteria="False",
                    children=[],
                    parameters=[2484.0, 0.0, 0.0, 1.0],
                )
            },
            {"4131": dict(cast_criterion_raw="False")},
        )

    def test_literal_disabled_root_is_a_hint_not_execution_qualification(self):
        row = constructor_spell_representations(*self.sources())
        self.assertEqual(
            row["owned_book_role"], "only_inert_constructor_representations"
        )
        witness = row["constructor_representations"][0]
        self.assertEqual(witness["constructor_state_ids"], [2484])
        self.assertTrue(witness["casting_literal_false"])
        self.assertFalse(witness["level_equivalence_qualified"])
        self.assertFalse(witness["constructor_execution_qualified"])
        self.assertFalse(row["qualification_changed"])

    def test_actor_with_other_owned_spells_is_mixed(self):
        monster, spells, effects, casting = self.sources()
        monster["native_abilities"].append(dict(spell_id=4118))
        row = constructor_spell_representations(monster, spells, effects, casting)
        self.assertEqual(
            row["owned_book_role"], "mixed_constructor_representations_and_other_spells"
        )
        self.assertEqual(row["other_owned_spell_ids"], [4118])

    def test_nonliteral_false_and_nonconstant_or_absent_state_rejected(self):
        for mutate in (
            lambda e: e.update(criteria="not True"),
            lambda e: e.update(parameters=[2484.0, 1.0]),
            lambda e: e.update(parameters=[2485.0, 0.0]),
            lambda e: e.update(parameters=[float("nan"), 0.0]),
            lambda e: e.update(children=[9]),
            lambda e: e.update(effect_class=321),
        ):
            sources = self.sources()
            mutate(sources[2]["108802"])
            self.assertEqual(
                constructor_spell_representations(*sources)[
                    "constructor_representations"
                ],
                [],
            )

    def test_mixed_active_root_cannot_be_classified_inert(self):
        monster, spells, effects, casting = self.sources()
        spells["4131"]["levels"][0][2].append(5)
        effects["5"] = dict(
            effect_class=304,
            variant=0,
            criteria="",
            children=[],
            parameters=[2484.0, 0.0],
        )
        self.assertEqual(
            constructor_spell_representations(monster, spells, effects, casting)[
                "constructor_representations"
            ],
            [],
        )

    def test_empty_casting_criterion_is_recorded_without_claiming_disabled_cast(self):
        sources = self.sources()
        sources[3]["4131"]["cast_criterion_raw"] = ""
        row = constructor_spell_representations(*sources)
        self.assertFalse(row["constructor_representations"][0]["casting_literal_false"])
