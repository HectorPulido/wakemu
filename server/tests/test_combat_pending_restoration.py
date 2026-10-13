"""Focused server-policy unit contracts; not a native monster qualification."""
import importlib.util
import sys
import types
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "wakfu_server/combat"
PACKAGE = "_pending_policy_contract"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT), str(Path.cwd() / "server/wakfu_server/combat")]
sys.modules[PACKAGE] = package


def load(name):
    spec = importlib.util.spec_from_file_location(
        PACKAGE + "." + name, ROOT / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


policy = load("combat_pending_restoration")
# The traversal is isolated from arithmetic: evaluated values are explicit inputs
# here; actual native rows are reserved for the end-to-end representative probe.
definitions = types.ModuleType(PACKAGE + ".combat_definitions")
definitions.effect_profile = lambda effect, level: {"parameters": effect["evaluated"]}
sys.modules[definitions.__name__] = definitions


class PendingRestorationTests(unittest.TestCase):
    def fight(self):
        from importlib import import_module

        queue = import_module(PACKAGE + ".combat_native_delay_queue")
        invocation = dict(reference=10, target_id=-7, caster_id=-8, level=20)
        owned = dict(invocation=deepcopy(invocation), native_delayed=True)
        fight = types.SimpleNamespace(
            actors={-7: types.SimpleNamespace(id=-7, hp=0)},
            native_delay_queue=queue.fresh_queue(),
            native_owned_group_effects={3: owned},
        )
        queue.enqueue(
            fight.native_delay_queue,
            uid=3,
            clock_id=-8,
            delay=3,
            expire_at_end=False,
            current_round=1,
            on_clock_turn=True,
            clock_not_reached=False,
            invocation=invocation,
        )
        effects = {
            "10": dict(
                effect_class=330,
                minimum_level=0,
                maximum_level=32767,
                evaluated=[0, 0],
                parameters=[0.0, 0.0],
                children=[11],
            ),
            "11": dict(
                effect_class=196,
                minimum_level=0,
                maximum_level=32767,
                evaluated=[50],
                parameters=[50.0, 0.0],
                children=[],
            ),
        }
        return fight, effects

    def test_actual_queue_and_owned_same_target_required(self):
        fight, effects = self.fight()
        self.assertTrue(policy.annotate_scheduled_restoration(fight, effects, 3))
        self.assertEqual(policy.pending_restoration_uids(fight, -7), (3,))
        self.assertEqual(policy.pending_restoration_uids(fight, -8), ())
        fight.native_owned_group_effects.clear()
        self.assertEqual(policy.pending_restoration_uids(fight, -7), ())

    def test_rebound_or_nonpositive_restore_is_not_authority(self):
        for parameters in ([0, 0, 1, 0, 1, 1], [0, 0, 0]):
            fight, effects = self.fight()
            effects["10"]["evaluated"] = parameters
            effects["10"]["parameters"] = [float(x) for v in parameters for x in (v, 0)]
            self.assertFalse(policy.annotate_scheduled_restoration(fight, effects, 3))
        fight, effects = self.fight()
        effects["11"]["evaluated"] = [0]
        self.assertFalse(policy.annotate_scheduled_restoration(fight, effects, 3))

    def test_missing_definition_and_handle_mismatch_fail_closed(self):
        fight, effects = self.fight()
        del effects["11"]
        with self.assertRaisesRegex(ValueError, "definition"):
            policy.annotate_scheduled_restoration(fight, effects, 3)
        fight, effects = self.fight()
        fight.native_owned_group_effects[3]["invocation"]["target_id"] = -8
        with self.assertRaisesRegex(ValueError, "scheduled owned"):
            policy.annotate_scheduled_restoration(fight, effects, 3)

    def test_cancel_or_exhaustion_publishes_final_once(self):
        death = types.ModuleType(PACKAGE + ".combat_death")
        calls = []
        death.death_messages = lambda runtime, identity, *, fighter_state: calls.append(
            (identity, fighter_state)
        ) or [(12727, b"final")]
        sys.modules[death.__name__] = death
        fight, effects = self.fight()
        policy.annotate_scheduled_restoration(fight, effects, 3)
        actor = fight.actors[-7]
        actor.native_death_status = {"pending_restoration": policy.SOURCE}
        runtime = types.SimpleNamespace(fight=fight)
        self.assertEqual(policy.settle_pending_restoration_deaths(runtime), ())
        fight.native_delay_queue["entries"].clear()
        self.assertEqual(
            policy.settle_pending_restoration_deaths(runtime), ((12727, b"final"),)
        )
        self.assertEqual(policy.settle_pending_restoration_deaths(runtime), ())
        self.assertEqual(calls, [(-7, 2)])

    def test_actual_death_publisher_default_ko_and_explicit_final_override(self):
        file = ROOT / "combat_death.py"
        spec = importlib.util.spec_from_file_location(PACKAGE + ".combat_death", file)
        death = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = death
        spec.loader.exec_module(death)
        retirement = types.ModuleType(PACKAGE + ".combat_ordinary_qi_retirement")
        calls = []
        retirement.complete_ordinary_qi_death = (
            lambda fight, actor, *, fighter_state: calls.append(fighter_state)
        )
        sys.modules[retirement.__name__] = retirement
        fight, effects = self.fight()
        fight.id = 77
        policy.annotate_scheduled_restoration(fight, effects, 3)
        actor = fight.actors[-7]
        actor.controlled = False
        actor.native_death_status = {
            "source": "fresh.bjm.constructor",
            "actor_kind": "bje",
            "mwD": False,
            "dtM_status": None,
            "last_writer": "fresh.bjm.constructor",
        }
        actor.native_world_properties = frozenset()

        class Runtime:
            def __init__(self):
                self.fight = fight
                self.action_id = 1

            def _prefix(self):
                return b"\x00" * 12

            def _flush(self):
                return (13420, b"flush")

        runtime = Runtime()
        packets = death.death_messages(runtime, -7)
        self.assertEqual(packets[0][1][-1], 0)
        self.assertEqual(
            actor.native_death_status["pending_restoration"], policy.SOURCE
        )
        final = death.death_messages(runtime, -7, fighter_state=2)
        self.assertEqual(final[0][1][-1], 2)
        self.assertNotIn("pending_restoration", actor.native_death_status)
        self.assertEqual(calls, [2])
        self.assertEqual(policy.settle_pending_restoration_deaths(runtime), ())

    def test_revival_clears_barrier_without_final_publication(self):
        fight, effects = self.fight()
        policy.annotate_scheduled_restoration(fight, effects, 3)
        actor = fight.actors[-7]
        actor.hp = 88
        actor.native_death_status = {"pending_restoration": policy.SOURCE}
        runtime = types.SimpleNamespace(fight=deepcopy(fight))
        self.assertEqual(policy.settle_pending_restoration_deaths(runtime), ())
        self.assertNotIn(
            "pending_restoration", runtime.fight.actors[-7].native_death_status
        )
        self.assertIn("pending_restoration", actor.native_death_status)


if __name__ == "__main__":
    unittest.main()
