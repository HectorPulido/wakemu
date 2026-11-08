"""Native glyph callbacks keep outputs and outer rollback while coalescing steps."""
from copy import deepcopy
from random import Random
import struct
import sys
import unittest

from test_larva_glyph_movement_integration import LarvaGlyphMovementIntegrationTests
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_owned_movement_step import owned_native_movement
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Fight
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats


class OwnedMovementStepTests(unittest.TestCase):
    def fixture(self, steps):
        helper = LarvaGlyphMovementIntegrationTests()
        char, monster, fight, deck, dispatcher = helper.fixture(target_distance=3)
        actor = fight.actors[7]
        # Test preparation grants four paid steps through the real resource API.
        from wakfu_server.combat_resource_pa_notifications import (
            set_resource_maximum,
            set_resource_current,
        )

        set_resource_maximum(fight, actor, 3, 6)
        set_resource_current(fight, actor, 3, 6)
        occupied = {a.position for a in fight.actors.values() if a.id != actor.id}

        def route(origin, seen):
            if len(seen) == steps:
                return seen
            for start, end in sorted(fight.edges):
                if (
                    start == origin
                    and end not in occupied
                    and end not in seen
                    and end != actor.position
                ):
                    found = route(end, [*seen, end])
                    if found is not None:
                        return found
            return None

        path = route(actor.position, [])
        self.assertIsNotNone(path)
        row = helper.install_glyph(fight, dispatcher, path[-1])

        def stats(current, state):
            if current.controlled:
                return actual_actor_stats(
                    char,
                    current,
                    state.id,
                    wp_current=current.effect_stats[4],
                    wp_maximum=current.effect_maxima[4],
                    fight=state,
                )
            return actual_monster_actor_stats(
                monster,
                current,
                state.id,
                wp_current=current.effect_stats[4],
                wp_maximum=current.effect_maxima[4],
                fight=state,
            )

        runtime = RuntimeMessages(fight, runtime_stats_serializer=stats)
        return char, monster, fight, deck, path, row, runtime, stats

    def state(self, shared):
        runtime = shared.runtime
        return (
            source_snapshot(shared.fight),
            shared.sequence,
            deepcopy(vars(shared.ack)),
            runtime.action_id,
            runtime.native_action_id,
            runtime.awaiting_ack,
            tuple(runtime.pending),
            runtime.last_native_delivery,
            {
                k: tuple((b.sequence, b.packets) for b in batches)
                for k, batches in shared.outboxes.items()
            },
        )

    def run_case(self, steps, enabled, *, failure=False, custom=False, direct=False):
        char, monster, fight, deck, path, row, runtime, stats = self.fixture(steps)
        session = Session(3, 7, "owned-movement", 1134, 0)
        registry = Registry(lambda current: current == session)
        shared = registry.register(fight, session, runtime=runtime)
        before = self.state(shared)
        calls = []
        rng = Random(9)

        def provider(preview, **boundary):
            result = prepare_area_movement(
                char, {-7: monster}, preview, deck, rng=rng, **boundary
            )
            calls.append((tuple(boundary["path"]), result[0] is preview))
            if failure and len(calls) == 3:
                raise ValueError("later native step failed")
            return result

        # A different callback than the explicitly certified one must not inherit its lease.
        def custom_provider(preview, **boundary):
            return provider(preview, **boundary)

        supplied = custom_provider if custom else provider
        body = struct.pack(">q", 7) + b"".join(
            struct.pack(">iih", *cell) for cell in path
        )
        events = []

        def operation(candidate, private):
            with owned_native_movement(private, provider, enabled=enabled):
                packets, event = apply_client(
                    private,
                    3,
                    body,
                    lambda actor: stats(actor, private.fight),
                    runtime_stats_serializer=stats,
                    area_provider=supplied,
                )
                packets = private.prepare_delivery(packets)
                events.append(event)
                return Transition(candidate, private, tuple(packets))

        counts = [0, 0]
        codes = (Fight.__deepcopy__.__code__, RuntimeMessages.__deepcopy__.__code__)

        def profile(frame, event, arg):
            if event == "call":
                for i, code in enumerate(codes):
                    if frame.f_code is code:
                        counts[i] += 1

        sys.setprofile(profile)
        try:
            if failure:
                with self.assertRaisesRegex(ValueError, "later native step failed"):
                    registry.execute(fight.id, session, 7, operation)
            elif direct:
                operation(fight, runtime)
            else:
                registry.execute(fight.id, session, 7, operation)
        finally:
            sys.setprofile(None)
        if failure:
            self.assertEqual(self.state(shared), before)
            self.assertIs(shared.fight, fight)
            self.assertIs(shared.runtime, runtime)
            self.assertEqual(len(calls), 3)
        else:
            self.assertEqual(events[0]["path"], path)
            self.assertEqual(len(calls), steps)
            self.assertNotIn(row["uid"], shared.fight.native_effect_areas)
        return self.state(shared), counts, calls

    def test_registry_native_steps_equivalence_counts_failure_and_fallback(self):
        for steps in (1, 4):
            baseline, old, oldcalls = self.run_case(steps, False)
            candidate, new, newcalls = self.run_case(steps, True)
            self.assertEqual(baseline, candidate)
            self.assertEqual(old[0], new[0] + steps)
            self.assertEqual(old[1], new[1])  # _with_areas runtime copy remains.
            self.assertTrue(all(not same for _, same in oldcalls))
            self.assertTrue(all(same for _, same in newcalls))
        self.run_case(4, True, failure=True)
        _, _, custom = self.run_case(1, True, custom=True)
        self.assertFalse(custom[0][1])
        _, _, direct = self.run_case(1, True, direct=True)
        self.assertFalse(direct[0][1])
