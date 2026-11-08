"""Fresh actor validity with callback-local immutable spell definition decoding."""
from contextlib import nullcontext
import json
import sys
import unittest
from unittest.mock import patch
from test_combat_ordinary_phase_read_pass import PhaseReadPassSemanticTests
from wakfu_server import combat_ordinary_authority as authority_module
from wakfu_server import combat_spell_level
from wakfu_server.combat_ordinary_events import _phase_read_pass
from wakfu_server.combat_native_spell_casting import catalog


class OrdinaryBaseSpellbookScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PhaseReadPassSemanticTests.setUpClass()

    def fixture(self):
        case = PhaseReadPassSemanticTests().fixture()
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
            None
        ] * 7
        return case

    def phase(self, reuse):
        case = self.fixture()
        decoder = combat_spell_level.decoded_spell_levels
        calls = []

        def observe(frame, event, arg):
            if event == "call" and frame.f_code is decoder.__code__:
                calls.append(1)

        previous = sys.getprofile()
        scope = (
            nullcontext()
            if reuse
            else patch.object(
                authority_module,
                "_phase_base_spell_levels",
                lambda owner, preview, records, definitions: decoder(
                    records, definitions
                ),
            )
        )
        try:
            sys.setprofile(observe)
            with scope:
                result = case.events.phase(
                    case.effect, case.inv, uid=800, value=1, channel=3, _event_ids=()
                )
        finally:
            sys.setprofile(previous)
        return (result, tuple(case.f.packets)), len(calls)

    def test_actual_phase_hits_fresh_inputs_outputs_callbacks_and_custom_fallback(self):
        baseline, original_calls = self.phase(False)
        candidate, reused_calls = self.phase(True)
        self.assertEqual(candidate, baseline)
        self.assertGreater(original_calls, reused_calls)
        self.assertGreater(reused_calls, 0)
        print(
            json.dumps(
                {
                    "actual_phase_baseline_decodes": original_calls,
                    "actual_phase_candidate_decodes": reused_calls,
                    "actual_phase_reused_decodes": original_calls - reused_calls,
                }
            )
        )

        case = self.fixture()
        owner = case.adapter.actor_authority
        actor = case.fight.actors[7]
        source = owner.characters[7]
        with _phase_read_pass(case.events, case.inv):
            first = owner(case.fight, actor).native_spellbook
            saved = dict(first.levels)
            first.levels.clear()
            second = owner(case.fight, actor).native_spellbook
            self.assertEqual(second.levels, saved)
            source["level"] += 1
            owner.deck_caps[7] = source["level"]
            changed = owner(case.fight, actor).native_spellbook
            self.assertNotEqual(changed.levels, saved)
            self.assertEqual(changed.deck_cap, owner.deck_caps[7])
            with case.replay._callback_read_boundary():
                source["level"] += 1
            refreshed = owner(case.fight, actor).native_spellbook
            self.assertNotEqual(refreshed.levels, changed.levels)
            actor.native_master_id = 999
            with self.assertRaisesRegex(ValueError, "changed native relationships"):
                owner(case.fight, actor)
            actor.native_master_id = None

            records = ((1, 6266, 10),)
            custom = {"6266": {"maximum_level": 8}}
            self.assertEqual(
                authority_module._phase_base_spell_levels(
                    owner, case.fight, records, custom
                ),
                {6266: 8},
            )
            custom["6266"]["maximum_level"] = 9
            self.assertEqual(
                authority_module._phase_base_spell_levels(
                    owner, case.fight, records, custom
                ),
                {6266: 9},
            )
            with patch.object(
                combat_spell_level, "decoded_spell_levels", return_value={6266: 3}
            ) as replacement:
                for _ in range(2):
                    self.assertEqual(
                        authority_module._phase_base_spell_levels(
                            owner, case.fight, records, catalog()
                        ),
                        {6266: 3},
                    )
                self.assertEqual(replacement.call_count, 2)


if __name__ == "__main__":
    unittest.main()
