"""Native validation companions retain exact team and state prerequisites."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_pending_scenarios import prepare_scenario, scenario_recipes


class MonsterNativeCompanionScenariosTests(unittest.TestCase):
    def fixture(self, *, reference=1987, level=95, team=1, states=(7318,)):
        caster = SimpleNamespace(id=-200, team=1)
        companion = SimpleNamespace(
            id=-201,
            team=team,
            effective_level=level,
            state_ledger=SimpleNamespace(
                entries=[SimpleNamespace(reference=s) for s in states]
            ),
        )
        return SimpleNamespace(
            current=caster, actors={-200: caster, -201: companion}, turn_id=2
        ), {-201: dict(ref=reference)}

    def prepare(self, fight, monsters, recipe):
        # This narrow scenario has no action. Constructor and spell execution
        # are covered by native acceptance; isolate the prerequisite gate here.
        with patch(
            "wakfu_server.combat_tactical_ai.NativeProvider", return_value=object()
        ):
            return prepare_scenario(fight, {}, monsters, b"", recipe=recipe)

    def test_luna_accepts_native_ally_with_actual_required_state(self):
        fight, monsters = self.fixture()
        receipt = self.prepare(fight, monsters, scenario_recipes(5361, 7527)[0])
        self.assertEqual(receipt["preparations"], [])
        self.assertEqual(receipt["caster_turn_id"], 2)
        self.assertEqual(fight.actors[-201].team, fight.actors[-200].team)

    def test_luna_rejects_native_reference_on_wrong_team(self):
        fight, monsters = self.fixture(team=0)
        with self.assertRaisesRegex(ValueError, "companion was not initialized"):
            self.prepare(fight, monsters, scenario_recipes(5361, 7527)[0])

    def test_luna_rejects_missing_native_state_without_manufacturing_it(self):
        fight, monsters = self.fixture(states=())
        with self.assertRaisesRegex(ValueError, "required native initial state"):
            self.prepare(fight, monsters, scenario_recipes(5361, 7527)[0])
        self.assertEqual(fight.actors[-201].state_ledger.entries, [])

    def test_seed_preserves_default_enemy_team_and_rejects_allied_seed(self):
        recipe = scenario_recipes(3907, 5599)[0]
        fight, monsters = self.fixture(reference=3907, level=1, team=0, states=())
        self.assertEqual(
            self.prepare(fight, monsters, recipe)["kind"], "native_opponent"
        )
        fight.actors[-201].team = 1
        with self.assertRaisesRegex(ValueError, "companion was not initialized"):
            self.prepare(fight, monsters, recipe)
