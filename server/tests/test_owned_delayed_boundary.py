"""A real first-aid-food delayed 321 runner crosses owned turn delivery."""
from contextlib import nullcontext
from copy import deepcopy
import json
from random import Random
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

_SERVER = Path(__file__).resolve().parents[1]
for _fixture_path in (_SERVER / "tests",):
    if str(_fixture_path) not in sys.path:
        sys.path.insert(0, str(_fixture_path))

from tests.native_callback_handoff_fixture import NativeCallbackHandoffTests
from tests import native_oracle_fixture as native_fixture
from wakfu_server import combat_native_action_ids as action_ids
from wakfu_server import combat_native_delay_queue as delay_queue
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_server_spell import prepare_server_initialization
from wakfu_server.combat_area_boundary import adopt_fight
from wakfu_server.paths import DATA_ROOT


class OwnedDelayedBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        NativeCallbackHandoffTests.setUpClass()

    def test_real_food_delayed_delivery_equivalence_and_outer_failure_rollback(self):
        fixture, original, decks = NativeCallbackHandoffTests().runtime_for()
        catalog = json.loads((DATA_ROOT / "native-consumable-actions.json").read_text())
        food = next(
            row["plan"]["states"][0]
            for row in catalog["items"]
            if row["item_ref"] == 13858
        )
        row = dict(
            uid=903,
            state_id=food["state_id"],
            level=food["level"],
            clock="event",
            duration_ms=0,
            remaining_ms=0,
            effect_ids=tuple(food["effect_ids"]),
            metadata=food["metadata"],
        )
        character = dict(fixture.character, consumable_states=[row])
        prepared, _ = prepare_server_initialization(
            character,
            {fixture.monster["id"]: fixture.monster},
            original.fight,
            character["account_id"],
            decks[character["id"]],
            action_id=1,
            rng=Random(1),
            fight_start=False,
        )
        adopt_fight(original.fight, prepared)
        (pending,) = original.fight.native_delay_queue["entries"]
        self.assertEqual(pending["clock_id"], fixture.pc.id)
        self.assertEqual(pending["phase"], "start")
        uid = pending["uid"]
        self.assertEqual(
            original.fight.native_owned_group_effects[uid]["effect_class"], 321
        )
        # Place the existing native timeline at the queued clock's actual due
        # boundary. No queue UID, producer, timer or invocation is fabricated.
        original.fight.order = [fixture.npc.id, fixture.pc.id]
        original.fight.turn_index = 0
        original.fight.turn_id = 1
        original.fight.native_timeline_round = pending["round"]
        original.fight.native_start_event_delivered = True
        original.fight.actors[fixture.npc.id].turn_count = pending["round"]
        original.fight.actors[fixture.pc.id].turn_count = pending["round"] - 1
        results = []
        for enabled in (False, True):
            runtime = deepcopy(original)
            oracle = native_fixture.NativeOracleTests.oracle_for(
                runtime,
                fixture.character,
                fixture.monster,
                decks[fixture.character["id"]],
            )
            disable = (
                nullcontext()
                if enabled
                else patch.object(
                    action_ids, "owned_native_delivery_fight", return_value=None
                )
            )
            with disable, patch(
                "wakfu_server.combat_runtime_messages.wall_time", return_value=1234.5
            ):
                packets = oracle.commit(
                    {"type": "end_turn"}, stats_serializer=runtime.stats_serializer
                )
            self.assertEqual(runtime.fight.native_delay_queue["entries"], [])
            self.assertNotIn(uid, runtime.fight.native_owned_group_effects)
            self.assertFalse(
                any(
                    entry.reference == food["state_id"]
                    for entry in runtime.fight.actors[
                        fixture.pc.id
                    ].state_ledger.entries
                )
            )
            results.append(
                (
                    tuple(packets),
                    source_snapshot(runtime.fight),
                    runtime.action_id,
                    runtime.awaiting_ack,
                    tuple(runtime.pending),
                )
            )
        self.assertEqual(*results)
        # A delayed runner may have been registered by an earlier owned turn
        # event. Its original provenance remains in both retained copies, but
        # that event is no longer the current turn when the runner executes.
        stale = deepcopy(original)
        old_context = dict(
            policy="wakemu.owned-turn-boundary-facts-v1",
            actor_id=fixture.pc.id,
            turn_id=0,
            phase="start",
            event_id=1001,
        )
        retained = stale.fight.native_owned_group_effects[uid]["invocation"]
        queued = stale.fight.native_delay_queue["entries"][0]["invocation"]
        retained["native_turn_boundary_context"] = deepcopy(old_context)
        queued["native_turn_boundary_context"] = deepcopy(old_context)
        self.assertEqual(retained, queued)
        broken = deepcopy(stale)
        broken.fight.native_delay_queue["entries"][0]["invocation"][
            "native_turn_boundary_context"
        ]["turn_id"] += 1
        broken_oracle = native_fixture.NativeOracleTests.oracle_for(
            broken, fixture.character, fixture.monster, decks[fixture.character["id"]]
        )
        with self.assertRaisesRegex(ValueError, "retained delayed Qe authority"):
            broken_oracle.commit(
                {"type": "end_turn"}, stats_serializer=broken.stats_serializer
            )
        stale_oracle = native_fixture.NativeOracleTests.oracle_for(
            stale, fixture.character, fixture.monster, decks[fixture.character["id"]]
        )
        with patch(
            "wakfu_server.combat_runtime_messages.wall_time", return_value=1234.5
        ):
            stale_packets = stale_oracle.commit(
                {"type": "end_turn"}, stats_serializer=stale.stats_serializer
            )
        self.assertEqual(tuple(stale_packets), results[1][0])
        self.assertEqual(stale.fight.native_delay_queue["entries"], [])
        self.assertNotIn(uid, stale.fight.native_owned_group_effects)
        self.assertEqual(retained["native_turn_boundary_context"], old_context)
        self.assertEqual(queued["native_turn_boundary_context"], old_context)
        runtime = deepcopy(original)
        oracle = native_fixture.NativeOracleTests.oracle_for(
            runtime, fixture.character, fixture.monster, decks[fixture.character["id"]]
        )
        before = (
            source_snapshot(runtime.fight),
            runtime.action_id,
            tuple(runtime.pending),
            runtime.awaiting_ack,
        )
        called = []
        real_deliver = delay_queue.deliver

        def fail_after_callback(queue, **kwargs):
            execute = kwargs["execute"]

            def callback(item):
                result = execute(item)
                called.append(item["uid"])
                raise RuntimeError("after real delayed callback")

            return real_deliver(queue, **dict(kwargs, execute=callback))

        # NativeDelayedEffects imports the delivery function once; replace that
        # invocation seam, while keeping native queue validation/execution intact.
        with patch(
            "wakfu_server.combat_native_delayed_effects.deliver",
            side_effect=fail_after_callback,
        ):
            with self.assertRaisesRegex(RuntimeError, "after real delayed callback"):
                oracle.commit(
                    {"type": "end_turn"}, stats_serializer=runtime.stats_serializer
                )
        self.assertIn(uid, called)
        self.assertEqual(
            before,
            (
                source_snapshot(runtime.fight),
                runtime.action_id,
                tuple(runtime.pending),
                runtime.awaiting_ack,
            ),
        )


if __name__ == "__main__":
    unittest.main()
