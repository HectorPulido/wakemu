"""World candidate generation retains an explicit reversible KO recipient."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_tactical_ai import NativeProvider


class NPCRetainedCastRecipientTests(unittest.TestCase):
    def test_native_revive_candidate_includes_retained_ko_identity(self):
        source = SimpleNamespace(
            id=-200, hp=20, max_hp=20, mp=0, position=(0, 0, 0), team=1
        )
        target = SimpleNamespace(id=7, hp=0, max_hp=60, position=(1, 0, 0), team=1)
        fight = SimpleNamespace(
            phase="active",
            current=source,
            actors={source.id: source, target.id: target},
            edges={((0, 0, 0), (1, 0, 0))},
        )
        provider = NativeProvider({}, {}, b"")
        capability = dict(spellId=6169, level=1, minimum=1, maximum=3, tags=["heal"])
        with patch.object(provider, "capabilities", return_value=[capability]), patch(
            "wakfu_server.combat_tactical_ai.effective_server_controlled",
            return_value=True,
        ), patch(
            "wakfu_server.combat_tactical_ai.effective_affiliation",
            side_effect=lambda fight, actor: actor.team,
        ), patch(
            "wakfu_server.combat_tactical_ai._distances",
            return_value={(0, 0, 0): (0, [(0, 0, 0)])},
        ), patch(
            "wakfu_server.combat_ai_capabilities.target_affinity", return_value=0
        ):
            actions = list(provider.actions(fight))
        self.assertIn(
            dict(type="cast", spellId=6169, level=1, targetId=7, target=[1, 0, 0]),
            actions,
        )


if __name__ == "__main__":
    unittest.main()
