"""The actual advisory facade batches static inputs, never current actor state."""
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import wakfu_server
from wakfu_ai.bridge.actor_casting_metadata import CostMetadata
from wakfu_ai.bridge.actor_repertoires import actor_repertoires
from wakfu_ai.bridge.world_bridge import _advisory_spell_capabilities


class ActorRepertoirePreparationTests(unittest.TestCase):
    def test_real_wrapper_prepares_complete_owned_books_and_preserves_failures_and_modifiers(
        self,
    ):
        engine = ModuleType("wakfu_server.combat_ai_capabilities")
        prepared, calls = [], []
        engine.prepare_spell_capabilities = lambda pairs: prepared.append(pairs)
        engine.describe_spell = lambda spell, level: dict(
            spellId=spell, level=level, tags=[]
        )

        def owned(_fight, identity):
            calls.append(identity)
            if identity == 4:
                raise ValueError("Unavailable owned metadata")
            return {identity * 100: identity + 10}

        oracle = SimpleNamespace(owned_spells=owned)
        actors = [
            dict(id=identity, hp=0 if identity == 3 else 10)
            for identity in (1, 2, 3, 4)
        ]
        fight = SimpleNamespace(
            sequence=7,
            actors={
                identity: SimpleNamespace(spell_ap_cost_modifiers={9: 0})
                for identity in (1, 2, 3, 4)
            },
        )

        def book(callback):
            return actor_repertoires(
                oracle,
                fight,
                actors,
                source_state="complete-source",
                capabilities=callback,
            )

        with patch.dict(
            "sys.modules", {"wakfu_server.combat_ai_capabilities": engine}
        ), patch.object(
            wakfu_server, "combat_ai_capabilities", engine, create=True
        ), patch(
            "wakfu_ai.bridge.actor_casting_metadata.selected_cost_metadata",
            return_value=CostMetadata(((4, 0, 0),), (9,), False),
        ):
            expected = book(
                lambda spell, level: _advisory_spell_capabilities(spell, level)
            )
            self.assertFalse(prepared)
            actual = book(_advisory_spell_capabilities)
            self.assertEqual(actual, expected)
            self.assertEqual(prepared, [((100, 11), (200, 12))])
            self.assertEqual(calls, [1, 2, 4, 1, 2, 4])
            self.assertNotIn("3", actual)
            self.assertEqual(
                actual["4"]["unknownDependencies"], ["owned_spell_metadata_unavailable"]
            )
            self.assertEqual(actual["1"]["sourceState"], "complete-source")
            self.assertEqual(actual["1"]["stateRevision"], 7)
            fight.actors[1].spell_ap_cost_modifiers[9] = -2
            again = book(_advisory_spell_capabilities)
            self.assertEqual(
                again["1"]["spells"][0]["costOptions"], [dict(ap=2, mp=0, wp=0)]
            )
            # Older engines and empty ownership retain the ordinary path.
            del engine.prepare_spell_capabilities
            self.assertEqual(book(_advisory_spell_capabilities), again)
            engine.prepare_spell_capabilities = Mock(
                side_effect=AssertionError("No empty preparation")
            )
            oracle.owned_spells = lambda *_: {}
            self.assertTrue(book(_advisory_spell_capabilities))
            engine.prepare_spell_capabilities.assert_not_called()
