import ast
import os
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from wakfu_server.combat_orientation import apply, decode_request, response
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Actor, Fight


def extracted_session_orientation(namespace):
    namespace.setdefault("struct", struct)
    from types import SimpleNamespace

    namespace.setdefault(
        "POSITIONS",
        SimpleNamespace(flush=lambda **_kwargs: None, attach=lambda *_args: None),
    )
    namespace.setdefault(
        "WORLD", SimpleNamespace(update=lambda *_args, **_kwargs: None)
    )
    namespace.setdefault("STORE", object())
    namespace.setdefault("generation", 1)
    source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
    source = source_path.read_text()
    tree = ast.parse(source, filename=str(source_path))
    session = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )

    def is_combat_orientation_branch(node):
        if not isinstance(node, ast.If):
            return False
        comparisons = [
            value for value in ast.walk(node.test) if isinstance(value, ast.Compare)
        ]
        opcode_match = any(
            isinstance(value.left, ast.Name)
            and value.left.id == "opcode"
            and any(
                isinstance(part, ast.Constant) and part.value == 13655
                for part in value.comparators
            )
            for value in comparisons
        )
        combat_match = any(
            isinstance(value.left, ast.Name)
            and value.left.id == "fight"
            and isinstance(value.ops[0], ast.IsNot)
            and any(
                isinstance(part, ast.Constant) and part.value is None
                for part in value.comparators
            )
            for value in comparisons
        )
        return opcode_match and combat_match

    branch = next(
        node for node in ast.walk(session) if is_combat_orientation_branch(node)
    )
    branch.orelse = []
    args = (
        "opcode",
        "fight",
        "fight_messages",
        "body",
        "account_id",
        "connection",
        "service",
        "send",
        "record",
        "checkpoint_fight",
    )
    function = ast.FunctionDef(
        name="handle_orientation",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg=name) for name in args],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Nonlocal(names=["character"]),
            branch,
            ast.Return(value=ast.Name(id="fight_messages", ctx=ast.Load())),
        ],
        decorator_list=[],
    )
    factory = ast.FunctionDef(
        name="_make_orientation_handler",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="character")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            function,
            ast.Return(value=ast.Name(id="handle_orientation", ctx=ast.Load())),
        ],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[]))
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace["_make_orientation_handler"](namespace.get("character"))


