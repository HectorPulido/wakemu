"""Mixed native states select callback alternatives, retaining independent roots."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_state_variants import (
    paired_state_callback,
    state_child_variant_mode,
)


class MixedStateCallbackVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exact published native contracts; this pure policy test does not
        # need to initialize every class and the full combat runtime catalogue.
        fixture = Path(__file__).parent / "fixtures/rogue_mixed_callback_roots.json"
        cls.definitions = json.loads(fixture.read_text())["definitions"]

    def fixture(self):
        return SimpleNamespace(
            reference=7923, effect_ids=[358848, 358850, 416453, 416454]
        ), deepcopy(self.definitions)

    def mode(self, state, definitions, reference, critical):
        with patch(
            "wakfu_server.combat_state_variants.resolve_state_container",
            return_value=state,
        ):
            return state_child_variant_mode(
                SimpleNamespace(),
                19,
                effect_definitions=definitions,
                causing_critical=critical,
                effect_reference=reference,
            )

    def test_mixed_subscribed_pair_selects_actual_causing_branch(self):
        state, definitions = self.fixture()
        for reference in (358848, 358850):
            self.assertTrue(paired_state_callback(state, definitions, reference))
            self.assertEqual(
                self.mode(state, definitions, reference, False), "EFFECTS_ONLY"
            )
            self.assertEqual(
                self.mode(state, definitions, reference, True), "CRITICALS_ONLY"
            )

    def test_independent_stat_roots_and_group_descendants_remain_all(self):
        state, definitions = self.fixture()
        for reference in (416453, 416454, 417862, 417863):
            self.assertEqual(self.mode(state, definitions, reference, True), "ALL")

    def test_subscription_mismatch_is_not_a_pair(self):
        state, definitions = self.fixture()
        masks = list(definitions["358850"]["target_masks"])
        masks[5] = [1001]
        definitions["358850"]["target_masks"] = masks
        self.assertEqual(self.mode(state, definitions, 358848, False), "ALL")

    def test_ambiguous_or_incomplete_population_does_not_select(self):
        state, definitions = self.fixture()
        state.effect_ids.append(999999)
        definitions["999999"] = deepcopy(definitions["358848"])
        self.assertEqual(self.mode(state, definitions, 358848, False), "ALL")
        state, definitions = self.fixture()
        del definitions["416453"]["criteria"]
        self.assertEqual(self.mode(state, definitions, 358848, True), "ALL")

    def test_paired_callback_requires_actual_causing_branch(self):
        state, definitions = self.fixture()
        with self.assertRaisesRegex(ValueError, "causing branch"):
            self.mode(state, definitions, 358848, None)
