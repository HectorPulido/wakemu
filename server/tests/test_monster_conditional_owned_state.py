"""Pure discovery and real-transaction receipt guards; no engine replay."""
import copy, json, sys, unittest
from pathlib import Path
from types import SimpleNamespace as NS

H = Path(__file__).resolve().parent / "fixtures/conditional_owned_state"
from conditional_owned_state import (
    discover_conditional_owned_state_recipes as discover,
    guarded_native_provider,
    verify_state_transaction,
    verify_committed_states,
)


class ConditionalStateTests(unittest.TestCase):
    def setUp(self):
        self.proof = json.loads((H / "actual2350-proof.json").read_text())
        self.doc = copy.deepcopy(self.proof["document"])
        self.abilities = self.proof["abilities"]
        self.recipe = discover(self.abilities, [1721], self.doc)[0]

    def test_actual2350_conditional_mask3_source_proof(self):
        p = next(p for p in self.recipe["native_producer_paths"] if p["state"] == 1721)
        self.assertEqual(p["effect_ids"], [339048, 339049])
        self.assertEqual(p["native_selector"], {"class": "fcE", "mask": 3})
        self.assertEqual(
            p["criteria"],
            [
                {
                    "effect_id": 339048,
                    "criterion": 'GetStateCountInRange(-1, "caster", 7486) == 0',
                }
            ],
        )
        self.assertEqual(
            self.doc["spells"]["3467"]["levels"][109],
            [0, 0, [86749, 86751, 339048, 339051]],
        )

    def test_unowned_producer_not_discovered(self):
        self.assertEqual(discover([], [1721], self.doc), [])

    def test_enemy_mask_cannot_supply_self_state(self):
        self.doc["effects"]["339049"]["native_target_selector"]["mask"] = 9
        self.assertEqual(discover(self.abilities, [1721], self.doc), [])

    def test_only_actual_zero_range_native_spell_is_candidate(self):
        self.doc["spells"]["3467"]["levels"][109][1] = 1
        self.assertEqual(discover(self.abilities, [1721], self.doc), [])

    def test_unknown_selector_fails_closed(self):
        self.doc["effects"]["339049"]["native_target_selector"] = {
            "class": "unknown",
            "mask": 3,
        }
        self.assertEqual(discover(self.abilities, [1721], self.doc), [])

    def test_context_changing_group_not_guessed(self):
        self.doc["effects"]["339048"]["effect_class"] = 349
        self.assertEqual(discover(self.abilities, [1721], self.doc), [])

    def test_bounded_recipe_count_and_no_action_grants(self):
        recipes = discover(self.abilities, [1721], self.doc, limit=1)
        self.assertEqual(len(recipes), 1)
        self.assertEqual(
            recipes[0]["actions"],
            [{"spell_id": 3467, "target": "caster", "next_turn": False}],
        )

    def scene(self, applied=True):
        actor = NS(state_ledger=NS(entries=[]))
        source = NS(actors={-200: actor})
        entry = NS(uid=99, reference=1721, level=1, target_id=-200, caster_id=-200)
        target = NS(
            actors={-200: NS(state_ledger=NS(entries=[entry] if applied else []))}
        )
        event = {
            "kind": "state_applied",
            "state_id": 1721,
            "actor_id": -200,
            "source_id": -200,
            "uid": 99,
        }
        preview = NS(
            fight=target,
            spell=NS(
                outcomes=(True,) if applied else (False,),
                events=(event,) if applied else (),
            ),
        )
        action = {"type": "cast", "spellId": 3467, "level": 110, "targetId": -200}
        return source, preview, action

    def test_actual_conditional_true_transaction_state_and_event_required(self):
        source, preview, action = self.scene()
        proof = verify_state_transaction(source, preview, self.recipe, action, -200)
        self.assertEqual(proof, [{"state_id": 1721, "uid": 99, "level": 1}])
        self.assertEqual(source.actors[-200].state_ledger.entries, [])
        self.assertEqual(verify_committed_states(preview.fight, proof, -200), proof)

    def test_actual_conditional_false_rejects_before_commit_adoption(self):
        source, preview, action = self.scene(False)
        with self.assertRaisesRegex(ValueError, "did not apply"):
            verify_state_transaction(source, preview, self.recipe, action, -200)
        self.assertEqual(source.actors[-200].state_ledger.entries, [])

    def test_existing_state_without_new_root_outcome_not_proof(self):
        source, preview, action = self.scene()
        source.actors[-200].state_ledger.entries = preview.fight.actors[
            -200
        ].state_ledger.entries
        with self.assertRaisesRegex(ValueError, "prior state UID"):
            verify_state_transaction(source, preview, self.recipe, action, -200)

    def test_wrong_producer_or_target_does_not_commit(self):
        source, preview, action = self.scene()
        action["spellId"] = 999
        with self.assertRaisesRegex(ValueError, "ownership"):
            verify_state_transaction(source, preview, self.recipe, action, -200)
        action["spellId"] = 3467
        action["targetId"] = 7
        with self.assertRaisesRegex(ValueError, "ownership"):
            verify_state_transaction(source, preview, self.recipe, action, -200)

    def test_missing_root_outcome_fails_closed(self):
        source, preview, action = self.scene()
        preview.spell.outcomes = ()
        with self.assertRaisesRegex(ValueError, "root outcomes"):
            verify_state_transaction(source, preview, self.recipe, action, -200)

    def test_guard_uses_one_real_preview_and_preserves_criterion_failure(self):
        source, preview, action = self.scene()
        calls = []

        class Base:
            def preview(self, fight, action, action_id, *, forecast):
                calls.append((action_id, forecast))
                return preview

        provider = guarded_native_provider(Base, self.recipe, -200)()
        self.assertIs(provider.preview(source, action, 1, forecast=False), preview)
        self.assertEqual(calls, [(1, False)])

        class Rejected:
            def preview(self, *a, **kw):
                raise ValueError("actual native criterion rejected")

        with self.assertRaisesRegex(ValueError, "actual native criterion"):
            guarded_native_provider(Rejected, self.recipe, -200)().preview(
                source, action, 1, forecast=False
            )

    def test_post_commit_or_next_turn_expiry_not_certified(self):
        source, preview, action = self.scene()
        proof = verify_state_transaction(source, preview, self.recipe, action, -200)
        with self.assertRaisesRegex(ValueError, "Committed"):
            verify_committed_states(source, proof, -200)


if __name__ == "__main__":
    unittest.main()