class OrientationTests(unittest.TestCase):
    def runtime(self, *, companion_owner=None):
        cells = {(x, 0, 0) for x in range(5)}
        pc = Actor(-7, 0, (0, 0, 0), 60, 6, 4, 100, 1, 9, True)
        actors = [pc]
        team_zero_cells = {pc.position}
        if companion_owner is not None:
            companion = Actor(-8, 0, (1, 0, 0), 60, 6, 4, 50, 1, companion_owner, True)
            actors.append(companion)
            team_zero_cells.add(companion.position)
        npc = Actor(2, 1, (2, 0, 0), 10, 3, 3, 0, 1)
        actors.append(npc)
        fight = Fight(3, actors, cells, {0: team_zero_cells, 1: {npc.position}})
        return RuntimeMessages(fight), pc

    def test_all_cardinals_during_placement_cost_no_ap_mp_and_need_no_ack(self):
        runtime, actor = self.runtime()
        self.assertEqual(runtime.fight.phase, "placement")
        for action, direction in enumerate((1, 3, 5, 7), 1):
            result = apply(runtime, 9, struct.pack(">qB", -7, direction))
            self.assertEqual(
                [opcode for opcode, _ in result["packets"]], [13494, 13420]
            )
            self.assertEqual(
                struct.unpack(">iiiqB", result["packets"][0][1]),
                (3, action, -1, -7, direction),
            )
            self.assertEqual(result["direction"], direction)
            self.assertEqual(result["event"]["cost_ap"], 0)
            self.assertEqual(result["event"]["cost_mp"], 0)
            self.assertIsNone(runtime.awaiting_ack)
            self.assertEqual((actor.ap, actor.mp), (6, 4))
        self.assertEqual(actor.position, (0, 0, 0))

    def test_server_orientation_handler_and_ready_bootstrap_keep_native_ids_unique(
        self,
    ):
        from wakfu_server.combat_native_action_ids import (
            MAX_NATIVE_ACTION_ID,
            NATIVE_ACTION_PACKETS,
        )
        from wakfu_server.combat_ready import prepare_ready

        runtime, actor = self.runtime()
        sent = []
        namespace = {"character": {"id": 9}}
        handler = extracted_session_orientation(namespace)
        connection = object()
        with patch(
            "wakfu_server.world_orientation.save",
            side_effect=lambda _store, _account, _generation, actor_id, direction, **_kw: {
                "direction": direction,
                "packet": (12401, struct.pack(">qB", actor_id, direction)),
            },
        ):
            for direction in (1, 3, 5, 7):
                runtime = handler(
                    13655,
                    runtime.fight,
                    runtime,
                    struct.pack(">qB", actor.id, direction),
                    9,
                    connection,
                    "world",
                    lambda _connection, _service, opcode, payload: sent.append(
                        (opcode, payload)
                    ),
                    lambda **_event: None,
                    lambda: None,
                )

        placement_ids = [
            struct.unpack_from(">i", payload, 4)[0]
            for opcode, payload in sent
            if opcode in NATIVE_ACTION_PACKETS
        ]
        self.assertEqual(placement_ids, [1, 2, 3, 4])
        candidate, ready_runtime, ready_packets = prepare_ready(
            runtime.fight,
            9,
            True,
            initialize=lambda preview, _action: (preview, ()),
            stats_serializer=lambda _actor: b"stats",
            effects_serializer=lambda: b"effects",
            previous_native_action_id=runtime.native_action_id,
        )
        self.assertEqual(candidate.phase, "active")
        ready_ids = [
            struct.unpack_from(">i", payload, 4)[0]
            for opcode, payload in ready_packets
            if opcode in NATIVE_ACTION_PACKETS
        ]
        self.assertTrue(ready_ids)
        self.assertEqual(ready_ids, list(range(5, 5 + len(ready_ids))))
        self.assertEqual(ready_runtime.native_action_id, ready_ids[-1])
        self.assertEqual(
            len(set(placement_ids + ready_ids)), len(placement_ids + ready_ids)
        )

        with self.assertRaisesRegex(ValueError, "sequence exhausted"):
            prepare_ready(
                runtime.fight,
                9,
                True,
                initialize=lambda preview, _action: (preview, ()),
                stats_serializer=lambda _actor: b"stats",
                effects_serializer=lambda: b"effects",
                previous_native_action_id=MAX_NATIVE_ACTION_ID,
            )
        self.assertEqual(runtime.fight.phase, "placement")

    def test_orientation_ready_real_unarmed_cast_and_ack_share_one_native_id_sequence(
        self,
    ):
        import copy

        from test_combat_melee import UnarmedTests
        from wakfu_server.combat_native_action_ids import NATIVE_ACTION_PACKETS
        from wakfu_server.combat_ready import prepare_ready
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        melee = UnarmedTests()
        melee.setUp()
        actors = [copy.deepcopy(melee.pc), copy.deepcopy(melee.npc)]
        fight = Fight(
            1,
            actors,
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.native_effect_uid_next = 1
        runtime = RuntimeMessages(fight)
        sent = []
        handler = extracted_session_orientation({"character": {"id": 7}})
        with patch(
            "wakfu_server.world_orientation.save",
            side_effect=lambda _store, _account, _generation, actor_id, direction, **_kw: {
                "direction": direction,
                "packet": (12401, struct.pack(">qB", actor_id, direction)),
            },
        ):
            for direction in (1, 3, 5, 7):
                runtime = handler(
                    13655,
                    fight,
                    runtime,
                    struct.pack(">qB", 7, direction),
                    9,
                    object(),
                    "world",
                    lambda _connection, _service, opcode, payload: sent.append(
                        (opcode, payload)
                    ),
                    lambda **_event: None,
                    lambda: None,
                )

        candidate, ready_runtime, ready_packets = prepare_ready(
            fight,
            9,
            True,
            initialize=lambda preview, _action: (preview, ()),
            stats_serializer=lambda _actor: b"stats",
            effects_serializer=lambda: b"effects",
            previous_native_action_id=runtime.native_action_id,
        )
        self.assertEqual(candidate.phase, "active")
        melee.fight = candidate
        melee.pc = candidate.actors[7]
        melee.npc = candidate.actors[-7]
        transaction = melee.run_attack(
            action_id=ready_runtime.action_id + 1,
            effect_uid=1,
            prepare_only=True,
        )
        cast_packets = commit_spell_transaction(
            ready_runtime, transaction, stats_serializer=lambda *_args: b"stats"
        )
        turn_packets = ready_runtime.end_turn(9, 7, candidate.actors[7].turn_count)
        ack_packets = ready_runtime.acknowledge_turn(
            struct.pack(">i", ready_runtime.awaiting_ack)
        )

        packet_batches = [sent, ready_packets, cast_packets, turn_packets, ack_packets]
        ids = [
            struct.unpack_from(">i", payload, 4)[0]
            for batch in packet_batches
            for opcode, payload in batch
            if opcode in NATIVE_ACTION_PACKETS
        ]
        self.assertGreater(len(ids), 8)
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        self.assertEqual(ready_runtime.native_action_id, ids[-1])

    def test_active_orientation_requires_current_owned_actor_and_tracks_turn_change(
        self,
    ):
        runtime, actor = self.runtime(companion_owner=9)
        runtime.fight.ready(9)
        self.assertEqual(runtime.fight.phase, "active")
        self.assertIs(runtime.fight.current, actor)
        apply(runtime, 9, struct.pack(">qB", actor.id, 3))
        action_id = runtime.action_id
        runtime.fight._advance()
        runtime.fight._advance()
        self.assertEqual(runtime.fight.current.id, -8)
        with self.assertRaisesRegex(ValueError, "does not have the turn"):
            apply(runtime, 9, struct.pack(">qB", actor.id, 5))
        self.assertEqual(runtime.action_id, action_id)
        result = apply(runtime, 9, struct.pack(">qB", -8, 7))
        self.assertEqual(result["direction"], 7)

    def test_rejects_foreign_npc_ready_owner_outside_area_finished_and_pending_ack(
        self,
    ):
        runtime, actor = self.runtime()
        cases = []
        cases.append((runtime, 9, struct.pack(">qB", 2, 1), "controlled"))

        ready_runtime, _ = self.runtime(companion_owner=10)
        ready_runtime.fight.ready(9)
        cases.append((ready_runtime, 9, struct.pack(">qB", -7, 1), "already ready"))

        outside_runtime, outside_actor = self.runtime()
        outside_actor.position = (4, 0, 0)
        cases.append(
            (
                outside_runtime,
                9,
                struct.pack(">qB", -7, 1),
                "outside its placement area",
            )
        )

        finished_runtime, _ = self.runtime()
        finished_runtime.fight.phase = "finished"
        cases.append(
            (
                finished_runtime,
                9,
                struct.pack(">qB", -7, 1),
                "placement or an active turn",
            )
        )

        ack_runtime, _ = self.runtime()
        ack_runtime.awaiting_ack = 17
        cases.append(
            (ack_runtime, 9, struct.pack(">qB", -7, 1), "synchronized combat state")
        )

        for candidate, owner, body, message in cases:
            with self.subTest(message=message):
                action_id = candidate.action_id
                with self.assertRaisesRegex(ValueError, message):
                    apply(candidate, owner, body)
                self.assertEqual(candidate.action_id, action_id)

    def test_invalid_owner_and_malformed_requests_do_not_mutate(self):
        runtime, actor = self.runtime()
        initial_direction = actor.direction
        body = struct.pack(">qB", -7, 1)
        for owner, request in ((8, body), (9, struct.pack(">qB", 2, 1))):
            with self.assertRaises(ValueError):
                apply(runtime, owner, request)
            self.assertEqual(actor.direction, initial_direction)
        for malformed in (
            b"",
            struct.pack(">qB", -7, 0),
            struct.pack(">qB", -7, 8),
            struct.pack(">qB", 0, 1),
        ):
            with self.assertRaises(ValueError):
                decode_request(malformed)
        runtime.action_id = (1 << 31) - 1
        with self.assertRaises(ValueError):
            apply(runtime, 9, body)
        self.assertEqual(actor.direction, initial_direction)

    def test_response_layout_validates_native_ranges(self):
        packet = response(3, 1, -7, 5)
        self.assertEqual(packet[0], 13494)
        self.assertEqual(struct.unpack(">iiiqB", packet[1]), (3, 1, -1, -7, 5))
        for args in ((3, 0, -7, 1), (1 << 31, 1, -7, 1), (3, 1, -7, 2)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                response(*args)


if __name__ == "__main__":
    unittest.main()
