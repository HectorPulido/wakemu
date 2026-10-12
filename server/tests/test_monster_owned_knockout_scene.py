"""KO scene orchestration contract; native runtime qualification is separate."""
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as N
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_knockout_scenarios import knock_out_ally


class OwnedKnockoutSceneTests(unittest.TestCase):
    def fixture(self, *, damage=4, flags=None, owned=True):
        actors = {
            7: N(id=7, controlled=True, hp=6, position=(1, 0, 0), native_obstacle_id=0),
            -1: N(id=-1, controlled=False, hp=20, effective_level=1),
            -2: N(id=-2, controlled=False, hp=20),
        }
        fight = N(
            actors=actors,
            turn_id=1,
            commits=[],
            events=[],
            prepare_delivery=lambda packets: packets,
        )
        modules = {}

        def module(name, **items):
            obj = ModuleType(name)
            obj.__dict__.update(items)
            modules[name] = obj

        def advance(state, identity):
            state.current = state.actors[identity]

        def commit(runtime, action, serialize):
            self.assertEqual(
                action,
                dict(type="cast", spellId=100, level=1, target=[1, 0, 0], targetId=7),
            )
            runtime.commits.append((runtime.current.id, action))
            actors[7].hp = max(0, actors[7].hp - damage)
            actors[7].native_death_status = dict(last_writer="owned.aTS.F.type0")
            return [b"actual-commit-receipt"]

        module(
            "monster_spell_scenarios",
            advance_to=advance,
            finish_current_turn=lambda state: setattr(
                state, "turn_id", state.turn_id + 1
            ),
        )
        module(
            "wakfu_server.combat_tactical_ai",
            NativeProvider=lambda *args: N(commit=commit),
        )
        module(
            "wakfu_server.combat_runtime_messages", RuntimeMessages=lambda state: state
        )
        module(
            "wakfu_server.combat_death",
            death_messages=lambda runtime, identity: [(12727, b"\x00")],
        )
        module(
            "wakfu_server.combat_actor",
            actual_actor_stats=None,
            actual_monster_actor_stats=None,
        )
        module(
            "wakfu_server.combat_controller_registry",
            current_native_team=lambda state, i: int(i != -1),
        )
        module(
            "wakfu_server.combat_global_pv_collections",
            global_fighter_guards=lambda *a: flags
            or dict(baF=False, baG=True, baK=False),
        )
        module(
            "wakfu_server.combat_ordinary_death",
            registered_ordinary_death=lambda state, actor: actor.hp == 0,
        )
        module(
            "wakfu_server.combat_qi_fight",
            current_registry=lambda state: N(
                slots=[dict(identity=["actor", 7], position=[1, 0])]
            ),
        )
        module(
            "wakfu_server.monsters",
            native_abilities=lambda *a: [dict(spell_id=100, spell_level=1)]
            if owned
            else [],
        )
        return fight, modules

    def run_scene(self, fight, modules, **kwargs):
        with patch.dict(sys.modules, modules):
            return knock_out_ally(
                fight,
                {},
                {-1: dict(ref=4)},
                b"",
                attacker_id=-1,
                ally_id=7,
                caster_id=-2,
                spell_id=100,
                spell_level=1,
                **kwargs
            )

    def test_only_owned_commits_reduce_hp_and_establish_caster_turn(self):
        fight, modules = self.fixture()
        receipt = self.run_scene(fight, modules)
        self.assertEqual(len(fight.commits), 2)
        self.assertEqual([step["hp_after"] for step in receipt["preparations"]], [2, 0])
        self.assertEqual(fight.current.id, -2)
        self.assertEqual(receipt["hp_before"], 6)
        self.assertEqual(
            receipt["preparations"][-1]["ko_delivery"],
            [dict(opcode=12727, payload_hex="00")],
        )

    def test_unowned_spell_rejected_before_any_commit(self):
        fight, modules = self.fixture(owned=False)
        with self.assertRaisesRegex(ValueError, "natively owned"):
            self.run_scene(fight, modules)
        self.assertEqual(fight.commits, [])
        self.assertEqual(fight.actors[7].hp, 6)

    def test_bounded_nonlethal_and_no_damage_never_fabricate_ko(self):
        for damage, message in ((1, "cast budget"), (0, "did not damage")):
            fight, modules = self.fixture(damage=damage)
            with self.assertRaisesRegex(ValueError, message):
                self.run_scene(fight, modules, maximum_casts=2)
            self.assertGreater(fight.actors[7].hp, 0)

    def test_numeric_zero_without_actual_offplay_registration_is_rejected(self):
        fight, modules = self.fixture(flags=dict(baF=True, baG=False, baK=False))
        with self.assertRaisesRegex(ValueError, "reversible native KO"):
            self.run_scene(fight, modules)


if __name__ == "__main__":
    unittest.main()
