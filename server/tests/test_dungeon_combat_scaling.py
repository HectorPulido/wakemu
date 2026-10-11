"""Qualified local Stasis policy: only native HP and conditional value roots."""
import unittest
from copy import deepcopy
from contextlib import nullcontext
from types import SimpleNamespace

from wakfu_server.maps import dungeon_combat_scaling as scaling
from wakfu_server.combat.combat_state import Actor
from wakfu_server.combat.combat_summon_initialization import detached_actor


class ScalingTests(unittest.TestCase):
    def setUp(self):
        self.actor = Actor(-3, 1, (0, 0, 0), 100, 6, 3, 1, 5)
        self.actor.native_world_properties = frozenset()
        self.actor.native_fight_properties = frozenset()
        self.fight = SimpleNamespace(
            id=7,
            phase="placement",
            actors={-3: self.actor},
            effect_resolution=lambda: nullcontext(),
        )
        self.monsters = {-3: {"ref": 1}}
        self.snapshot = dict(
            schema_version=1,
            instance_id=123,
            selection_revision=4,
            stasis_level=4,
            competitive=True,
            competitive_max_level=20,
            hp_percent=210,
            damage_percent=190,
            reward_rate_bp=25000,
        )
        self.catalog = dict(
            schema_version=1,
            policy=scaling.POLICY,
            hp={"210": 330890},
            damage={"190": [330891, 330893]},
            effects={
                "330890": {"effect_class": 16},
                "330891": {"effect_class": 330},
                "330893": {"effect_class": 330},
            },
        )
        self.db = SimpleNamespace(
            execute=lambda *args: SimpleNamespace(
                fetchone=lambda: {"snapshot": self.snapshot}
            )
        )

    def test_native_plan_keeps_conditional_branches_and_excludes_whole_states(self):
        selected = scaling.plan(self.fight, self.monsters, self.snapshot, self.catalog)
        self.assertEqual(selected.references, (330890, 330891, 330893))
        self.assertEqual(selected.actor_ids, (-3,))
        self.assertEqual(selected.profile, self.snapshot)
        self.snapshot["hp_percent"] = 9999
        self.assertEqual(selected.profile["hp_percent"], 210)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            scaling.plan(self.fight, self.monsters, self.snapshot, self.catalog)

    def test_default_percentages_need_no_native_effects(self):
        selected = scaling.plan(
            self.fight,
            self.monsters,
            dict(self.snapshot, hp_percent=100, damage_percent=100),
            self.catalog,
        )
        self.assertEqual(selected.references, ())

    def test_failure_after_first_native_branch_does_not_mutate_original_actor(self):
        seen = []

        def runtime(preview, identity):
            actor = detached_actor(preview, identity)
            self.assertIsNotNone(actor)
            self.assertNotIn(identity, preview.actors)

            def execute(invocation):
                seen.append(invocation.reference)
                actor.hp = 1
                if len(seen) == 2:
                    raise ValueError("unsupported native trigger metadata")
                return True

            return SimpleNamespace(execute=execute)

        with self.assertRaisesRegex(ValueError, "trigger metadata"):
            scaling.initialize(
                self.db,
                self.fight,
                self.monsters,
                catalog=self.catalog,
                runtime_factory=runtime,
            )
        self.assertEqual(self.actor.hp, 100)
        self.assertEqual(tuple(self.fight.actors), (-3,))
        self.assertFalse(hasattr(self.fight, "native_dungeon_scaling_receipt"))

    def test_success_freezes_receipt_and_replay_does_not_apply_again(self):
        calls = []

        def runtime(preview, identity):
            return SimpleNamespace(
                execute=lambda invocation: calls.append(invocation.reference) or True
            )

        preview, receipt = scaling.initialize(
            self.db,
            self.fight,
            self.monsters,
            catalog=self.catalog,
            runtime_factory=runtime,
        )
        self.assertEqual(calls, [330890, 330891, 330893])
        self.assertEqual(receipt["fight_id"], 7)
        self.assertIsNot(preview, self.fight)
        self.assertEqual(preview.phase, "placement")
        replay, repeated = scaling.initialize(
            self.db,
            preview,
            self.monsters,
            catalog=self.catalog,
            runtime_factory=runtime,
        )
        self.assertIs(replay, preview)
        self.assertEqual(receipt, repeated)
        self.assertEqual(len(calls), 3)
        self.snapshot["selection_revision"] += 1
        with self.assertRaisesRegex(ValueError, "replay changed"):
            scaling.initialize(
                self.db,
                preview,
                self.monsters,
                catalog=self.catalog,
                runtime_factory=runtime,
            )

    def test_unbound_fight_and_wounded_or_live_fight_cannot_gain_scaling(self):
        db = SimpleNamespace(
            execute=lambda *args: SimpleNamespace(fetchone=lambda: None)
        )
        self.assertEqual(
            scaling.initialize(
                db,
                self.fight,
                self.monsters,
                catalog=self.catalog,
                runtime_factory=None,
            ),
            (self.fight, None),
        )
        self.actor.hp = 99
        with self.assertRaisesRegex(ValueError, "fresh"):
            scaling.plan(self.fight, self.monsters, self.snapshot, self.catalog)
        self.fight.phase = "active"
        with self.assertRaisesRegex(ValueError, "placement"):
            scaling.plan(self.fight, self.monsters, self.snapshot, self.catalog)


