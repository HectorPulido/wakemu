"""Original signed eWu→fyW→eZk lifecycle; no clamped or skipped carrier."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server.combat_conditions import ConditionContext, evaluate_condition
from wakfu_server.combat_definitions import state_profile
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_effect_resolver import (
    NativeEffectResolver,
    EffectResolutionContext,
)
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_handler import NativeStateHandler
from wakfu_server.combat_state_parameters import pack_state_identity
from wakfu_server.combat_timed_expiration import prepare_timed_expiration
from wakfu_server.fight_checkpoint_store import snapshot


class NativeSignedStateCarrierTests(unittest.TestCase):
    def test_original_signed_grade_wire_merge_callbacks_expiry_and_checkpoint(self):
        source = json.loads(
            (
                Path(__file__).parent / "fixtures" / "native_signed_state_carrier.json"
            ).read_text()
        )
        catalog = dict(states=source["states"], effects=source["effects"])
        pc = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 10, 3, True)
        enemy = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 1, 10)
        fight = Fight(
            77,
            [pc, enemy],
            {pc.position, enemy.position},
            {0: {pc.position}, 1: {enemy.position}},
        )
        fight.ready(3)
        for actor in (pc, enemy):
            actor.physical_radius = 0
        fight.native_effect_uid_next = 500
        packets, phases = [], []
        plan = {"native_retained_container": {"present": False}}
        timing = NativeEffectTimingProvider(catalog)
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan=plan,
            state_catalog=catalog,
            action_id=1,
            timing=timing,
            metadata=source["retained_metadata"],
        )
        handler = NativeStateHandler(
            fight,
            packets,
            catalog,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            execute_child=None,
            context=lambda effect, invocation: timing.state(
                fight, plan, effect, invocation
            ),
            rng=lambda: 0.99,
            applied_state_scope=retention.applied_state_scope,
        )
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda _effect, _invocation, **data: phases.append(
                (data["channel"], data["runner_modifier"].pending_level)
            )
        )
        targets = {
            identity: dict(
                bEe=True,
                is_amO=True,
                is_eGj=True,
                is_Qq=False,
                is_eHH=True,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
            )
            for identity in fight.actors
        }
        resolver = NativeEffectResolver(
            actors=lambda *_: tuple(fight.actors.values()),
            caster=lambda _effect, invocation: fight.actors[invocation.caster_id],
            native_context=lambda *_: targets,
            context=lambda *_: EffectResolutionContext(
                "EFFECTS_ONLY", "immediate", "actors", True
            ),
        )
        dispatcher = EffectDispatcher(
            catalog["effects"],
            {304: retention.wrap(handler, state=True)},
            resolve=resolver,
            condition_context=lambda _: ConditionContext({}),
            probability_accepts=lambda probability, _: probability == 100,
            group_cells=lambda *_: (),
            actor_position=lambda identity: fight.actors[identity].position,
            group_retention=retention,
            prepare_effect=handler.prepare,
        )
        handler.execute_child = dispatcher.execute
        invocation = EffectInvocation(315471, 16384, 7, 7, pc.position)
        self.assertTrue(dispatcher.execute(invocation))
        (first,) = pc.state_ledger.entries
        self.assertEqual(
            (first.reference, first.level, first.effect_ids, first.retained),
            (6844, -32768, (), True),
        )
        self.assertIsNotNone(first.timer)
        self.assertEqual(phases, [(1, 0), (2, -32768), (3, -32768), (4, -32768)])
        self.assertEqual(state_profile(catalog, 6844, -32768)["effects"], [])
        packed = (6844 << 16) + 32768
        self.assertEqual(pack_state_identity(6844, -32768), packed)
        payload = bytes.fromhex(fight.state_wire_payloads[first.uid])
        messages = {}
        fields = _identity_fields(payload, messages=messages)
        additional = _identity_fields(messages[8], integer_fields=(10, 13))
        self.assertEqual(
            (fields[4], additional[10], additional[13]), (packed, packed, first.uid)
        )
        self.assertEqual(
            retention.container(replace(invocation, state_uid=first.uid))[1], packed
        )
        from wakfu_server.combat_state_cleanup import RetainedCleanupAuthority

        (carrier,) = retention.view().entries
        self.assertFalse(RetainedCleanupAuthority(retention, 7).cleanup_flag(carrier))
        facts = pc.state_ledger.condition_actor()
        context = ConditionContext({"caster": facts})
        self.assertTrue(evaluate_condition("HasState(6844)", context))
        self.assertTrue(evaluate_condition("GetStateLevel(6844) == -32768", context))
        self.assertFalse(evaluate_condition("HasStateFromLevel(6844, 0)", context))
        saved = snapshot(fight)
        self.assertEqual(
            saved["actors"]["7"]["state_ledger"]["entries"][0]["level"], -32768
        )
        cloned = deepcopy(fight)
        self.assertEqual(snapshot(cloned), saved)

        # Additive merging retains the signed input, rather than zero-clamping
        # it or substituting the incoming parent's positive level.
        self.assertTrue(dispatcher.execute(replace(invocation, level=1)))
        (current,) = pc.state_ledger.entries
        self.assertEqual(current.level, -32766)
        self.assertNotEqual(first.uid, current.uid)
        self.assertNotIn(first.uid, fight.state_wire_payloads)
        self.assertEqual(set(fight.native_retained_records), {current.uid})
        self.assertEqual([opcode for opcode, _ in packets], [12613, 13560, 12613])
        before = snapshot(fight)
        expired, removed = prepare_timed_expiration(
            fight,
            actor_id=7,
            round_number=current.timer.expiration_round,
            phase=current.timer.phase,
            action_id=2,
            registry={"effects": {}},
        )
        self.assertEqual(
            snapshot(fight), before
        )  # Expiration remains a private preview.
        self.assertEqual(expired.actors[7].state_ledger.entries, ())
        self.assertEqual(expired.state_wire_payloads, {})
        self.assertEqual(expired.native_retained_records, {})
        self.assertEqual([opcode for opcode, _ in removed], [13560])
        for invalid in (-32769, 32768, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                state_profile(catalog, 6844, invalid)
