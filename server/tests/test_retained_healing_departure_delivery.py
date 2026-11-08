"""Retained damage children keep caster-local delivery without active authority."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

import test_rift_retained_departure_source as fixtures
from native_combat_fixture import initialize_fixture_qi
from test_combat_effect_dispatch import effect
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents
from wakfu_server.combat_damage_events import damage_event_ids
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_summon import RegisteredSummonAuthority
from wakfu_server.combat_pve_departure import retire_pve_actor
from wakfu_server import combat_retained_departure_source as proof


class RetainedHealingDepartureDeliveryTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.RetainedDepartureSourceTests()
        fight = fixture.fight_with_retained_effect()
        root = replace(fixture.invocation(), reference=317575, state_uid=4568)
        row = fight.native_owned_group_effects[root.base_uid]
        row.update(
            invocation=vars(replace(root, base_uid=None)),
            state_uid=4568,
            children=[317576],
        )
        initialize_fixture_qi(fight)
        fight.phase = "active"
        authority = RegisteredSummonAuthority(fixture.ordinary())
        proof.capture_departure_sources(fight, {159}, authority)
        retire_pve_actor(fight, fight.actors[159], root_actor_id=159, owner_id=98)
        fight.actors[159].pve_withdrawn = True
        adapter = NativeServerRuntimeAdapter.__new__(NativeServerRuntimeAdapter)
        adapter.actor_authority = authority
        deliveries = []
        events = OrdinaryHealingEvents.__new__(OrdinaryHealingEvents)
        events.adapter, events.preview = adapter, fight
        events.definition = lambda *_: dict(event_suppresses_level_one=False)
        events.identifiers = lambda *_: {}
        events.retention = SimpleNamespace(view=lambda: SimpleNamespace(entries=()))
        events.replay = lambda source, **_: deliveries.append(
            (source.manager_actor_id, source.channel)
        )
        events.authority = object()
        child_effect = effect(1)
        child_effect.update(
            native_effect_flags=(), target_masks=[[], [], [], [], [], [], []]
        )
        children = []

        def damage_phase(definition, child, *, uid):
            # Match OrdinaryDamageEvents.phase's eXt event selection while
            # isolating delivery authority from damage arithmetic/geometry.
            ids = damage_event_ids(
                definition,
                container_type=1,
                phase=1,
                blocked=False,
                localization="FRONT",
                context_is_native_fight=True,
            )
            return events.phase(
                definition,
                child,
                uid=uid,
                value=10,
                channel=1,
                _event_ids=ids,
                _cost_source=dict(
                    runner_class="other",
                    spell_context=dict(present=True, container_type=1),
                ),
            )

        events.damage_phase = damage_phase

        def handle(definition, values, child):
            children.append(child)
            damage_phase(definition, child, uid=9000)
            return True

        dispatcher = EffectDispatcher(
            {"317575": effect(330, children=(317576,)), "317576": child_effect},
            {1: handle},
            resolve=lambda e, i: (i,),
            condition_context=lambda i: ConditionContext({}),
            probability_accepts=lambda *a: True,
            group_cells=lambda *a: (),
            actor_position=lambda i: (0, 0, 0),
        )
        return fight, root, dispatcher, events, authority, deliveries, children

    def activate(self, fight, root, dispatcher):
        with proof.retained_activation_scope(fight, dispatcher, root):
            dispatcher.execute_activation(
                root,
                source=None,
                condition_context=lambda *a: ConditionContext({}),
                executable=True,
                allocate_uid=lambda: 9000,
            )

    def test_original_damage_child_delivers_caster_then_target_without_active_grant(
        self,
    ):
        fight, root, dispatcher, events, authority, delivered, children = self.fixture()
        self.activate(fight, root, dispatcher)
        self.assertIsNone(children[0].base_uid)
        self.assertEqual(children[0].reference, 317576)
        self.assertEqual(delivered[:2], [(159, 10), (160, 1)])
        with self.assertRaisesRegex(ValueError, "no active summon authority"):
            authority(fight, fight.actors[159])
        self.assertIsNone(proof._ACTIVATION.get())
        self.assertIsNone(proof._DESCENDANT.get())

    def test_unscoped_child_and_changed_original_group_remain_rejected(self):
        fight, root, dispatcher, events, authority, delivered, children = self.fixture()
        self.activate(fight, root, dispatcher)
        with self.assertRaisesRegex(ValueError, "Missing exact"):
            events.damage_phase(dispatcher.effects["317576"], children[0], uid=9001)
        fight.native_owned_group_effects[root.base_uid]["invocation"]["target_id"] = 159
        with self.assertRaisesRegex(ValueError, "original group"):
            self.activate(fight, root, dispatcher)

    def test_withdrawn_target_has_no_recipient_exception(self):
        fight, root, dispatcher, events, authority, delivered, children = self.fixture()
        fight.actors[160].pve_withdrawn = True
        with self.assertRaisesRegex(ValueError, "no active summon authority"):
            self.activate(fight, root, dispatcher)
        self.assertEqual(delivered, [])