class NativeForcedConstructorTests(unittest.TestCase):
    """Real generic16 execution; no invented active-phase initialization."""

    def fixture(self):
        import random
        from wakfu_server.combat.combat_state import Fight
        from wakfu_server.combat.combat_force_characteristic import (
            NativeForcedCharacteristicHandler,
        )
        from wakfu_server.combat.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat.combat_effect_dispatch import EffectInvocation

        actor = Actor(-3, 1, (0, 0, 0), 100, 6, 3, 1, 5)
        player = Actor(7, 0, (1, 0, 0), 100, 6, 3, 1, 5)
        fight = Fight(
            7, [player, actor], {(0, 0, 0), (1, 0, 0)}, {0: {(1, 0, 0)}, 1: {(0, 0, 0)}}
        )
        for name, value in (
            ("effect_stats", 100),
            ("effect_maxima", 100),
            ("effect_minima", 0),
            ("effect_base_maxima", 100),
            ("effect_base_minima", 0),
            ("effect_percentages", 0),
        ):
            setattr(actor, name, {1: value})
        actor.effect_frozen = frozenset()
        handler = NativeForcedCharacteristicHandler(
            fight,
            [],
            {"effects": {"16": {"runner": "eYO", "fixed_stat_id": 1}}},
            action_id=1,
            allocate_uid=lambda: 101,
            context=lambda *args: StatExecutionContext(True, True, None, False, None),
            rng=random.Random(1),
        )
        invocation = EffectInvocation(330890, 4, actor.id, actor.id, actor.position)
        return fight, actor, player, handler, invocation

    def test_actual_detached_self_can_execute_native_hp_percentage_in_placement(self):
        from unittest.mock import patch
        from wakfu_server.combat.combat_summon_creation import (
            native_fresh_summon_authority,
        )
        from wakfu_server.combat.combat_summon_initialization import (
            detached_summon_scope,
        )

        fight, actor, player, handler, invocation = self.fixture()
        del fight.actors[actor.id]
        actor.team = -1
        authority = native_fresh_summon_authority(actor, 1)
        with detached_summon_scope(fight, actor, authority), patch(
            "wakfu_server.combat.combat_character_copy_metadata.native_copy_characteristics",
            return_value={"fresh_characteristics": {"1": {"over_max_current": True}}},
        ):
            self.assertTrue(
                handler(
                    {
                        "effect_class": 16,
                        "parameters": [210.0, 0.0, 1.0, 0.0, 1.0, 0.0],
                    },
                    [],
                    invocation,
                )
            )
        self.assertEqual((actor.hp, actor.max_hp), (210, 210))
        self.assertEqual(fight.phase, "placement")

    def test_registered_placement_and_detached_cross_actor_do_not_bypass_guard(self):
        from dataclasses import replace
        from wakfu_server.combat.combat_summon_creation import (
            native_fresh_summon_authority,
        )
        from wakfu_server.combat.combat_summon_initialization import (
            detached_summon_scope,
        )

        fight, actor, player, handler, invocation = self.fixture()
        effect = {"effect_class": 16, "parameters": [210.0, 0.0, 1.0, 0.0, 1.0, 0.0]}
        with self.assertRaisesRegex(ValueError, "actors"):
            handler(effect, [], invocation)
        del fight.actors[actor.id]
        actor.team = -1
        with detached_summon_scope(
            fight, actor, native_fresh_summon_authority(actor, 1)
        ):
            with self.assertRaisesRegex(ValueError, "actors"):
                handler(effect, [], replace(invocation, target_id=player.id))
        self.assertEqual(actor.hp, 100)
