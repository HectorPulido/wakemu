"""Initialized undead damage uses ordinary consumption and clone continuations."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_runner_target import bind_runner_target
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
from wakfu_server.combat_undead_healing import apply_undead_healing


class InitializedUndeadDamageTests(unittest.TestCase):
    def test_current_catalogue_uses_reexported_facts_and_rejects_foreign_revision(self):
        from wakfu_server import native_catalog
        from wakfu_server.combat_undead_native_facts import (
            NATIVE_CATALOG_REVISION,
            original_fkk,
        )

        self.assertEqual(native_catalog.release(), NATIVE_CATALOG_REVISION)
        # Original aNw/bcA/eVn export witnesses, not family-derived defaults.
        for reference, flag in (
            (223, True),
            (4778, False),
            (419077, False),
            (-11, True),
            (-3, True),
            (-8, False),
            (-12, False),
        ):
            with self.subTest(reference=reference):
                self.assertIs(original_fkk(reference), flag)
        with self.assertRaisesRegex(ValueError, "Unknown native FKK"):
            original_fkk(1)
        with patch(
            "wakfu_server.native_catalog.release",
            return_value="72c33b9d9a94d6e4e913399e5e3c6b28db939227e926f237572e720b1170fd48",
        ):
            with self.assertRaisesRegex(ValueError, "another catalogue revision"):
                original_fkk(223)

    def test_conversion_consumption_properties_and_calculated_transfer(self):
        for scenario in ("absorption", "calculated", "property75", "transfer"):
            with self.subTest(scenario=scenario):
                actors = [
                    Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True, max_hp=100),
                    Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1, max_hp=100),
                    Actor(-8, 1, (2, 0, 0), 100, 6, 3, 4, 1, max_hp=100),
                ]
                fight = Fight(
                    77,
                    actors,
                    {a.position for a in actors},
                    {
                        0: {actors[0].position},
                        1: {a.position for a in actors[1:]},
                    },
                )
                fight.ready(3)
                for actor in actors:
                    # Huge mastery/resistance must not recalculate a supplied amount.
                    actor.effect_stats = {
                        92: 0,
                        97: 0,
                        100: 0,
                        32: 0,
                        21: 10000,
                        26: 10000,
                    }
                    actor.effect_maxima = {92: 0}
                    actor.effect_frozen = frozenset()
                    actor.physical_radius = 0
                if scenario == "absorption":
                    actors[0].effect_stats[100] = 3
                    actors[1].effect_stats.update({97: 7, 92: 5})
                    actors[1].effect_maxima[92] = 5
                packets, phases, split = [], [], []

                class Events:
                    def phase(self, effect, invocation, **data):
                        self.definition(effect, invocation)
                        self.identifiers(effect, invocation)
                        phases.append(data["channel"])
                        if (
                            scenario == "transfer"
                            and data["channel"] == 2
                            and not split
                        ):
                            split.append(True)
                            runner = data["runner_modifier"]
                            continuation = runner.native_calculated_clone.prepare(
                                caster_id=7,
                                target_id=-8,
                                amount=10,
                            )
                            runner.set_calculated(15)
                            assert continuation.execute()

                allocate = iter(range(100, 200)).__next__
                healing = SimpleNamespace(
                    fight=fight,
                    packets=packets,
                    action_id=2,
                    allocate_uid=allocate,
                    rng=lambda: self.fail("Initialized conversion rerolled RNG"),
                    retention=SimpleNamespace(
                        definition=lambda *args: {
                            "event_suppresses_level_one": False,
                        }
                    ),
                )
                damage = NativeDamageHandler(
                    fight,
                    packets,
                    action_id=2,
                    allocate_uid=allocate,
                    context=lambda *args: DamageExecutionContext(
                        True, True, True, True, None, False, "FRONT"
                    ),
                    rng=healing.rng,
                )
                damage.event_lifecycle = Events()

                def clone_gate(source, invocation):
                    source.verify(source.effect, invocation)
                    self.assertLessEqual(
                        source.original["minimum_level"], invocation.level
                    )
                    self.assertGreaterEqual(
                        source.original["maximum_level"], invocation.level
                    )
                    return True

                damage.calculated_clone_gate = clone_gate
                invocation = EffectInvocation(
                    416674, 20, 7, -7, (1, 0, 0), native_running_uid=77
                )
                runner = NativeRunnerAmount(77, 24, rng=healing.rng)
                runner.set_calculated(25)
                bind_runner_target(runner, invocation)
                authority = SimpleNamespace(
                    property_counts=lambda *args: {75: 1}
                    if scenario == "property75"
                    else {}
                )
                with patch(
                    "wakfu_server.combat_undead_native_facts.original_fkk",
                    return_value=True,
                ):
                    apply_undead_healing(
                        healing,
                        damage,
                        {"effect_class": 24, "native_effect_flags": []},
                        invocation,
                        25,
                        runner,
                        actor_authority=authority,
                    )
                self.assertTrue(runner.notification_suppressed)
                self.assertEqual(runner.value, 25)
                if scenario == "property75":
                    self.assertEqual((actors[1].hp, packets, phases), (100, [], []))
                elif scenario == "absorption":
                    self.assertEqual(actors[1].hp, 90)
                    self.assertEqual(
                        (actors[1].effect_stats[97], actors[1].effect_stats[92]), (0, 0)
                    )
                    self.assertEqual(phases, [2, 3, 4])
                elif scenario == "transfer":
                    self.assertEqual((actors[1].hp, actors[2].hp), (85, 90))
                    self.assertEqual(
                        [_identity_fields(body[19:])[4] for _, body in packets],
                        [10, 15],
                    )
                else:
                    self.assertEqual(actors[1].hp, 75)
                    self.assertEqual(_identity_fields(packets[0][1][19:])[4], 25)
