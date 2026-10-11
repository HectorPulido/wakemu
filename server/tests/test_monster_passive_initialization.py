"""Passive qualification requires exact source, levels and real constructor proof."""
import copy
from dataclasses import asdict
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_passive_initialization import (
    passive_initialization_proof,
    passive_case_proven,
)
from validate_monster_spell_activation import initialization_proven
from wakfu_server.combat_summon_initial_states import initial_state_plan


def sources():
    monster = dict(
        ref=2867,
        min_level=1,
        max_level=2,
        native_abilities=[dict(spell_id=4131, level_parameter=-1)],
        initial_state_triples=[2484, -1, 1],
    )
    document = dict(
        spells={"4131": dict(levels=[[1, 1, [108802]]] * 2)},
        effects={
            "108802": dict(
                effect_class=304,
                variant=0,
                criteria="False",
                children=[],
                native_target_selector={"class": "fcE", "mask": 0},
                parameters=[2484.0, 0.0, 0.0, 1.0, -1.0, 0.0],
            )
        },
    )
    casting = {"4131": dict(maximum_level=2, cast_criterion_raw="False")}
    return monster, document, casting


def receipt(monster, level):
    plan = initial_state_plan(monster["initial_state_triples"], level)
    return dict(
        initialized=True,
        ref=monster["ref"],
        descriptor_level=level,
        raw_triples=monster["initial_state_triples"],
        resolved_states=[asdict(item) for item in plan],
        applications=[
            dict(state_id=item.state_id, level=item.level, applied=True)
            for item in plan
        ],
        placement_effects=dict(
            verified=True,
            effect_count=1,
            state_carrier_count=1,
            bytes=20,
            sha256="a" * 64,
        ),
    )


def case(monster, document, casting, level=1):
    initialized = receipt(monster, level)
    proof = passive_initialization_proof(
        monster,
        level,
        4131,
        level,
        document,
        casting,
        initialized,
        initialization_proven,
    )
    return dict(
        reference=monster["ref"],
        level=level,
        spell_id=4131,
        spell_level=level,
        status="passive_initialization_only",
        attempts=0,
        errors={},
        successful_targets=[],
        initialization_receipts=[initialized],
        passive_initialization_proof=proof,
    )


class PassiveInitializationProofTests(unittest.TestCase):
    def test_exact_native_plan_and_levels_qualify_separately_from_cast(self):
        monster, document, casting = sources()
        observed = case(monster, document, casting, 2)
        self.assertTrue(
            passive_case_proven(
                observed, monster, document, casting, initialization_proven
            )
        )
        self.assertEqual(observed["attempts"], 0)
        self.assertEqual(observed["successful_targets"], [])
        self.assertEqual(observed["passive_initialization_proof"]["state_level"], 2)

    def test_forged_status_or_proof_without_receipt_rejected(self):
        monster, document, casting = sources()
        for change in (
            {"initialization_receipts": []},
            {"passive_initialization_proof": {"qualified": True}},
            {"reference": 999},
            {"attempts": 1},
            {"successful_targets": [{"effectful": True}]},
            {"errors": {"x": 1}},
        ):
            observed = case(monster, document, casting)
            observed.update(change)
            self.assertFalse(
                passive_case_proven(
                    observed, monster, document, casting, initialization_proven
                )
            )

    def test_changed_receipt_and_native_level_mismatch_rejected(self):
        monster, document, casting = sources()
        for mutate in (
            lambda c: c["initialization_receipts"][0]["applications"][0].update(
                applied=False
            ),
            lambda c: c["initialization_receipts"][0]["placement_effects"].update(
                sha256="b" * 64
            ),
            lambda c: c.update(spell_level=2),
        ):
            observed = case(monster, document, casting)
            mutate(observed)
            self.assertFalse(
                passive_case_proven(
                    observed, monster, document, casting, initialization_proven
                )
            )

    def test_nonfalse_or_mixed_roots_and_unowned_spells_rejected(self):
        for mutate in (
            lambda m, d, c: c["4131"].update(cast_criterion_raw=""),
            lambda m, d, c: d["effects"]["108802"].update(criteria=""),
            lambda m, d, c: d["spells"]["4131"]["levels"][0][2].append(9),
            lambda m, d, c: m.update(native_abilities=[]),
            lambda m, d, c: d["effects"]["108802"].update(
                native_target_selector={"class": "fcE", "mask": 1}
            ),
        ):
            monster, document, casting = copy.deepcopy(sources())
            observed = case(monster, document, casting)
            mutate(monster, document, casting)
            self.assertFalse(
                passive_case_proven(
                    observed, monster, document, casting, initialization_proven
                )
            )

    def test_state_reference_presence_without_level_equivalence_rejected(self):
        monster, document, casting = sources()
        observed = case(monster, document, casting)
        monster["initial_state_triples"] = [2484, 2, 1]
        self.assertFalse(
            passive_case_proven(
                observed, monster, document, casting, initialization_proven
            )
        )
