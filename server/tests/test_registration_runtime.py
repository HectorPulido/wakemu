"""Focused integration of runtime registration with native owner journals."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from wakfu_server.combat_retained_registration_scope import (
    live_registration_scope,
    native_membership_owner,
    registration_owner,
)
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_handler import NativeStateHandler
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_stat_handler import NativeStatHandler
import test_combat_stat_handler as stat_fixtures


def _fight():
    pc = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
    npc = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1)
    fight = Fight(
        77,
        [pc, npc],
        {pc.position, npc.position},
        {0: {pc.position}, 1: {npc.position}},
    )
    fight.ready(3)
    return fight


def _running_state(uid):
    return RunningState(uid, 3442, 1, 7, 7, 1, "target", False, (), 0, True, None)


class RegistrationRuntimeTests(TestCase):
    def test_prior_ledger_only_uid_is_present_to_the_native_registration_journal(self):
        fight = _fight()
        owner = native_membership_owner(fight)
        self.assertIsNotNone(owner)
        fight.actors[7].state_ledger._entries = (_running_state(300),)
        self.assertNotIn(300, owner.source_counts)
        with live_registration_scope(owner) as journal:
            self.assertIn(300, journal)
            journal.touch(300)
            self.assertTrue(journal.previous[300])

    def test_wrap_registers_fresh_stat_sources_in_native_insertion_order(self):
        fixture = stat_fixtures.StatHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        fight.native_effect_uid_next = 100
        packets = []
        effect = dict(
            effect_class=120,
            parameters=[10, 0],
            parameter_count=1,
            minimum_level=1,
            maximum_level=200,
            variant=0,
            native_execution_mode=0,
            target_masks=[None] * 7,
            children=[],
            criteria="",
            probability_base=100,
            probability_per_level=0,
        )
        metadata = dict(
            states={},
            spells={},
            effects={
                "123": dict(
                    effect_class=120,
                    parameters=[10, 0],
                    minimum_level=1,
                    maximum_level=200,
                    variant=0,
                    definition_type=0,
                    definition_dispellable=False,
                    owner_on_caster=False,
                    subscription=False,
                )
            },
        )
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan={"native_retained_container": {"present": False}},
            state_catalog={},
            action_id=1,
            timing=None,
            metadata=metadata,
        )
        handler = NativeStatHandler(
            fight,
            packets,
            fixture.registry,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda *args: fixture.handler.context(*args),
            rng=lambda: 0.5,
        )
        observed = []

        def phase(_effect, _invocation, *, channel, uid, **_kwargs):
            if channel in (3, 4):
                scopes = getattr(
                    retention.fight.native_retained_records.owner, "_live_scopes", ()
                )
                observed.append((channel, uid, tuple(scopes)))

        handler.event_lifecycle = SimpleNamespace(
            phase=phase,
            register_applied=retention.register_applied_stat,
        )
        retention.stat_handler = handler
        execute = retention.wrap(handler)
        for reference in (123, 123):
            invocation = fixture.invocation.__class__(
                reference,
                1,
                7,
                7,
                (0, 0, 0),
                base_uid=None,
                state_uid=None,
            )
            prepared = handler.prepare(effect, {}, invocation)
            self.assertTrue(execute(effect, {}, prepared))

        self.assertEqual(fight.native_retained_order, [100, 101])
        self.assertEqual(tuple(fight.owned_stat_effects), (100, 101))
        self.assertEqual(tuple(fight.native_retained_records), (100, 101))
        self.assertEqual(
            [event[:2] for event in observed], [(3, 100), (4, 100), (3, 101), (4, 101)]
        )
        self.assertTrue(all(event[2] for event in observed))
        self.assertFalse(fight.native_retained_records.owner._live_scopes)

    def test_nested_scope_unwinds_after_handler_error(self):
        owner = native_membership_owner(_fight())
        self.assertIsNotNone(owner)
        with self.assertRaisesRegex(RuntimeError, "fixture failure"):
            with live_registration_scope(owner) as outer:
                with live_registration_scope(owner) as inner:
                    self.assertIn(inner, owner._live_scopes)
                    self.assertIn(outer, owner._live_scopes)
                    raise RuntimeError("fixture failure")
        self.assertEqual(owner._live_scopes, [])

    def test_native_owner_admission_excludes_area_detached_and_custom_handlers(self):
        fight = _fight()
        self.assertIsNotNone(native_membership_owner(fight))
        fight.native_effect_areas[901] = {"uid": 901}
        self.assertIsNone(native_membership_owner(fight))
        del fight.native_effect_areas[901]

        with patch(
            "wakfu_server.combat_summon_initialization.detached_actors",
            return_value=(object(),),
        ):
            self.assertIsNone(native_membership_owner(fight))

        class CustomHandler:
            def __call__(self, *_args):
                return None

        custom = CustomHandler()
        self.assertIsNone(registration_owner(fight, custom))
        self.assertIsNotNone(
            registration_owner(
                fight,
                NativeStateHandler(
                    fight,
                    [],
                    {},
                    action_id=1,
                    allocate_uid=fight.allocate_effect_uid,
                    context=lambda *_: None,
                    execute_child=lambda *_: None,
                ),
            )
        )
        fixture = stat_fixtures.StatHandlerTests()
        fixture.setUp()
        self.assertIsNotNone(registration_owner(fixture.fight, fixture.handler))

    def test_custom_runtime_live_provider_uses_legacy_path_without_journal(self):
        fixture = stat_fixtures.StatHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        fight.native_effect_uid_next = 100
        packets = []
        effect = dict(
            effect_class=120,
            parameters=[10, 0],
            parameter_count=1,
            minimum_level=1,
            maximum_level=200,
            variant=0,
            native_execution_mode=0,
            target_masks=[None] * 7,
            children=[],
            criteria="",
            probability_base=100,
            probability_per_level=0,
        )
        metadata = dict(
            states={},
            spells={},
            effects={
                "123": dict(
                    effect_class=120,
                    parameters=[10, 0],
                    minimum_level=1,
                    maximum_level=200,
                    variant=0,
                    definition_type=0,
                    definition_dispellable=False,
                    owner_on_caster=False,
                    subscription=False,
                )
            },
        )
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan={"native_retained_container": {"present": False}},
            state_catalog={},
            action_id=1,
            timing=None,
            metadata=metadata,
        )
        source_live = retention._live

        def custom_live(*args, **kwargs):
            return source_live(*args, **kwargs)

        retention._live = custom_live
        handler = NativeStatHandler(
            fight,
            packets,
            fixture.registry,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda *args: fixture.handler.context(*args),
            rng=lambda: 0.5,
        )
        owner = fight.native_retained_records.owner
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda *_args, **_kwargs: None,
            register_applied=retention.register_applied_stat,
        )
        retention.stat_handler = handler
        invocation = fixture.invocation.__class__(
            123,
            1,
            7,
            7,
            (0, 0, 0),
            base_uid=None,
            state_uid=None,
        )
        prepared = handler.prepare(effect, {}, invocation)
        self.assertTrue(retention.wrap(handler)(effect, {}, prepared))
        self.assertEqual(fight.native_retained_order, [100])
        self.assertIsNone(getattr(owner, "_live_scopes", None))
