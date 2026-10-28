"""Original artifact programs produce owned, deferred travel plans only."""
import copy
import json
from pathlib import Path
import re
import struct
import unittest
from unittest.mock import Mock, patch

from wakfu_server import exploration_artifact_actions as actions, exploration_secrets


class ExplorationArtifactActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = json.loads(Path(actions.__file__).with_suffix(".json").read_text())
        cls.programs = {p["descriptor_id"]: p for p in cls.book["programs"]}

    def actor(self, row, effect=None):
        position = row["approach_positions"][0] if row["approach_positions"] else row
        position = {axis: int(position[axis]) for axis in ("x", "y", "z")}
        if effect is not None:
            for axis in ("x", "y"):
                match = re.search(
                    r"Get" + axis.upper() + r"\(\)\s*(?:==|>=|<=)\s*(-?\d+)",
                    effect["criterion"],
                )
                if match:
                    position[axis] = int(match[1])
        return dict(
            id=90,
            account_id=7,
            map_id=row["map_id"],
            instance_id=0,
            **position,
            account_quest_items=[],
            exploration_secrets=dict(account_item_refs=exploration_secrets.ITEM_REFS)
        )

    def branches(self):
        for row in actions.sources():
            for group in self.programs[row["descriptor"]]["groups"]:
                if group["cod"] not in exploration_secrets.ITEM_REFS:
                    continue
                for action in group["actions"]:
                    for effect in action["effects"]:
                        if effect["effect_type"] == 3:
                            yield row, group, action, effect

    def truth(self, expression, actor):
        if not expression:
            return True
        for axis in ("x", "y", "z"):
            expression = expression.replace(
                "Get" + axis.upper() + "()", str(actor[axis])
            )
        expression = re.sub(r"IsAchievementActive\((?:3093|3616)\)", "True", expression)
        expression = expression.replace("IsInFight()", "False")
        self.assertFalse(
            re.search(
                r"[A-Za-z_]", re.sub(r"\b(?:True|False|and|or|not)\b", "", expression)
            )
        )
        return eval(expression, {"__builtins__": {}}, {})

    def decode_script(self, packet):
        opcode, body = packet
        self.assertEqual(opcode, 13270)
        actor, reference, namespace, count = struct.unpack_from(">qiBi", body)
        cursor, variables = 17, {}
        for _ in range(count):
            size = struct.unpack_from(">i", body, cursor)[0]
            cursor += 4
            key = body[cursor : cursor + size].decode()
            cursor += size
            self.assertNotIn(key, variables)
            variables[key] = struct.unpack_from(">q", body, cursor)[0]
            cursor += 8
        self.assertEqual(cursor, len(body))
        self.assertEqual(namespace, 1)
        return actor, reference, variables

    def test_all_original_travel_branches_preserve_targets_delays_scripts_and_inputs(
        self,
    ):
        sources = actions.sources()
        self.assertEqual(len(sources), 61)
        self.assertEqual(
            {(r["map_id"], r["id"]) for r in sources},
            {(r["map_id"], r["id"]) for r in self.book["placements"]},
        )
        touched, branch_count = set(), 0
        with patch.object(actions, "_verify_source", return_value=True), patch.object(
            actions, "_walkable", return_value=True
        ):
            for row, group, action, effect in self.branches():
                with self.subTest(source=row["id"], effect=effect["action_reference"]):
                    actor = self.actor(row, effect)
                    before = copy.deepcopy(actor)
                    body = struct.pack(">qHH", row["id"], action["wire_action"], 0)
                    self.assertTrue(actions.recognizes(actor, body))
                    plan = actions.resolve(
                        actor,
                        body,
                        source_allowed=lambda *_: True,
                        position_allowed=lambda *_: True,
                    )
                    coordinates = list(
                        map(
                            int,
                            re.fullmatch(
                                r"\{\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\}",
                                effect["parameters"][0],
                            ).groups(),
                        )
                    )
                    self.assertEqual(
                        plan["destination"],
                        dict(
                            map_id=int(effect["parameters"][1]),
                            instance_id=0,
                            **dict(zip(("x", "y", "z"), coordinates))
                        ),
                    )
                    self.assertEqual(plan["direction"], int(effect["parameters"][2]))
                    self.assertEqual(
                        plan["delay_ms"],
                        int(effect["parameters"][3])
                        if len(effect["parameters"]) == 4
                        else 0,
                    )
                    self.assertEqual(
                        plan["origin"],
                        {
                            key: actor[key]
                            for key in ("map_id", "instance_id", "x", "y", "z")
                        },
                    )
                    self.assertEqual(
                        (
                            plan["native_group_id"],
                            plan["native_action_id"],
                            plan["native_effect_reference"],
                            plan["artifact_reference"],
                        ),
                        (
                            group["id"],
                            action["native_id"],
                            effect["action_reference"],
                            group["cod"],
                        ),
                    )
                    selected = [
                        e
                        for e in action["effects"]
                        if self.truth(e["criterion"], actor)
                    ]
                    present = [
                        e
                        for e in selected
                        if self.book["native_scripts"][str(e["action_reference"])][
                            "present"
                        ]
                    ]
                    missing = tuple(
                        e["action_reference"]
                        for e in selected
                        if not self.book["native_scripts"][str(e["action_reference"])][
                            "present"
                        ]
                    )
                    self.assertEqual(plan["missing_visual_scripts"], missing)
                    self.assertEqual(len(plan["script_packets"]), len(present))
                    for scripted, original in zip(plan["script_packets"], present):
                        packet_actor, reference, variables = self.decode_script(
                            scripted["packet"]
                        )
                        self.assertEqual(
                            (packet_actor, reference, variables),
                            (
                                actor["id"],
                                original["action_reference"],
                                {"userId": actor["id"], "elementId": row["id"]},
                            ),
                        )
                        self.assertEqual(
                            scripted["broadcast"],
                            original["effect_type"] == 1
                            and original["parameters"] == ["true"],
                        )
                        self.assertEqual(
                            scripted["native_effect_type"], original["effect_type"]
                        )
                    self.assertEqual(actor, before)
                    touched.add((row["map_id"], row["id"]))
                    branch_count += 1
        self.assertEqual(len(touched), 59)
        self.assertEqual(actions.sources(), sources)
        print(
            "Original artifact travel:",
            len(touched),
            "placements;",
            branch_count,
            "coordinate/program branches",
        )

    def test_original_sources_targets_and_approaches_against_actual_native_catalog(
        self,
    ):
        from wakfu_server.combat_terrain import map_geometry

        sources = actions.sources()
        for row in sources:
            with self.subTest(native_source=row["id"]):
                self.assertTrue(actions._verify_source(row))
        native_cells = {}

        def cells(map_id):
            if map_id not in native_cells:
                native_cells[map_id] = frozenset(
                    tuple(c) for c in map_geometry(map_id)["cells"]
                )
            return native_cells[map_id]

        exported, walkable_exported, actual_plans = 0, 0, 0
        for row in sources:
            for point in row["approach_positions"]:
                exported += 1
                walkable_exported += tuple(point[a] for a in ("x", "y", "z")) in cells(
                    row["map_id"]
                )
        for row, group, action, effect in self.branches():
            with self.subTest(
                native_branch=effect["action_reference"], source=row["id"]
            ):
                destination = tuple(
                    map(
                        int,
                        re.fullmatch(
                            r"\{\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\}",
                            effect["parameters"][0],
                        ).groups(),
                    )
                )
                destination_map = int(effect["parameters"][1])
                self.assertIn(
                    destination,
                    cells(destination_map),
                    "Original literal destination has no native walkable surface",
                )
                self.assertTrue(actions._walkable(destination_map, destination))
                actor = self.actor(row, effect)
                possible = sorted(
                    c for c in cells(row["map_id"]) if c[:2] == (actor["x"], actor["y"])
                )
                self.assertTrue(
                    possible, "Original endpoint has no native walkable source surface"
                )
                exported_here = [
                    c
                    for c in possible
                    if any(
                        c == tuple(p[a] for a in ("x", "y", "z"))
                        for p in row["approach_positions"]
                    )
                ]
                selected = exported_here[0] if exported_here else possible[0]
                actor.update(zip(("x", "y", "z"), selected))
                self.assertTrue(self.truth(effect["criterion"], actor))

                def source_allowed(current, original):
                    return any(
                        tuple(current[a] for a in ("x", "y", "z"))
                        == tuple(p[a] for a in ("x", "y", "z"))
                        for p in original["approach_positions"]
                    )

                def position_allowed(current):
                    return tuple(current[a] for a in ("x", "y", "z")) in cells(
                        current["map_id"]
                    )

                plan = actions.resolve(
                    actor,
                    struct.pack(">qHH", row["id"], action["wire_action"], 0),
                    source_allowed=source_allowed,
                    position_allowed=position_allowed,
                )
                self.assertEqual(
                    plan["native_effect_reference"], effect["action_reference"]
                )
                actual_plans += 1
        self.assertEqual(actual_plans, 106)
        print(
            "Actual native qualification:",
            len(sources),
            "sources;",
            actual_plans,
            "branches;",
            walkable_exported,
            "of",
            exported,
            "exported approach cells are native walkable",
        )

    def test_rejections_never_return_a_plan_and_keep_owned_state_unchanged(self):
        row, _, action, effect = next(self.branches())
        actor = self.actor(row, effect)
        body = struct.pack(">qHH", row["id"], action["wire_action"], 0)
        invalid = [
            (actor, b"", {}),
            (actor, body + b"x", {}),
            (actor, bytearray(body), {}),
            (actor, struct.pack(">qHH", row["id"], action["wire_action"], 1), {}),
            (actor, struct.pack(">qHH", row["id"], 31, 0), {}),
            (dict(actor, map_id=-1), body, {}),
            (dict(actor, instance_id=4), body, {}),
            (dict(actor, id=True), body, {}),
            (actor, body, {"blocked": True}),
            (dict(actor, health_dead=True), body, {}),
            (dict(actor, exploration_secrets=dict(account_item_refs=())), body, {}),
            (dict(actor, exploration_secrets=dict(account_item_refs=(19,))), body, {}),
            (
                dict(actor, exploration_secrets=dict(account_item_refs=(18722, 18722))),
                body,
                {},
            ),
            (
                dict(
                    actor,
                    account_quest_items=[
                        dict(account_id=8, reference=18722, quantity=1)
                    ],
                ),
                body,
                {},
            ),
        ]
        absent = copy.deepcopy(actor)
        absent.pop("exploration_secrets")
        invalid.append((absent, body, {}))
        with patch.object(actions, "_verify_source", return_value=True), patch.object(
            actions, "_walkable", return_value=True
        ):
            for current, request, options in invalid:
                with self.subTest(options=options, body_type=type(request).__name__):
                    before = copy.deepcopy(current)
                    with self.assertRaises(ValueError):
                        actions.resolve(
                            current,
                            request,
                            source_allowed=lambda *_: True,
                            position_allowed=lambda *_: True,
                            **options
                        )
                    self.assertEqual(current, before)
            for source_row, _, native_action, native_effect in self.branches():
                current = self.actor(source_row, native_effect)
                request = struct.pack(
                    ">qHH", source_row["id"], native_action["wire_action"], 0
                )
                with self.subTest(source=source_row["id"]), self.assertRaises(
                    ValueError
                ):
                    actions.resolve(
                        current,
                        request,
                        source_allowed=lambda *_: False,
                        position_allowed=lambda *_: False,
                    )
        with patch.object(
            actions, "_verify_source", side_effect=ValueError("native source mismatch")
        ):
            with self.assertRaisesRegex(ValueError, "source mismatch"):
                actions.resolve(
                    actor,
                    body,
                    source_allowed=lambda *_: True,
                    position_allowed=lambda *_: True,
                )
        with patch.object(actions, "_verify_source", return_value=True), patch.object(
            actions, "_walkable", return_value=False
        ):
            with self.assertRaises(ValueError):
                actions.resolve(
                    actor,
                    body,
                    source_allowed=lambda *_: True,
                    position_allowed=lambda *_: True,
                )

    def test_numeric_varita_action_and_two_unrecovered_hammers_are_explicit(self):
        varita = next(r for r in actions.sources() if r["descriptor"] == 1145)
        artifact_action = next(
            a
            for g in self.programs[1145]["groups"]
            if g["cod"] == 21598
            for a in g["actions"]
        )
        self.assertEqual(artifact_action["wire_action"], 1)
        actor = self.actor(varita, artifact_action["effects"][0])
        self.assertFalse(
            actions.recognizes(actor, struct.pack(">qHH", varita["id"], 0, 0))
        )
        self.assertTrue(
            actions.recognizes(actor, struct.pack(">qHH", varita["id"], 1, 0))
        )
        for action_id in (0, 31):
            with self.assertRaises(ValueError):
                actions.resolve(
                    actor,
                    struct.pack(">qHH", varita["id"], action_id, 0),
                    source_allowed=lambda *_: True,
                )
        hammers = [r for r in actions.sources() if r["descriptor"] == 1265]
        self.assertEqual({r["id"] for r in hammers}, {28105, 28106})
        verify = Mock(
            side_effect=AssertionError(
                "Opaque hammer must not reach source or movement"
            )
        )
        with patch.object(actions, "_verify_source", verify), patch.object(
            actions, "_walkable", verify
        ):
            for row in hammers:
                actor = self.actor(row)
                before = copy.deepcopy(actor)
                with self.assertRaisesRegex(
                    actions.UnsupportedExplorationArtifact, "2947"
                ):
                    actions.resolve(
                        actor,
                        struct.pack(">qHH", row["id"], 0, 0),
                        source_allowed=verify,
                    )
                self.assertEqual(actor, before)
        verify.assert_not_called()

    def test_original_varita_menu_projects_native_index_one_across_scene_replays(self):
        from wakfu_server import seasonal_native_gateway, world_static, world_scene_sync
        from wakfu_server.interactive_publication import (
            InteractivePublication,
            refresh_snapshots,
        )
        from test_travel_mists import frame, packets

        row = next(r for r in world_static.objects(1118) if r["id"] == 27550)
        self.assertTrue(actions._verify_source(actions.source(1118, 27550)))
        actor = self.actor(actions.source(1118, 27550))
        scope = dict(
            actor, character_id=actor["id"], session_id="varita-qa", generation="lease"
        )
        tracker = InteractivePublication(
            lambda _: (row,), attachment_projector=seasonal_native_gateway.attachment
        )
        loader = frame(12318, struct.pack(">ii", int(row["x"]), int(row["y"])))
        bodies = world_scene_sync.dynamic_snapshots(
            1118, (world_scene_sync.chunk(row),)
        )
        original_state = world_static._DUNGEON_ENTRY_STATE
        actual = [
            record
            for body in bodies
            for record in refresh_snapshots(body)
            if struct.unpack_from(">q", record)[0] == row["id"]
        ]
        self.assertEqual(actual[0][10:], original_state)
        snapshots = b"".join(frame(13984, body) for body in bodies)
        first = tuple(packets(tracker.transform(loader + snapshots, scope)))
        appearances = [body for opcode, body in first if opcode == 13664]
        self.assertEqual(len(appearances), 1)
        count, identity, prototype, size = struct.unpack_from(">hqqH", appearances[0])
        self.assertEqual((count, identity, prototype), (1, 27550, 19825))
        appearance = seasonal_native_gateway._parts(appearances[0][20 : 20 + size])
        self.assertEqual(
            appearance[0],
            seasonal_native_gateway._parts(bytes.fromhex(row["payload_hex"]))[0],
        )
        self.assertIn(b"{1;desc.mru.entrer}", appearance[1])
        replay = tuple(packets(tracker.transform(snapshots, scope)))
        self.assertEqual(
            [
                body[10:]
                for opcode, body in replay
                if opcode == 12344 and struct.unpack_from(">q", body)[0] == 27550
            ],
            [original_state],
        )
        tracker.transform(frame(12318, struct.pack(">ii", 10000, 10000)), scope)
        for reset in (b"", frame(13256)):
            again = tuple(packets(tracker.transform(reset + loader + snapshots, scope)))
            self.assertEqual(
                [body for opcode, body in again if opcode == 13664], appearances
            )
        projected = actions.activation(actor, struct.pack(">qHH", 27550, 0, 0))
        self.assertEqual(projected, struct.pack(">qHH", 27550, 1, 0))
        self.assertTrue(actions.recognizes(actor, projected))
        self.assertIsNone(actions.activation(actor, projected))
        for invalid in (dict(actor, instance_id=4),):
            with self.assertRaises(ValueError):
                actions.activation(invalid, struct.pack(">qHH", 27550, 0, 0))
