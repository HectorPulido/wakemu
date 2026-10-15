"""Movement followups publish native PCs without replaying POSITION."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import struct
import sys
import unittest
from unittest.mock import patch

from test_combat_movement_runtime import MovementRuntimeTests, AIMovementRuntimeTests
from wakfu_server.combat_movement_runtime import (
    apply_client,
    apply_ai,
    movement_stats_snapshot,
)
from wakfu_server.combat_wire import decode_actor_state
from wakfu_server.combat_actor import actor_stats, monster_actor_stats
from wakfu_server.combat_characteristic_snapshot import characteristics_only_snapshot


def full_stats(actor, state=None):
    rows = [(2, actor.ap, 0, actor.max_ap, 0), (3, actor.mp, 0, actor.max_mp, 0)]
    table = struct.pack(">H", len(rows)) + b"".join(
        struct.pack(">Biiii", *row) for row in rows
    )
    record = dict(
        id=actor.id,
        account_id=7,
        level=1,
        breed=3,
        hp=actor.hp,
        max_hp=actor.max_hp,
        x=actor.position[0],
        y=actor.position[1],
        z=actor.position[2],
        map_id=1,
        team=actor.team,
        ref=1,
    )
    if actor.controlled:
        authority = getattr(actor, "native_controlled_by_ai", None)
        if authority is None:
            authority = False
        return actor_stats(
            record,
            2,
            actor.team,
            wp=0,
            direction=getattr(actor, "direction", None) or 0,
            characteristics_payload=table,
            native_controlled_by_ai=authority,
        )
    return monster_actor_stats(
        record, 2, characteristics_payload=table, fight_property_counts={}
    )


def publications(packets):
    return [decode_actor_state(op, body) for op, body in packets if op == 12873]


class MovementCharacteristicPublicationTests(unittest.TestCase):
    def test_nonmover_direction_change_retains_full_position(self):
        _, actor = MovementRuntimeTests().setup_fight()
        before = full_stats(actor)
        actor.direction = 3
        after = full_stats(actor)
        self.assertEqual(
            movement_stats_snapshot(after, before, position_owned=False), after
        )
        self.assertEqual(movement_stats_snapshot(after, before)[0], 40)

    def test_player_movement_publishes_paid_resources_without_position(self):
        runtime, actor = MovementRuntimeTests().setup_fight()
        packets, event = apply_client(
            runtime, 7, struct.pack(">qiih", actor.id, 1, 0, 0), full_stats
        )
        state = publications(packets)[0]["state"]
        self.assertEqual(state[0], 40)
        self.assertEqual(state, characteristics_only_snapshot(full_stats(actor)))
        self.assertEqual((actor.position, actor.mp, event["cost"]), ((1, 0, 0), 2, 1))
        self.assertEqual([op for op, _ in packets], [13624, 13420, 12873])

    def test_npc_movement_publishes_paid_resources_without_position(self):
        runtime, actor = AIMovementRuntimeTests().setup_fight()
        plan = {"path": [(1, 0, 0), (2, 0, 0), (3, 0, 0)], "attack": None}
        with patch("wakfu_server.combat_ai.plan", return_value=plan):
            packets, result = apply_ai(runtime, full_stats, direction=2)
        state = publications(packets)[0]["state"]
        self.assertEqual(state[0], 40)
        self.assertEqual(state, characteristics_only_snapshot(full_stats(actor)))
        self.assertEqual((actor.mp, result["event"]["cost"]), (0, 3))

    def test_area_callbacks_precede_partial_snapshot_with_final_resources(self):
        runtime, actor = MovementRuntimeTests().setup_fight()

        def area(state, **boundary):
            state = deepcopy(state)
            state.actors[actor.id].ap -= 2
            return state, [(12613, b"owned-relative-AP")]

        packets, _ = apply_client(
            runtime,
            7,
            struct.pack(">qiih", actor.id, 1, 0, 0),
            full_stats,
            area_provider=area,
        )
        state = publications(packets)[0]["state"]
        self.assertEqual(state[0], 40)
        self.assertEqual(struct.unpack_from(">i", state, 4)[0], actor.ap)
        self.assertLess(
            next(i for i, p in enumerate(packets) if p[0] == 12613),
            next(i for i, p in enumerate(packets) if p[0] == 12873),
        )

    def test_area_control_change_keeps_full_native_actor_state(self):
        runtime, actor = MovementRuntimeTests().setup_fight()

        def area(state, **boundary):
            state = deepcopy(state)
            state.actors[actor.id].native_controlled_by_ai = True
            return state, []

        packets, _ = apply_client(
            runtime,
            7,
            struct.pack(">qiih", actor.id, 1, 0, 0),
            full_stats,
            area_provider=area,
        )
        state = publications(packets)[0]["state"]
        self.assertEqual(state[0], 3)
        table_end = 39 + 2 + 2 * 17
        self.assertEqual(state[table_end], 1)

    def test_both_native_ai_commit_paths_project_movement_followups(self):
        from wakfu_server.combat_tactical_ai import NativeProvider, Preview

        ai_root = str(Path(__file__).resolve().parents[1] / "ai-service")
        if ai_root not in sys.path:
            sys.path.insert(0, ai_root)
        from wakfu_ai.native.native_oracle import NativeOracle

        for oracle_path in (False, True):
            with self.subTest(oracle=oracle_path):
                runtime, actor = AIMovementRuntimeTests().setup_fight()
                candidate = deepcopy(runtime)
                candidate.fight.server_move(actor.id, [(1, 0, 0)])
                candidate.action_id = 1
                if oracle_path:
                    oracle = object.__new__(NativeOracle)
                    oracle.runtime = runtime
                    oracle.flags = {}
                    oracle.authorities = lambda state: {}
                    oracle.preview = lambda *args, **kwargs: (candidate, [], None)
                    with patch("wakfu_ai.native.native_oracle.check"), patch(
                        "wakfu_ai.native.native_oracle.complete_fingerprint",
                        return_value="owned",
                    ):
                        packets = oracle.commit(
                            {"type": "move"}, stats_serializer=full_stats
                        )
                else:
                    provider = SimpleNamespace(
                        area_provider=None,
                        preview=lambda *args, **kwargs: Preview(candidate.fight),
                    )
                    with patch(
                        "wakfu_server.combat_tactical_ai._source_key",
                        return_value="owned",
                    ):
                        packets = NativeProvider.commit(
                            provider, runtime, {"type": "move"}, full_stats
                        )
                self.assertEqual(len(publications(packets)), 2)
                self.assertTrue(
                    all(row["state"][0] == 40 for row in publications(packets))
                )
                self.assertEqual(runtime.fight.actors[actor.id].mp, 2)


if __name__ == "__main__":
    unittest.main()
