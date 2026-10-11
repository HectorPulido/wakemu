"""Original noncombat NPC positions, native sR masks and dispatcher boundaries."""
import ast
import copy
import struct
import unittest
from pathlib import Path

from wakfu_server.maps import npc_placements


CREATION_SOURCE = "eedbfd7561e0ae53398bab0eddd26bfac674fb77953d537cea4dbbecd9c4cd69"
DUNGEON_SOURCE = "0410af8f82ee3c8a209efca093d0ebbdaf477be9f35801b1a63d4559f4e381cb"


EXPECTED = (
    dict(
        actor_id=-1706442046308330,
        reference_id=5459,
        map_id=1385,
        x=20,
        y=17,
        z=1,
        direction=3,
        name_es="Otomai",
        visual_id=181404009,
        level=200,
        native_action_ids=[1244, 1239],
        source_sha256=CREATION_SOURCE,
        source_frame=1077,
    ),
    dict(
        actor_id=-1706442046308328,
        reference_id=5467,
        map_id=1385,
        x=12,
        y=32,
        z=1,
        direction=1,
        name_es="Kheperalia",
        visual_id=1111505467,
        level=200,
        native_action_ids=[1255],
        source_sha256=CREATION_SOURCE,
        source_frame=1077,
    ),
    dict(
        actor_id=-1706442046308322,
        reference_id=5461,
        map_id=1385,
        x=-17,
        y=-4,
        z=17,
        direction=3,
        name_es="Huly",
        visual_id=1111505461,
        level=200,
        native_action_ids=[1241, 1243],
        source_sha256=CREATION_SOURCE,
        source_frame=1154,
    ),
    dict(
        actor_id=-1706442046308339,
        reference_id=5460,
        map_id=1388,
        x=0,
        y=-19,
        z=3,
        direction=3,
        name_es="Airyna",
        visual_id=1111505460,
        level=200,
        native_action_ids=[1389, 1390, 1252],
        source_sha256=CREATION_SOURCE,
        source_frame=3785,
    ),
    dict(
        actor_id=-1706442035962340,
        reference_id=5458,
        map_id=1387,
        x=-12,
        y=0,
        z=2,
        direction=1,
        name_es="Grugaloragrán",
        visual_id=1111505458,
        level=300,
        native_action_ids=[1238],
        source_sha256=CREATION_SOURCE,
        source_frame=9303,
    ),
    dict(
        actor_id=-1724034232352690,
        reference_id=4590,
        map_id=1134,
        x=11,
        y=-13,
        z=0,
        direction=5,
        name_es="Guarda de Amakna",
        visual_id=150,
        level=1,
        native_action_ids=[],
        source_sha256=DUNGEON_SOURCE,
        source_frame=77,
    ),
    dict(
        actor_id=-1724034232352729,
        reference_id=4800,
        map_id=1134,
        x=-17,
        y=9,
        z=-1,
        direction=3,
        name_es="Wuan Tazo",
        visual_id=1300088,
        level=200,
        native_action_ids=[1002],
        source_sha256=DUNGEON_SOURCE,
        source_frame=77,
    ),
    dict(
        actor_id=-1724034232352753,
        reference_id=3819,
        map_id=1134,
        x=16,
        y=8,
        z=0,
        direction=1,
        name_es="Magnum Deskhalzo",
        visual_id=117903819,
        level=100,
        native_action_ids=[703],
        source_sha256=DUNGEON_SOURCE,
        source_frame=77,
    ),
    dict(
        actor_id=-1776810790485976,
        reference_id=4069,
        map_id=527,
        x=-219,
        y=-46,
        z=5,
        direction=3,
        name_es="B. Tóven",
        visual_id=1300086,
        level=200,
        native_action_ids=[798],
        source_sha256=DUNGEON_SOURCE,
        source_frame=208,
    ),
    dict(
        actor_id=-1776810790235521,
        reference_id=4399,
        map_id=9,
        x=0,
        y=-5,
        z=4,
        direction=1,
        name_es="Mod'Ulo",
        visual_id=144902070,
        level=1,
        native_action_ids=[884],
        source_sha256=DUNGEON_SOURCE,
        source_frame=1488,
    ),
)


