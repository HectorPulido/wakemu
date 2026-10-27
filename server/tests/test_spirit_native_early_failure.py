"""Real native damage/death and original411015 component, not a full scene."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_minimum_resource import (
    NativeMinimumResourceHandler,
    remove_minimum_resource,
)
from wakfu_server.combat_kill import NativeKillHandler
from wakfu_server.combat_dispel import NativeDispelHandler
from wakfu_server.combat_retained_effects import (
    RetainedEffect,
    NativeRetainedEffectView,
    NativeRetainedRemoval,
)
from wakfu_server.combat_effect_targets import select_native_effect_targets
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_death_events import deliver_owned_death
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server.combat_encounter_objective_spirit import deliver_spirit_early_defeat

EFFECTS = json.loads(
    (Path(__file__).parent / "fixtures/native_spirit_failure_effects.json").read_text()
)


class SpiritNativeEarlyFailureTests(unittest.TestCase):
    def fixture(self):
        actors = [
            Actor(7, 0, (0, 0, 0), 100, 6, 3, 20, 200, 3, True),
            Actor(8, 0, (0, 1, 0), 100, 6, 3, 15, 200, 4, True),
            Actor(-7, 1, (2, 0, 0), 100, 6, 3, 10, 96),
            Actor(-8, 0, (1, 0, 0), 100, 6, 3, 9, 200),
            Actor(-9, 0, (1, 1, 0), 100, 6, 3, 8, 200),
        ]
        fight = Fight(
            77,
            actors,
            {a.position for a in actors},
            {0: {a.position for a in actors if a.team == 0}, 1: {(2, 0, 0)}},
        )
        fight.ready(3)
        fight.ready(4)
        initialize_global_pv_collections(fight, tuple(fight.actors))
        for actor in actors:
            actor.effect_stats = {1: 100, 14: 0, 92: 0, 97: 0, 100: 0}
            actor.effect_maxima = {1: 100, 14: 0, 92: 0}
            actor.effect_minima = {1: 0, 14: 0}
            actor.effect_base_minima = dict(actor.effect_minima)
            actor.effect_base_maxima = dict(actor.effect_maxima)
            actor.effect_percentages = {1: 0, 14: 0}
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
        packets = []
        ids = iter(range(101, 1000))
        allocate = lambda: next(ids)
        ctx = lambda *args: StatExecutionContext(True, True, None, True, b"", None)
        minimum = NativeMinimumResourceHandler(
            fight, packets, action_id=5, allocate_uid=allocate, context=ctx
        )
        for actor in actors[-2:]:
            minimum(
                EFFECTS["410754"],
                {},
                EffectInvocation(410754, 200, actor.id, actor.id, actor.position),
            )

        def view():
            return NativeRetainedEffectView(
                fight,
                [
                    RetainedEffect(
                        uid,
                        row["target_id"],
                        row["effect_class"],
                        _identity_fields(bytes.fromhex(row["payload"]))[3],
                        owner_uid=row.get("state_uid"),
                    )
                    for uid, row in fight.owned_stat_effects.items()
                ],
                population_verified_complete=True,
            )

        def removal(current):
            consumer = NativeRetainedRemoval(current)
            consumer.register(
                877,
                exists=lambda uid: uid in fight.owned_stat_effects,
                remove=lambda uid: remove_minimum_resource(minimum, uid),
                validate=lambda uid: None,
            )
            return consumer

        dispel = NativeDispelHandler(view_provider=view, removal_provider=removal)
        kill = NativeKillHandler(
            fight,
            packets,
            action_id=5,
            allocate_uid=allocate,
            context=ctx,
            rng=lambda: 0,
            authority=N(property_counts=lambda *args: {}),
        )
        contexts = {
            a.id: dict(
                is_amO=True,
                is_eGj=True,
                is_Qq=False,
                is_eHH=False,
                bEe=True,
                UNTARGETTABLE_BY_OTHER=False,
            )
            for a in actors
        }

        def resolve(effect, inv):
            return tuple(
                replace(inv, target_id=a.id, cell=a.position)
                for a in select_native_effect_targets(
                    effect,
                    fight.actors[inv.caster_id],
                    inv.cell,
                    fight.actors.values(),
                    native_context=contexts,
                )
            )

        dispatcher = EffectDispatcher(
            EFFECTS,
            {421: dispel, 28: kill, 1099: lambda *args: True},
            resolve=resolve,
            condition_context=lambda inv: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda identity: fight.actors[identity].position,
        )
        dispatcher.native_retention = N(fight=fight)
        fight.native_encounter_objective_policy = {}
        fight.native_scene_helper_manifest = {
            "source": {"helpers": [{"actor_id": -8}, {"actor_id": -9}]}
        }
        receipt = dict(
            status="granted",
            source=dict(participant_id=7, admission_digest="a" * 64),
            ready_participants=dict(
                source=dict(
                    players=[
                        dict(actor_id=7, account_id=3),
                        dict(actor_id=8, account_id=4),
                    ]
                ),
                source_digest="b" * 64,
            ),
        )
        return fight, dispatcher, receipt, packets, allocate

    def authorization(self, fight, receipt):
        stack = ExitStack()
        stack.enter_context(
            patch(
                "wakfu_server.combat_encounter_objective_spirit.spirit_admission",
                return_value=receipt,
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_encounter_objective_policy.require_admitted_policy",
                return_value=N(reference=5848),
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_encounter_objective._score_scope",
                return_value=({}, fight.actors[-7]),
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_encounter_objective._admission",
                return_value=(None, "a" * 64, None),
            )
        )
        return stack

    def lethal_damage(self, fight, identity, packets, allocate):
        handler = NativeDamageHandler(
            fight,
            packets,
            action_id=7,
            allocate_uid=allocate,
            rng=lambda: 0.99,
            context=lambda *args: DamageExecutionContext(
                False, True, False, True, 11, False
            ),
        )
        invocation = EffectInvocation(
            999001, 96, -7, identity, fight.actors[identity].position
        )
        handler(
            dict(
                effect_class=1,
                parameters=[500, 0],
                native_effect_flags=[],
                native_localization_enabled=False,
            ),
            {},
            invocation,
        )
        self.assertEqual(fight.actors[identity].hp, 0)
        source = NativeEventSource(
            999,
            999001,
            500,
            -7,
            identity,
            invocation.cell,
            (1013,),
            6,
            identity,
            None,
            False,
            False,
            False,
            True,
        )
        deliver_owned_death(
            fight,
            identity,
            source=source,
            replay=lambda *args, **kwargs: (),
            authority=object(),
        )

    def test_actual_last_human_damage_and_death_run_original_floor_dispel_and_helper_kill(
        self,
    ):
        fight, dispatcher, receipt, packets, allocate = self.fixture()
        self.lethal_damage(fight, 7, packets, allocate)
        with self.authorization(fight, receipt):
            self.assertFalse(deliver_spirit_early_defeat(dispatcher))
            self.assertEqual([fight.actors[i].hp for i in (-8, -9)], [100, 100])
            self.lethal_damage(fight, 8, packets, allocate)
            boss_hp = fight.actors[-7].hp
            self.assertTrue(deliver_spirit_early_defeat(dispatcher))
        self.assertEqual(fight.actors[-7].hp, boss_hp)
        self.assertEqual([fight.actors[i].effect_minima[1] for i in (-8, -9)], [0, 0])
        self.assertTrue(all(not fight._in_play(fight.actors[i]) for i in (-8, -9)))
        self.assertEqual(fight.native_spirit_failure_result["effect_reference"], 411015)
        self.assertEqual((fight.phase, fight.winner), ("finished", 1))

    def test_raw_zero_hp_without_owned_death_receipt_cannot_authorize_failure(self):
        fight, dispatcher, receipt, _, _ = self.fixture()
        # Deliberately invalid negative premise; never used as positive proof.
        fight.actors[7].hp = fight.actors[8].hp = 0
        with self.authorization(fight, receipt):
            self.assertFalse(deliver_spirit_early_defeat(dispatcher))
        self.assertEqual([fight.actors[i].effect_minima[1] for i in (-8, -9)], [1, 1])
        self.assertFalse(hasattr(fight, "native_spirit_failure_result"))

    def test_unadmitted_fight_does_not_consume_protected_helpers(self):
        fight, dispatcher, _, _, _ = self.fixture()
        del fight.native_encounter_objective_policy
        self.assertFalse(deliver_spirit_early_defeat(dispatcher))
        self.assertEqual([fight.actors[i].effect_minima[1] for i in (-8, -9)], [1, 1])
