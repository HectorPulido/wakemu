"""Paid native Steamer sequence preserves results across read optimizations."""
import copy
import os
import unittest
from contextlib import ExitStack, nullcontext
from unittest.mock import patch

import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerLagParityRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt

    def cycle(self, data):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from tools.combat_audit_turns import advance_actual_turn

        character, monster, fight, deck, rng = data
        packets = []
        for _ in range(20):
            runtime = RuntimeMessages(
                fight,
                turn_end_provider=lambda p, **b: prepare_server_turn_end(
                    character, {-7: monster}, p, deck, rng=rng, **b
                ),
                turn_start_provider=lambda p, **b: prepare_server_turn_start(
                    character, {-7: monster}, p, deck, rng=rng, area_callbacks=True, **b
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    character,
                    {-7: monster},
                    deck,
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                )[0],
            )
            packets.extend(advance_actual_turn(runtime))
            if fight.current.id == 7:
                return packets
        self.fail("Actual owner turn did not return")

    def test_paid_rails_turret_current_and_turn_callbacks_have_exact_parity(self):
        from wakfu_server import combat_fake_fighter as fake
        from wakfu_server import combat_ordinary_events as ordinary
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.fight_checkpoint_store import snapshot

        original = self.fixture((6940,), actives=(6907,))
        owner = original[2].actors[7]
        candidates = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cells = [
                (
                    owner.position[0] + dx * n,
                    owner.position[1] + dy * n,
                    owner.position[2],
                )
                for n in range(1, 5)
            ]
            if all(
                c in original[2].walkable
                and not any(a.position == c for a in original[2].actors.values())
                for c in cells
            ):
                candidates.append(cells)
        self.assertTrue(candidates)
        results = {}
        for optimized in (False, True):
            with self.subTest(optimized=optimized), ExitStack() as stack:
                if not optimized:
                    stack.enter_context(
                        patch.object(
                            ordinary,
                            "_phase_read_pass",
                            side_effect=lambda *_: nullcontext(),
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            ordinary, "_pure_area_recipient_read", return_value=False
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            NativeRetainedRuntime,
                            "_pure_view_manager_pass",
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            fake, "_plain_float_constructor", return_value=None
                        )
                    )
                data = copy.deepcopy(original)
                trace = []
                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    trace.append(
                        (
                            invocation.reference,
                            invocation.target_id,
                            invocation.native_trigger_context,
                            result,
                        )
                    )
                    return result

                stack.enter_context(patch.object(EffectDispatcher, "execute", observe))
                packets, states, rng_states, outcomes = [], [], [], []

                def record(transaction):
                    nonlocal data
                    before_actor = data[2].actors[7]
                    after_actor = transaction.fight.actors[7]
                    costs = transaction.plan["costs"]
                    self.assertGreater(costs["ap"], 0)
                    self.assertEqual(after_actor.ap, before_actor.ap - costs["ap"])
                    self.assertEqual(
                        after_actor.effect_stats[4],
                        before_actor.effect_stats[4] - costs["wp"],
                    )
                    self.assertTrue(any(transaction.outcomes))
                    packets.extend(transaction.packets)
                    outcomes.append(transaction.outcomes)
                    data = self.adopt(data, transaction.fight)
                    states.append(snapshot(data[2]))
                    rng_states.append(data[4].getstate())

                cells = candidates[0]
                record(self.cast(data, 7008, target=cells[0], action_id=2))
                record(self.cast(data, 7008, target=cells[-1], action_id=3))
                self.assertTrue(data[2].native_microbot_networks[7]["segments"])
                packets.extend(self.cycle(data))
                record(self.cast(data, 7700, action_id=4))
                packets.extend(self.cycle(data))
                record(self.cast(data, 6907, action_id=5))
                packets.extend(self.cycle(data))
                states.append(snapshot(data[2]))
                rng_states.append(data[4].getstate())
                self.assertTrue(packets)
                self.assertTrue({345157, 345158} <= {ref for ref, *_ in trace}, trace)
                self.assertTrue(any(context is not None for _, _, context, _ in trace))
                results[optimized] = (packets, states, rng_states, outcomes, trace)
        self.assertEqual(results[False], results[True])
