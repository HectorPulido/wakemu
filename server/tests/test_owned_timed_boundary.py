"""Native outer delivery owns expiration and Oracle boundary previews."""
from contextlib import nullcontext
from copy import deepcopy, _reconstruct
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

# Reuse native fixtures through the production module namespaces.
_SERVER = Path(__file__).resolve().parents[1]
for _fixture_path in (_SERVER / "tests",):
    if str(_fixture_path) not in sys.path:
        sys.path.insert(0, str(_fixture_path))

from tests.native_callback_handoff_fixture import NativeCallbackHandoffTests
from tests import native_oracle_fixture as native_fixture
from test_combat_timed_expiration import TimedExpirationTests
from wakfu_server import combat_native_action_ids as action_ids
from wakfu_server import combat_timed_expiration as expiration
from wakfu_server.combat_state import Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_stat_handler import NativeStatHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_geometry_snapshot import source_snapshot


class OwnedTimedBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        NativeCallbackHandoffTests.setUpClass()
        from test_combat_state_child_removal import StateChildRemovalTests
        from wakfu_server.spell_audit import states_catalog
        from wakfu_server.combat_static_catalogs import (
            DefinitionOverlay,
            characteristic_registry,
        )

        native = states_catalog()
        changed = dict(
            native["effects"]["150327"],
            effect_class=120,
            parameters=[0, 1],
            parameter_count=1,
        )
        StateChildRemovalTests.catalog = dict(
            native, effects=DefinitionOverlay(native["effects"], {"150327": changed})
        )
        StateChildRemovalTests.registry = characteristic_registry()

    def setup_runtime(self):
        fixture, runtime, decks = NativeCallbackHandoffTests().runtime_for()
        fight = runtime.fight
        fight.order = [fixture.pc.id, fixture.npc.id]
        fight.turn_index = 0
        fight.turn_id = 1
        fight.native_start_event_delivered = True
        fixture.pc.turn_count = 1
        fixture.npc.turn_count = 0
        actor = fight.actors[fixture.npc.id]
        fixture.initial_stat_27 = actor.effect_stats[27]
        factory = runtime.expiration_runtime_factory(action_id=1)
        dispatcher, _packets = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        before = set(fight.owned_stat_effects)
        dispatcher.execute(
            EffectInvocation(317002, 1, fixture.pc.id, actor.id, actor.position)
        )
        (uid,) = set(fight.owned_stat_effects) - before
        fight.owned_stat_effects[uid]["timer"] = dict(
            actor_id=fixture.pc.id, expiration_round=1, phase="end"
        )
        return fixture, runtime, decks, uid

    def oracle(self, fixture, runtime, decks):
        return native_fixture.NativeOracleTests.oracle_for(
            runtime, fixture.character, fixture.monster, decks[fixture.character["id"]]
        )

    def test_native_expiration_boundary_equivalence_copy_reduction_and_rollback(self):
        fixture, original, decks, uid = self.setup_runtime()
        # Forecast never receives an in-place boundary, independently of
        # the otherwise valid native callback owner.
        from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import (
            _owned_live_boundary_fight,
        )

        lifecycle = original.turn_end_provider.__self__
        self.assertIsNone(
            _owned_live_boundary_fight(lifecycle, original.fight, "end", True)
        )
        self.assertIsNone(
            action_ids.owned_native_delivery_fight(original, original.fight)
        )
        results = []
        for enabled in (False, True):
            runtime = deepcopy(original)
            oracle = self.oracle(fixture, runtime, decks)
            copies = []
            runtime_copies = []

            def profile(frame, event, arg):
                if event == "call" and frame.f_code is Fight.__deepcopy__.__code__:
                    copies.append(True)
                if (
                    event == "call"
                    and frame.f_code is _reconstruct.__code__
                    and type(frame.f_locals.get("x")) is RuntimeMessages
                ):
                    runtime_copies.append(True)

            disable = (
                nullcontext()
                if enabled
                else patch.object(
                    action_ids, "owned_native_delivery_fight", return_value=None
                )
            )
            previous = sys.getprofile()
            try:
                with disable, patch(
                    "wakfu_server.combat_runtime_messages.wall_time",
                    return_value=1234.5,
                ):
                    sys.setprofile(profile)
                    packets = oracle.commit(
                        {"type": "end_turn"}, stats_serializer=runtime.stats_serializer
                    )
            finally:
                sys.setprofile(previous)
            print(
                {
                    "scope": "NativeOracle.commit(end_turn)",
                    "enabled": enabled,
                    "fight_deepcopies": len(copies),
                    "runtime_deepcopies": len(runtime_copies),
                }
            )
            self.assertNotIn(uid, runtime.fight.owned_stat_effects)
            self.assertEqual(
                runtime.fight.actors[fixture.npc.id].effect_stats[27],
                fixture.initial_stat_27,
            )
            self.assertIsNotNone(runtime.awaiting_ack)
            self.assertTrue(runtime.pending)
            results.append(
                (
                    tuple(packets),
                    source_snapshot(runtime.fight),
                    runtime.action_id,
                    runtime.awaiting_ack,
                    tuple(runtime.pending),
                    len(copies),
                )
            )
        self.assertEqual(results[0][:-1], results[1][:-1])
        self.assertLess(results[1][-1], results[0][-1])
        # Native removal really executes before failure. The Oracle's outer
        # private transaction must not publish any of that partial mutation.
        runtime = deepcopy(original)
        oracle = self.oracle(fixture, runtime, decks)
        before = (
            source_snapshot(runtime.fight),
            runtime.action_id,
            tuple(runtime.pending),
            runtime.awaiting_ack,
        )
        removed = []
        real_remove = expiration.remove_owned_stat

        def fail_after_remove(handler, identity):
            real_remove(handler, identity)
            removed.append(identity)
            raise RuntimeError("after native expiration mutation")

        with patch.object(
            expiration, "remove_owned_stat", side_effect=fail_after_remove
        ):
            with self.assertRaisesRegex(RuntimeError, "after native expiration"):
                oracle.commit(
                    {"type": "end_turn"}, stats_serializer=runtime.stats_serializer
                )
        self.assertIn(uid, removed)
        self.assertEqual(
            before,
            (
                source_snapshot(runtime.fight),
                runtime.action_id,
                tuple(runtime.pending),
                runtime.awaiting_ack,
            ),
        )
        # Direct API keeps its existing dual ownership, even with a native factory.
        runtime = deepcopy(original)
        before = source_snapshot(runtime.fight)
        preview, packets = expiration.prepare_timed_expiration(
            runtime.fight,
            actor_id=fixture.pc.id,
            round_number=1,
            phase="end",
            action_id=4,
            runtime_factory=runtime.expiration_runtime_factory,
            _owned_runtime=runtime,
        )
        self.assertIsNot(preview, runtime.fight)
        self.assertEqual(before, source_snapshot(runtime.fight))
        self.assertNotIn(uid, preview.owned_stat_effects)
        custom = lambda **kw: runtime.expiration_runtime_factory(**kw)
        self.assertFalse(
            expiration._owns_expiration_preview(runtime.fight, runtime, custom)
        )
        # Same-object providers cannot hide a removed actor by mutating both
        # sides of a post-operation roster comparison.
        runtime = deepcopy(original)

        def remove_actor_in_place(fight, **_kwargs):
            del fight.actors[fixture.npc.id]
            fight.phase = "finished"
            return fight, []

        runtime.turn_end_provider = remove_actor_in_place
        with self.assertRaisesRegex(ValueError, "Turn-end policy removed an actor"):
            runtime._end_owned(runtime.fight.actors[fixture.pc.id])
        runtime = deepcopy(original)
        with patch.object(
            expiration, "prepare_timed_expiration", side_effect=remove_actor_in_place
        ):
            with self.assertRaisesRegex(ValueError, "Expiration changed actor roster"):
                expiration.expire_timed_effects(runtime.fight)
        # Actual state-owned child expiration retains its direct rollback/order contract.
        TimedExpirationTests().test_state_expiration_removes_child_before_carrier_and_atomic_missing_payload()


if __name__ == "__main__":
    unittest.main()