def decode_spawn(packet):
    message_id, payload = packet
    if message_id != 12608 or payload[:2] != b"\x00\x01":
        raise ValueError("Unexpected actor envelope")
    count = struct.unpack_from(">H", payload, 0)[0]
    kind, actor_id, size = struct.unpack_from(">BqH", payload, 2)
    entity = payload[13:]
    if count != 1 or kind != 1 or size != len(entity) or entity[0] != 11:
        raise ValueError("Invalid native format11 actor")
    cursor = 1
    (inner_actor_id,) = struct.unpack_from(">q", entity, cursor)
    cursor += 8
    (_,) = struct.unpack_from(">B", entity, cursor)
    cursor += 1
    (_,) = struct.unpack_from(">q", entity, cursor)
    cursor += 8
    (name_size,) = struct.unpack_from(">H", entity, cursor)
    cursor += 2
    name = entity[cursor : cursor + name_size].decode("utf-8")
    cursor += name_size
    (reference_id,) = struct.unpack_from(">h", entity, cursor)
    cursor += 2
    x, y, z, map_id, direction, _ = struct.unpack_from(">iihqBB", entity, cursor)
    cursor += 20
    cursor += 5  # native level flags
    cursor += 11  # native extra actor properties
    cursor += 1  # world properties
    cursor += 14  # actor ID, reference and level
    action_a, action_b, mask_count = struct.unpack_from(">hhH", entity, cursor)
    cursor += 6
    masked_actions = (
        list(struct.unpack_from(">" + "i" * mask_count, entity, cursor))
        if mask_count
        else []
    )
    cursor += 4 * mask_count
    if cursor + 21 != len(entity) or action_a != -1 or action_b != -1:
        raise ValueError("Invalid native sR action mask/tail")
    return dict(
        actor_id=actor_id,
        inner_actor_id=inner_actor_id,
        reference_id=reference_id,
        map_id=map_id,
        x=x,
        y=y,
        z=z,
        direction=direction,
        name=name,
        masked_actions=masked_actions,
    )


class NpcPlacementTests(unittest.TestCase):
    def test_all_ten_source_positions_and_native_sR_action_masks(self):
        for expected in EXPECTED:
            with self.subTest(actor_id=expected["actor_id"]):
                row = dict(expected, instance_id=0, enabled=True)
                self.assertIs(npc_placements.validate(row), row)
                decoded = decode_spawn(npc_placements.spawn(row))
                self.assertEqual(
                    decoded,
                    dict(
                        actor_id=row["actor_id"],
                        inner_actor_id=row["actor_id"],
                        reference_id=row["reference_id"],
                        map_id=row["map_id"],
                        x=row["x"],
                        y=row["y"],
                        z=row["z"],
                        direction=row["direction"],
                        name=row["name_es"],
                        masked_actions=row["native_action_ids"],
                    ),
                )
        by_ref = {row["reference_id"]: row for row in EXPECTED}
        self.assertEqual(
            decode_spawn(npc_placements.spawn(dict(by_ref[4069], instance_id=0)))[
                "masked_actions"
            ],
            [798],
        )
        self.assertEqual(
            decode_spawn(npc_placements.spawn(dict(by_ref[4399], instance_id=0)))[
                "masked_actions"
            ],
            [884],
        )

    def test_invalid_identity_and_action_masks_fail_closed(self):
        base = dict(EXPECTED[-1], instance_id=0, enabled=True)
        for change in (
            {"actor_id": 7},
            {"actor_id": -(2**53)},
            {"reference_id": True},
            {"map_id": 0},
            {"map_id": 2**31},
            {"instance_id": 1},
            {"x": 2**31},
            {"y": -(2**31) - 1},
            {"z": 32768},
            {"direction": 8},
            {"visual_id": 0},
            {"level": 0},
            {"source_sha256": "bad"},
            {"name_es": ""},
            {"native_action_ids": (884,)},
            {"native_action_ids": [884, 884]},
            {"native_action_ids": [True]},
            {"native_action_ids": [0]},
            {"native_action_ids": [[884]]},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                npc_placements.validate(dict(base, **change))

    def test_private_instance_returns_without_querying_database(self):
        class NoQuery:
            def execute(self, *_args, **_kwargs):
                raise AssertionError("Private scenes must not query public NPC rows")

        self.assertEqual(npc_placements.load_scene(NoQuery(), 1385, 1), ())

    def test_position_only_contract_has_no_dialogue_or_interaction_handler(self):
        row = dict(EXPECTED[-1], instance_id=0, enabled=True)
        self.assertNotIn("dialogue_root", row)
        self.assertNotIn("action_ids", row)
        self.assertFalse(hasattr(npc_placements, "begin"))
        self.assertTrue(hasattr(npc_placements, "spawn"))

    def test_actual_join_and_replay_hooks_include_position_only_actors(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        join = functions["join_world"]
        calls = [
            ast.unparse(node.func)
            for node in ast.walk(join)
            if isinstance(node, ast.Call)
        ]
        self.assertIn("npc_world.load_scene", calls)
        self.assertIn("npc_placements.load_scene", calls)
        self.assertIn("npc_world.spawn", calls)
        self.assertIn("npc_placements.spawn", calls)
        dialogue_loop = next(
            node
            for node in ast.walk(join)
            if isinstance(node, ast.For) and ast.unparse(node.iter) == "dialogue_npcs"
        )
        placement_loop = next(
            node
            for node in ast.walk(join)
            if isinstance(node, ast.For) and ast.unparse(node.iter) == "positioned_npcs"
        )
        self.assertLess(join.body.index(dialogue_loop), join.body.index(placement_loop))

        replay = functions["replay"]
        sql = [
            node.value
            for node in ast.walk(replay)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "world_dialogue_npcs" in node.value
        ]
        self.assertTrue(
            any(
                "UNION SELECT actor_id FROM world_native_npc_placements" in value
                for value in sql
            )
        )
        replay_calls = [
            ast.unparse(node.func)
            for node in ast.walk(replay)
            if isinstance(node, ast.Call)
        ]
        self.assertNotIn("npc_placements.begin", replay_calls)
