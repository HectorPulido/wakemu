"""Original Arma de Luz consumers under the declared paid-weapon boundary."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_damage_events import damage_event_ids
from wakfu_server.combat_death_script import NativeDeathScriptHandler
from wakfu_server.combat_finisher_events import (
    prepare_owned_finisher,
    finish_owned_finisher,
)
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_event_replay import (
    NativeEventReplay,
    NativeEventSource,
    NativeCloneAuthority,
    NativeExternalEvent,
)
from wakfu_server.combat_final_modifier import NativeFinalModifierHandler
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_handler import NativeStateHandler
from wakfu_server.combat_stat_handler import NativeStatHandler
from wakfu_server.combat_weapon_events import POLICY, weapon_event_scope
from wakfu_server.fight_checkpoint_store import snapshot


class NativeLightWeaponConsumerTests(unittest.TestCase):
    def test_original_weapon_current_modifier_poison_and_success_cleanup(self):
        data = json.loads(
            (
                Path(__file__).parent / "fixtures" / "native_light_weapon.json"
            ).read_text()
        )
        catalog = dict(states=data["states"], effects=data["effects"])
        actors = [
            Actor(7, 0, (0, 0, 0), 1000, 12, 6, 10, 100, 3, True),
            Actor(-7, 1, (1, 0, 0), 1000, 6, 3, 1, 100),
        ]
        fight = Fight(
            77,
            actors,
            {a.position for a in actors},
            {0: {actors[0].position}, 1: {actors[1].position}},
        )
        for actor in actors:
            actor.physical_radius = 0
            actor.effect_stats = {
                1: 1000,
                2: actor.ap,
                3: actor.mp,
                4: 6,
                20: 0,
                21: 0,
                22: 0,
                23: 0,
                24: 0,
                32: 0,
                40: 0,
                92: 0,
                97: 0,
                100: 0,
            }
            actor.effect_maxima = {
                1: 1000,
                2: actor.max_ap,
                3: actor.max_mp,
                4: 6,
                92: 0,
            }
            actor.effect_minima = {key: 0 for key in actor.effect_stats}
            actor.effect_frozen = frozenset()
        from native_combat_fixture import initialize_fixture_qi

        initialize_fixture_qi(fight)
        fight.ready(3)
        fight.native_effect_uid_next = 900
        packets = []
        plan = {"native_retained_container": {"present": False}}
        timing = NativeEffectTimingProvider(catalog)
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan=plan,
            state_catalog=catalog,
            action_id=1,
            timing=timing,
            metadata=data["retained_metadata"],
        )

        def condition(invocation, source=None):
            trigger = invocation.native_trigger_context or {}
            native_container = trigger.get("native_container", {})
            if source is not None and isinstance(source, NativeEventSource):
                native_container = source.native_container

            def alias(identity):
                actor = fight.actors[identity]
                return actor.state_ledger.condition_actor(
                    is_native_fighter=True,
                    is_player=actor.controlled,
                    summon_count=0,
                    world_properties=frozenset(),
                    characteristics={
                        "HP": actor.hp,
                        "ARMOR": 0,
                        "KO_TIME_BEFORE_DEATH": 0,
                    },
                    characteristic_maxima={"HP": actor.max_hp},
                )

            return ConditionContext(
                {
                    "caster": alias(invocation.caster_id),
                    "target": alias(invocation.target_id),
                },
                fight_current_table_turn=4,
                fight_model_query=lambda: 2,
                allies_count_query=lambda selector: 0,
                active_cosmetic_id_query=lambda category: 20753 if category == 5 else 0,
                has_active_cosmetic_query=lambda category, reference: category == 5
                and reference == 20753,
                random_number_query=lambda maximum, exclusions: 0,
                pvp_query=lambda: False,
                weapon_type_query=lambda references: 254 in references,
                triggering_effect_present=bool(trigger)
                or isinstance(source, NativeEventSource),
                triggering_effect_flags=frozenset(trigger.get("effect_flags", ()))
                if not isinstance(source, NativeEventSource)
                else frozenset(source.effect_flags or ()),
                triggering_container_type=native_container.get("type", 0),
            )

        state = NativeStateHandler(
            fight,
            packets,
            catalog,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            execute_child=None,
            context=lambda e, i: timing.state(fight, plan, e, i),
            rng=lambda: 0.99,
            applied_state_scope=retention.applied_state_scope,
        )
        final = NativeFinalModifierHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda e, i: timing.stat(fight, plan, e, i),
        )
        damage = NativeDamageHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            rng=lambda: 0.99,
            context=lambda e, i: DamageExecutionContext(
                False,
                True,
                False,
                True,
                retention.container(i)[0].get("container_type"),
                False,
            ),
        )
        death_script = NativeDeathScriptHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda e, i: timing.stat(fight, plan, e, i),
            rng=lambda: 0.99,
        )
        dispatcher = EffectDispatcher(
            data["effects"],
            {
                304: retention.wrap(state, state=True),
                1093: retention.wrap(final),
                1099: retention.wrap(death_script),
                1: damage,
                1083: damage,
            },
            resolve=lambda e, i: (i,),
            condition_context=condition,
            probability_accepts=lambda p, i: p == 100,
            group_cells=lambda *_: (),
            actor_position=lambda identity: fight.actors[identity].position,
            group_retention=retention,
            prepare_effect=lambda e, v, i: state.prepare(e, v, i)
            if e["effect_class"] == 304
            else damage.prepare(e, v, i)
            if e["effect_class"] in (1, 1083)
            else i,
        )
        from random import Random
        from wakfu_server.combat_relative_probability import RelativeGroupAuthority
        from wakfu_server.combat_runtime_adapter import NativeActorAuthority

        relative_rng = Random(7)

        def actor_authority(preview, actor):
            return NativeActorAuthority(
                targeting=dict(
                    bEe=True,
                    is_amO=True,
                    is_eGj=True,
                    is_Qq=False,
                    is_eHH=True,
                    UNTARGETTABLE_BY_OTHER=False,
                    buX=False,
                    baF=True,
                    baG=False,
                    baK=False,
                ),
                is_player=actor.controlled,
                deck_spell_ids=frozenset(),
                excluded_deck_spell_ids=frozenset(),
                is_carried=False,
                breed_id=15,
                summon_count=0,
                summon_counts_by_breed={},
                occupant_blocks=True,
            )

        relative = RelativeGroupAuthority(
            effects=data["effects"],
            actor_authority=actor_authority,
            condition_context=lambda p, plan, e, i: condition(i),
            draw_integer=lambda total: relative_rng.randint(1, total),
            draw_fraction=lambda fraction: relative_rng.random() < fraction,
        )
        dispatcher.relative_group_children = lambda e, v, i, children: relative(
            fight, plan, e, v, i, children
        )
        state.execute_child = dispatcher.execute
        state.register_subscription = dispatcher.register_subscription
        retention.stat_handler = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda e, i: timing.stat(fight, plan, e, i),
        )
        dispatcher.native_retention = retention
        dispatcher.replay_event = NativeEventReplay(dispatcher, retention)
        event_deliveries = []
        actual_replay = dispatcher.replay_event

        def replay(event, **kwargs):
            outcome = actual_replay(event, **kwargs)
            event_deliveries.append(
                (
                    event.event_ids,
                    event.channel,
                    event.manager_actor_id,
                    outcome,
                    [
                        (entry.uid, entry.generic_effect, entry.manager_id)
                        for entry in retention.view().entries
                    ],
                )
            )
            return outcome

        replay.retention = retention
        dispatcher.replay_event = replay
        dispatcher.native_clone_authority = NativeCloneAuthority(
            lambda e, i, s: True, lambda e, i, s: condition(i, s)
        )
        observed, sources = [], []

        class Events:
            def phase(_, effect, invocation, **facts):
                channel = facts["channel"]
                descriptor, identity = retention.container(invocation)
                kind = descriptor.get("container_type")
                native_container = dict(present=descriptor["container_present"])
                if native_container["present"]:
                    native_container.update(type=kind, is_state=kind == 1)
                    if kind == 1:
                        native_container["state_id"] = identity >> 16
                source = NativeEventSource(
                    facts["uid"],
                    invocation.reference,
                    facts["value"],
                    invocation.caster_id,
                    invocation.target_id,
                    invocation.cell,
                    damage_event_ids(
                        effect,
                        container_type=kind,
                        phase=channel,
                        blocked=False,
                        localization="FRONT",
                        context_is_native_fight=True,
                    ),
                    channel * 10,
                    invocation.caster_id,
                    None,
                    False,
                    False,
                    False,
                    True,
                    native_container=native_container,
                    effect_action_id=effect["effect_class"],
                    effect_flags=tuple(effect["native_effect_flags"]),
                    native_definition_present=True,
                    native_definition_variant=effect["variant"],
                    final_modifier=facts.get("final_modifier"),
                    runner_modifier=facts.get("runner_modifier"),
                )
                sources.append(source)
                dispatcher.replay_event(
                    source, authority=dispatcher.native_clone_authority
                )
                if channel == 2:
                    observed.append(
                        (
                            source.uid,
                            source.final_modifier.value,
                            source.target_id,
                            source.native_container["type"],
                        )
                    )

        damage.event_lifecycle = Events()
        self.assertTrue(
            dispatcher.execute(EffectInvocation(287190, 1, 7, 7, (0, 0, 0)))
        )
        self.assertEqual(
            [entry.reference for entry in actors[0].state_ledger.entries], [5976]
        )
        innate = EffectInvocation(
            -1, 1, 7, 7, (0, 0, 0), native_retained_container={"present": False}
        )
        self.assertTrue(
            retention.apply_state_reference(
                state,
                innate,
                4464,
                1,
                carrier_context=timing.direct_state_reference(
                    fight, innate, 4464, 1, critical=False
                ),
            )
        )
        actors[0].native_cosmetic_state = dict(
            selected_values={5: (20753,)}, active_cosmetics={5: (20753,)}
        )
        # A normal spell's native external event must not arm the weapon listener.
        dispatcher.replay_event(
            NativeExternalEvent(7, (1024,), 60),
            authority=dispatcher.native_clone_authority,
        )
        self.assertFalse(
            any(
                row["invocation"]["reference"] == 283074
                for row in fight.native_owned_group_effects.values()
            )
        )
        plan.update(
            actor_id=7,
            item_uid=1000,
            item_reference=2027,
            slot=15,
            costs={"ap": 3, "mp": 0, "wp": 0},
            native_retained_container={
                "present": True,
                "type": 12,
                "id": 2027,
                "is_spell": False,
                "protected": None,
            },
        )
        before_payment = (actors[0].ap, actors[0].mp, 6)
        actors[0].ap -= 3
        actors[0].effect_stats[2] = actors[0].ap
        plan["native_weapon_payment"] = dict(
            policy=POLICY,
            actor_id=7,
            item_uid=1000,
            before=before_payment,
            after=(actors[0].ap, actors[0].mp, 6),
        )
        before = snapshot(fight)
        with weapon_event_scope(dispatcher, plan):
            self.assertEqual(
                sum(
                    row["invocation"]["reference"] == 283074
                    for row in fight.native_owned_group_effects.values()
                ),
                1,
                (
                    event_deliveries,
                    {
                        uid: {
                            key: row.get(key)
                            for key in (
                                "invocation",
                                "state_uid",
                                "native_subscription_masks",
                            )
                        }
                        for uid, row in fight.native_owned_group_effects.items()
                    },
                ),
            )
            self.assertTrue(
                dispatcher.execute(EffectInvocation(382064, 100, 7, -7, (1, 0, 0)))
            )
        self.assertEqual(observed[0][1:], (-20, -7, 12))
        self.assertEqual(
            actors[1].hp, 920
        )  # The actual current 100-damage faq lost20%.
        # The original mask0 damage control deliberately excludes final modifiers.
        _, _, unmodified = damage._calculate(
            data["effects"]["243857"],
            EffectInvocation(243857, 100, 7, -7, (1, 0, 0)),
            additional_final=-20,
        )
        self.assertEqual(unmodified, 100)
        (poison,) = actors[1].state_ledger.entries
        self.assertEqual((poison.reference, poison.level), (5977, 3))
        self.assertIsNotNone(poison.timer)
        self.assertEqual(poison.timer.expiration_round, 4)
        self.assertFalse(
            any(
                row["invocation"]["reference"] == 283074
                for row in fight.native_owned_group_effects.values()
            )
        )
        self.assertEqual(
            sum(
                row["invocation"]["reference"] == 287264
                for row in fight.native_owned_group_effects.values()
            ),
            1,
        )
        # Original START subscription consumes the retained grade, not AP guesses.
        dispatcher.replay_event(
            NativeExternalEvent(-7, (1001,), 60),
            authority=dispatcher.native_clone_authority,
        )
        self.assertEqual(actors[1].hp, 890)
        self.assertEqual(actors[1].state_ledger.entries[0].timer, poison.timer)
        # The cosmetic namespace preserves its actual4464 descendants through
        # all three boundaries, without arming the independent equipment5976.
        cosmetic_source = next(
            source
            for source in sources
            if source.generic_effect == 382064 and source.channel == 40
        )
        cosmetic = prepare_owned_finisher(
            fight,
            cosmetic_source,
            replay=dispatcher.replay_event,
            authority=dispatcher.native_clone_authority,
        )
        self.assertIsNotNone(cosmetic)
        self.assertEqual(actors[1].native_death_script_id, 1100010)
        self.assertTrue(
            any(
                row["invocation"]["reference"] == 185235
                for row in fight.native_owned_group_effects.values()
            )
        )
        self.assertFalse(
            any(
                row["invocation"]["reference"] == 283074
                for row in fight.native_owned_group_effects.values()
            )
        )
        finish_owned_finisher(
            cosmetic,
            replay=dispatcher.replay_event,
            authority=dispatcher.native_clone_authority,
        )
        self.assertFalse(
            any(
                row["invocation"]["reference"] in (185235, 283074)
                for row in fight.native_owned_group_effects.values()
            )
        )
        # Checkpoint/deepcopy parity; paid-entry failure and RNG rollback have
        # their separate production-seam regression.
        private = deepcopy(fight)
        self.assertNotEqual(before, snapshot(fight))
        self.assertEqual(snapshot(private), snapshot(fight))
