"""Real Tipsy application and Cyanosis conversion on owned turn boundaries."""
import os
import unittest
from unittest.mock import patch
import test_combat_pandawa_runtime as fixture_module


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaPoisonRuntimeTests(unittest.TestCase):
    fixture = fixture_module.PandawaRuntimeTests.fixture
    cast = fixture_module.PandawaRuntimeTests.cast
    next_owned_turn = fixture_module.PandawaRuntimeTests.next_owned_turn

    def test_cyanosis_converts_real_enemy_tipsy_and_ticks_without_baseline_poison(self):
        from wakfu_server import combat_server_spell

        for passive in (None, 5149):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                applied = self.cast(
                    fixture, 8592, target=fixture[2].actors[-7].position
                )
                fixture = (*fixture[:2], applied.fight, *fixture[3:])
                self.assertIn(
                    6107,
                    {
                        entry.reference
                        for entry in fixture[2].actors[-7].state_ledger.entries
                    },
                )
                before_hp = fixture[2].actors[-7].hp
                original = combat_server_spell.prepare_server_turn_end
                observed = []

                def observe_end(*args, **kwargs):
                    result = original(*args, **kwargs)
                    if kwargs["actor_id"] == 7:
                        observed.append(
                            {
                                entry.reference
                                for entry in result[0].actors[-7].state_ledger.entries
                            }
                        )
                    return result

                with patch.object(
                    combat_server_spell, "prepare_server_turn_end", observe_end
                ):
                    fixture = self.next_owned_turn(fixture)
                self.assertEqual(len(observed), 1)
                if passive == 5149:
                    self.assertIn(3690, observed[0])
                    # Native end418059 installs poison; state3690's start
                    # root160735 later removes6107 through child418074.
                    self.assertNotIn(
                        6107,
                        {
                            entry.reference
                            for entry in fixture[2].actors[-7].state_ledger.entries
                        },
                    )
                    self.assertLess(fixture[2].actors[-7].hp, before_hp)
                else:
                    self.assertNotIn(3690, observed[0])
                    self.assertEqual(fixture[2].actors[-7].hp, before_hp)
