"""Native timed area/parent removals use the same closure and packets locally."""
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
import random
import sys
import unittest
from unittest.mock import patch
from test_combat_area_timed_expiration import AreaTimedExpirationTests
from wakfu_server import combat_timed_expiration as expiration
from wakfu_server.combat_retained_effects import NativeRetainedEffectView
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_server_spell import server_runtime
from wakfu_server.combat_state_timing import StateTimer
from wakfu_server.fight_checkpoint_store import snapshot


class TimedExpirationLocalRemovalTests(unittest.TestCase):
    def test_actual_area_parent_parity_locality_custom_order_and_atomic_failure(self):
        fixture = AreaTimedExpirationTests()
        original = fixture.fixture()
        character, monster, deck = fixture.runtime_source

        def factory(*, action_id):
            return server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=action_id,
                critical=False,
                rng=random.Random(1),
            )[0]

        def run(fight, enabled, runtime_factory=factory):
            counts = dict(full_view=0, view_constructor=0, managers=0)
            codes = {
                NativeRetainedRuntime.view.__code__: "full_view",
                NativeRetainedEffectView.__init__.__code__: "view_constructor",
                expiration.state_managers.__code__: "managers",
            }
            prior = sys.getprofile()

            def observe(frame, event, arg):
                if event == "call" and frame.f_code in codes:
                    counts[codes[frame.f_code]] += 1

            with (
                nullcontext()
                if enabled
                else patch.object(
                    expiration, "_native_expiration_retention", return_value=False
                )
            ):
                sys.setprofile(observe)
                try:
                    preview, packets = expiration.prepare_timed_expiration(
                        fight,
                        actor_id=7,
                        round_number=2,
                        phase="start",
                        action_id=3,
                        runtime_factory=runtime_factory,
                    )
                finally:
                    sys.setprofile(prior)
            return preview, packets, counts

        # Both normal area expiry and a due parent with indefinite area children
        # use real Feca runners, the native runtime factory and actual Qf removal.
        for parent_owned in (False, True):
            fight = deepcopy(original)
            if parent_owned:
                parent = next(
                    entry
                    for actor in fight.actors.values()
                    for entry in actor.state_ledger.entries
                    if entry.uid in fight.state_wire_payloads
                )
                manager = fight.actors[parent.target_id]
                manager.state_ledger._entries = tuple(
                    replace(
                        entry,
                        timer=StateTimer(7, 2, "start")
                        if entry.uid == parent.uid
                        else None,
                    )
                    for entry in manager.state_ledger.entries
                )
                for uid, child in fight.native_owned_area_effects.items():
                    child["timer"] = None
                    child["state_uid"] = parent.uid
                    record = fight.native_retained_records[uid]
                    record.update(
                        owner_uid=parent.uid,
                        container_present=True,
                        container_type=1,
                        container_id=parent.reference,
                    )
            before = snapshot(fight)
            old, old_packets, old_counts = run(fight, False)
            new, new_packets, new_counts = run(fight, True)
            self.assertEqual(new_packets, old_packets)
            self.assertEqual(snapshot(new), snapshot(old))
            from wakfu_server.combat_retained_collections import bound_collections

            old_owner, new_owner = bound_collections(vars(old)), bound_collections(
                vars(new)
            )
            self.assertIsNotNone(old_owner)
            self.assertIsNotNone(new_owner)
            self.assertEqual(new_owner.consistent(), old_owner.consistent())
            for field in (
                "managers",
                "by_manager",
                "source_counts",
                "unmatched",
                "by_owner_uid",
                "record_owners",
                "owner_opaque",
                "ordinals",
                "order_mismatch",
            ):
                self.assertEqual(
                    getattr(new_owner, field), getattr(old_owner, field), field
                )
            self.assertEqual(snapshot(fight), before)
            self.assertFalse(new.native_owned_area_effects)
            self.assertFalse(new.native_effect_areas)
            self.assertLess(
                new_counts["view_constructor"], old_counts["view_constructor"]
            )
            self.assertLess(new_counts["managers"], old_counts["managers"])
            if parent_owned:
                self.assertNotIn(parent.uid, new.state_wire_payloads)
            print(
                "timed_expiration_local_counts",
                dict(
                    parent_owned=parent_owned, baseline=old_counts, candidate=new_counts
                ),
            )

        # Supplied retention callbacks preserve their legacy invocation order.
        events = []

        def custom_factory(*, action_id):
            native = factory(action_id=action_id)

            def build(fight, context):
                dispatcher, packets = native(fight, context)
                retention = dispatcher.native_retention
                original_view, original_remove = retention.view, retention.removal

                def view():
                    events.append("view")
                    return original_view()

                def removal(current):
                    events.append("removal")
                    return original_remove(current)

                retention.view, retention.removal = view, removal
                return dispatcher, packets

            return build

        old, old_packets, _ = run(original, False, custom_factory)
        expected_events = list(events)
        events.clear()
        new, new_packets, _ = run(original, True, custom_factory)
        self.assertEqual(events, expected_events)
        self.assertIn("removal", events)
        self.assertEqual(new_packets, old_packets)
        self.assertEqual(snapshot(new), snapshot(old))

        broken = deepcopy(original)
        next(iter(broken.native_owned_area_effects.values()))["timer"]["actor_id"] = 999
        before = snapshot(broken)
        for enabled in (False, True):
            with self.assertRaisesRegex(ValueError, "area timer"):
                run(broken, enabled)
            self.assertEqual(snapshot(broken), before)

        # Inject failure after actual native removal, inside the private preview.
        # The caller's source must remain completely unchanged on both paths.
        from wakfu_server import combat_retained_runtime

        original_remove_now = combat_retained_runtime.remove_now
        removed = []

        def fail_after_remove(retention, view, uids, **kwargs):
            result = original_remove_now(retention, view, uids, **kwargs)
            removed.append(True)
            raise RuntimeError("after actual timed removal")

        before = snapshot(original)
        for enabled in (False, True):
            with patch.object(combat_retained_runtime, "remove_now", fail_after_remove):
                with self.assertRaisesRegex(RuntimeError, "after actual timed removal"):
                    run(original, enabled)
            self.assertEqual(snapshot(original), before)
        self.assertEqual(len(removed), 2)
