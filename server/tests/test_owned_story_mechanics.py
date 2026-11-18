"""Native story adapters preserve exact items, costs, collision and positions."""

from copy import deepcopy
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import wakfu_server
from wakfu_server import owned_story_controller as controller
from wakfu_server import owned_story_mechanics as mechanics

ROOT = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"


class OwnedStoryMechanicsTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / "astrub-temple-887.json").read_text())
        self.native = json.loads(
            (ROOT / "astrub-temple-887.native.v1.json").read_text()
        )
        self.store = SimpleNamespace(
            now=lambda: datetime(2026, 11, 15, tzinfo=timezone.utc)
        )
        self.character = dict(
            id=7, account_id=3, map_id=887, instance_id=99, x=1, y=2, z=0
        )

    def test_native_artifact_table_gives_18722_once_and_respects_original_quest_guard(
        self,
    ):
        from wakfu_server.achievements import rewards

        item = Mock(return_value=[(13879, b"actual-item")])
        with patch.object(mechanics, "sources", return_value=self.native), patch.object(
            mechanics, "allowed", return_value=True
        ), patch.object(rewards, "_item", item):
            result = mechanics._loot(
                "db", self.store, self.character, self.profile, 2437
            )
        self.assertEqual(result, [(13879, b"actual-item")])
        item.assert_called_once_with("db", self.store, self.character, 18722, 1)
        item.reset_mock()
        with patch.object(mechanics, "sources", return_value=self.native), patch.object(
            mechanics, "allowed", return_value=False
        ), patch.object(
            __import__("wakfu_server.combat_inventory_date_conditions", fromlist=["x"]),
            "complete_owned_item_quantity",
            return_value=1,
        ), patch.object(
            rewards, "_item", item
        ):
            self.assertEqual(
                mechanics._loot("db", self.store, self.character, self.profile, 2437),
                [],
            )
        item.assert_not_called()

    def test_story_artifact_loot_exception_only_covers_missing_required_transfer_item(
        self,
    ):
        from wakfu_server import combat_inventory_date_conditions

        table = deepcopy(self.native["loot_tables"]["2437"])
        expression = table["gBN"][0]["czk"]

        def permitted(
            candidate_table=table, candidate_expression=expression, quantity=0
        ):
            with patch.object(
                combat_inventory_date_conditions,
                "complete_owned_item_quantity",
                return_value=quantity,
            ):
                return mechanics._visit_artifact_guard(
                    self.character,
                    self.profile,
                    self.native,
                    candidate_table,
                    candidate_expression,
                )

        self.assertTrue(permitted())
        self.assertFalse(permitted(quantity=1))
        self.assertFalse(
            permitted(candidate_expression="not IsAchievementComplete(2166)")
        )
        randomized = deepcopy(table)
        randomized["gBN"][0]["cmY"] = 0.5
        self.assertFalse(permitted(candidate_table=randomized))
        unrelated = deepcopy(table)
        unrelated["gBN"][0]["aAi"] += 1
        self.assertFalse(permitted(candidate_table=unrelated))

    def test_executor_keeps_ordinary_effects_and_advances_only_assigned_active_objective(
        self,
    ):
        from wakfu_server.achievements import owned_quest_encounters, storage

        ordinary = {
            "kind": "element_state",
            "object_id": 23424,
            "state": 0,
            "visible": True,
            "usable": False,
            "blocks_movement": False,
        }
        effects = [
            ordinary,
            {"kind": "quest_objective", "quest_id": 999999, "objective_id": 1},
            {"kind": "quest_objective", "quest_id": 2166, "objective_id": 2},
            {"kind": "quest_objective", "quest_id": 2170, "objective_id": 3},
        ]
        state = dict(running=[2170], completed=[2166])
        advance = Mock(return_value=[(12345, b"objective")])
        ordinary_packet = (13422, b"unchanged native element state")
        apply = mechanics.executor(self.profile)
        with patch.object(storage, "load_locked", return_value=state), patch.object(
            owned_quest_encounters, "_advance", advance
        ), patch.object(controller, "element_packets", return_value=[ordinary_packet]):
            result = apply("db", self.store, self.character, effects)

        self.assertEqual(result, [ordinary_packet, (12345, b"objective")])
        advance.assert_called_once()
        self.assertEqual(advance.call_args.args[3], {"quest_id": 2170})
        self.assertEqual(advance.call_args.args[4], 3)

    def test_out_of_order_active_practice_skips_only_typed_prerequisite_then_valid_stage_advances(
        self,
    ):
        from wakfu_server.achievements import owned_quest_encounters, storage
        from wakfu_server.achievements.mission_progress import (
            ObjectivePrerequisiteUnavailable,
        )

        effects = [
            {"kind": "quest_objective", "quest_id": 2166, "objective_id": 2},
            {"kind": "quest_objective", "quest_id": 2166, "objective_id": 3},
        ]
        state = dict(running=[2166], completed=[])
        accepted = [(12345, b"valid next-stage objective")]
        advance = Mock(
            side_effect=[ObjectivePrerequisiteUnavailable("not ready"), accepted]
        )
        with patch.object(mechanics, "sources", return_value=self.native), patch.object(
            storage, "load_locked", return_value=state
        ), patch.object(owned_quest_encounters, "_advance", advance):
            result = mechanics.executor(self.profile)(
                "db", self.store, self.character, effects
            )

        self.assertEqual(result, accepted)
        self.assertEqual(advance.call_count, 2)
        self.assertEqual([call.args[4] for call in advance.call_args_list], [2, 3])

        malformed = Mock(side_effect=ValueError("malformed native objective"))
        with patch.object(mechanics, "sources", return_value=self.native), patch.object(
            storage, "load_locked", return_value=state
        ), patch.object(owned_quest_encounters, "_advance", malformed):
            with self.assertRaisesRegex(ValueError, "malformed native objective"):
                mechanics.executor(self.profile)(
                    "db", self.store, self.character, effects[:1]
                )
        malformed.assert_called_once()

    def test_story_scene_is_once_per_character_but_content_and_mechanics_are_quest_independent(
        self,
    ):
        from wakfu_server.achievements import storage, tutorial_presentation_once

        scene = next(
            effect
            for step in self.profile["steps"]
            for effect in step["effects"]
            if effect.get("kind") == "scenario_event" and effect["event"] == 14265
        )
        mechanical = next(
            effect
            for step in self.profile["steps"]
            for effect in step["effects"]
            if effect.get("kind") == "scenario_event" and effect["event"] == 14288
        )
        unassigned = {"kind": "quest_objective", "quest_id": 999999, "objective_id": 1}
        claim = Mock(side_effect=[True, False, True])
        apply = mechanics.executor(self.profile)
        db = Mock()
        character = dict(self.character)
        with patch.object(mechanics, "sources", return_value=self.native), patch.object(
            storage,
            "load_locked",
            side_effect=[dict(running=[], completed=[])] * 2
            + [dict(running=[2166], completed=[])] * 6,
        ), patch.object(tutorial_presentation_once, "claim", claim):
            # Visiting before assignment emits neither scene nor once-only claim.
            questless = apply(db, self.store, character, [scene, unassigned])
            self.assertEqual(questless, [])
            claim.assert_not_called()

            first = apply(db, self.store, character, [scene, mechanical, unassigned])
            repeated = apply(
                db,
                self.store,
                dict(character, instance_id=100),
                [scene, mechanical, unassigned],
            )
            other_character = apply(
                db, self.store, dict(character, id=8), [scene, unassigned]
            )

        self.assertTrue(any(body[1:5] == struct.pack(">i", 14265) for _, body in first))
        self.assertTrue(any(body[1:5] == struct.pack(">i", 14288) for _, body in first))
        self.assertIn(14265, repeated.skipped_scenes)
        self.assertTrue(
            any(body[1:5] == struct.pack(">i", 14288) for _, body in repeated)
        )
        self.assertTrue(
            any(body[1:5] == struct.pack(">i", 14265) for _, body in other_character)
        )
        self.assertEqual(claim.call_count, 3)

    def test_questless_suppressed_intro_does_not_hide_first_assigned_presentation(self):
        from wakfu_server.achievements import storage, tutorial_presentation_once

        intro = next(
            step for step in self.profile["steps"] if step["id"] == "boss-intro"
        )
        character = dict(self.character)
        db = Mock()
        apply = mechanics.executor(self.profile)
        with patch.object(mechanics, "sources", return_value=self.native), patch.object(
            storage, "load_locked", return_value=dict(running=[], completed=[])
        ), patch.object(
            storage, "record_event", return_value=True
        ) as record, patch.object(
            tutorial_presentation_once, "claim"
        ) as claim:
            suppressed = apply(db, self.store, character, intro["effects"])
            self.assertEqual(suppressed, [])
            self.assertTrue(suppressed.suppressed_presentations)
            claim.assert_not_called()

        receipts = []

        def remember(_db, _owner, key, payload):
            receipts.append((key, deepcopy(payload)))
            return True

        callback_packets = mechanics.MechanicPackets()
        callback_packets.append((13411, b"mechanical continuation"))
        with patch.object(storage, "record_event", side_effect=remember), patch.object(
            mechanics, "sources", return_value=self.native
        ):
            result = controller._settle(
                db,
                self.store,
                character,
                self.profile,
                {"boss-gate"},
                kind="zone_trigger",
                reference=23540,
                evidence={"native_trigger": 23540},
                apply_effects=Mock(side_effect=[suppressed, callback_packets]),
            )
        self.assertTrue(result["applied"])
        self.assertEqual(len(result["packets"]), 1)
        suppressed_receipt = next(
            payload for _key, payload in receipts if payload.get("step") == "boss-intro"
        )
        self.assertTrue(suppressed_receipt["presentation_suppressed"])

        query = Mock(return_value=SimpleNamespace(fetchone=lambda: None))
        with patch.object(
            storage, "load_locked", return_value=dict(running=[2166], completed=[])
        ), patch.object(storage, "record_event", return_value=True), patch.object(
            db, "execute", query
        ), patch.object(
            mechanics, "sources", return_value=self.native
        ):
            shown = apply(db, self.store, character, intro["effects"])
        self.assertTrue(any(body[1:5] == struct.pack(">i", 14265) for _, body in shown))
        history_sql, history_params = query.call_args.args
        self.assertIn("AND NOT payload @>", history_sql)
        exclude = getattr(history_params[-1], "obj", history_params[-1])
        self.assertEqual(exclude, {"presentation_suppressed": True})

    def test_native_guide_and_presentation_metadata_routes_once_without_hiding_mechanics(
        self,
    ):
        from wakfu_server.achievements import storage, tutorial_presentation_once

        selected = dict(
            id="generic-metadata-fixture",
            admission=dict(quest_id=7001, continuation_quest_id=7002),
            steps=[],
        )
        native = dict(
            guides={"10": 710},
            presentations=[20],
            scenes={},
        )
        guide_claim = Mock(side_effect=[True, False])
        scene_claim = Mock(return_value=True)
        with patch.object(
            tutorial_presentation_once, "claim_guide", guide_claim
        ), patch.object(tutorial_presentation_once, "claim", scene_claim), patch.object(
            storage,
            "load_locked",
            side_effect=[
                dict(running=[], completed=[]),
                dict(running=[7001], completed=[]),
            ],
        ) as load:
            self.assertTrue(
                mechanics._presentation_claim(
                    "db",
                    self.character,
                    selected,
                    native,
                    dict(scenario=111, event=10),
                )
            )
            self.assertFalse(
                mechanics._presentation_claim(
                    "db",
                    self.character,
                    selected,
                    native,
                    dict(scenario=222, event=10),
                )
            )
            # Metadata permits a presentation with no scene callback; quest
            # assignment controls it like a normal non-guide cinematic.
            self.assertFalse(
                mechanics._presentation_claim(
                    "db",
                    self.character,
                    selected,
                    native,
                    dict(scenario=111, event=20),
                )
            )
            self.assertTrue(
                mechanics._presentation_claim(
                    "db",
                    self.character,
                    selected,
                    native,
                    dict(scenario=111, event=20),
                )
            )
            # An unlisted source event remains mechanical and is not claimed.
            self.assertTrue(
                mechanics._presentation_claim(
                    "db",
                    self.character,
                    selected,
                    native,
                    dict(scenario=111, event=30),
                )
            )

        self.assertEqual(guide_claim.call_count, 2)
        self.assertEqual(guide_claim.call_args_list[0].args[2], 710)
        self.assertEqual(guide_claim.call_args_list[1].args[2], 710)
        scene_claim.assert_called_once_with("db", 7, 111, 20, legacy=())
        self.assertEqual(load.call_count, 2)

        guide_claim.reset_mock()
        with patch.object(tutorial_presentation_once, "claim_guide", guide_claim):
            with self.assertRaisesRegex(ValueError, "native identity"):
                mechanics._presentation_claim(
                    "db",
                    self.character,
                    selected,
                    dict(native, guides={"10": 0}),
                    dict(scenario=333, event=10),
                )
        guide_claim.assert_not_called()

    def test_group_presentation_respects_assignment_before_consuming_group_claim(self):
        from wakfu_server.achievements import storage, tutorial_presentation_once

        selected = dict(
            id="group-gating-fixture",
            admission=dict(quest_id=2015, continuation_quest_id=2018),
            steps=[],
        )
        group = dict(
            id="mixed-native-tutorial",
            start_event=15992,
            initializers={"2015": 15992, "2018": 16007, "2016": 15998},
            events=[15992, 15998, 16007, 16008],
        )
        native = dict(
            scenes={},
            guides={},
            presentations=[],
            presentation_groups=[group],
            presentation_quests={"15992": 2015},
        )
        claim = Mock(return_value=True)
        with patch.object(mechanics, "sources", return_value=native), patch.object(
            storage, "load_locked", return_value=dict(running=[], completed=[])
        ), patch.object(tutorial_presentation_once, "claim_group_event", claim):
            self.assertFalse(
                mechanics._presentation_claim(
                    "db",
                    self.character,
                    selected,
                    native,
                    dict(scenario=2015, event=15992),
                )
            )
            claim.assert_not_called()

        with patch.object(mechanics, "sources", return_value=native), patch.object(
            storage, "load_locked", return_value=dict(running=[2015], completed=[])
        ), patch.object(tutorial_presentation_once, "claim_group_event", claim):
            self.assertTrue(
                mechanics._presentation_claim(
                    "db",
                    self.character,
                    selected,
                    native,
                    dict(scenario=2015, event=15992),
                )
            )
        claim.assert_called_once_with("db", self.character, group, 2015, 15992)

    def test_actual_native_artifact_transfer_requires_but_does_not_consume_18722(self):
        from wakfu_server import (
            native_generic_rewards,
            combat_inventory_date_conditions,
        )

        moved = Mock(return_value=(13530, b"position"))
        payment = Mock()
        with patch.object(mechanics, "sources", return_value=self.native), patch.object(
            mechanics, "allowed", return_value=True
        ), patch.object(
            combat_inventory_date_conditions,
            "complete_owned_item_quantity",
            return_value=1,
        ), patch.object(
            native_generic_rewards, "_payment", payment
        ), patch.object(
            mechanics, "move", moved
        ):
            packets = mechanics.native_transfer(
                "db", self.store, self.character, self.profile, 23590, 1410
            )
        moved.assert_called_once_with("db", self.character, [-15, -21, 0], direction=5)
        self.assertEqual(packets[-1], (13530, b"position"))
        payment.assert_not_called()

    def test_missing_artifact_rejects_native_transfer_before_any_position_change(self):
        from wakfu_server import combat_inventory_date_conditions

        moved = Mock()
        with patch.object(mechanics, "sources", return_value=self.native), patch.object(
            mechanics, "allowed", return_value=True
        ), patch.object(
            combat_inventory_date_conditions,
            "complete_owned_item_quantity",
            return_value=0,
        ), patch.object(
            mechanics, "move", moved
        ):
            with self.assertRaisesRegex(ValueError, "actual native artifact"):
                mechanics.native_transfer(
                    "db", self.store, self.character, self.profile, 23590, 1410
                )
        moved.assert_not_called()

    def test_native_position_compare_and_set_uses_real_old_location_and_same_owned_instance(
        self,
    ):
        from wakfu_server import dungeon_runtime

        db = Mock()
        db.execute.return_value.rowcount = 1
        with patch.object(
            dungeon_runtime,
            "configuration_for_instance",
            return_value=(
                None,
                dict(topology=dict(exploration_geometry=dict(cells=[[-15, -25, 0]]))),
            ),
        ):
            packet = mechanics.move(db, self.character, [-15, -25, 0])
        self.assertEqual(
            db.execute.call_args.args[1], (-15, -25, 0, 7, 3, 887, 99, 1, 2, 0)
        )
        self.assertEqual(
            tuple(self.character[key] for key in ("x", "y", "z")), (-15, -25, 0)
        )
        self.assertEqual(packet, (13530, struct.pack(">qiihBi", 7, -15, -25, 0, 3, -1)))

    def test_position_race_does_not_publish_relocation_or_replace_owner_projection(
        self,
    ):
        from wakfu_server import dungeon_runtime

        db = Mock()
        db.execute.return_value.rowcount = 0
        before = deepcopy(self.character)
        with patch.object(
            dungeon_runtime,
            "configuration_for_instance",
            return_value=(
                None,
                dict(topology=dict(exploration_geometry=dict(cells=[[-15, -25, 0]]))),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "committed position"):
                mechanics.move(db, self.character, [-15, -25, 0])
        self.assertEqual(self.character, before)

    def test_door_state_and_collision_projection_share_the_same_flags(self):
        from wakfu_server import dungeon_native_door_collision

        world = SimpleNamespace(objects=Mock(return_value=self.native["objects"]))
        completed = {step["id"] for step in self.profile["steps"]}
        with patch.object(wakfu_server, "world_static", world, create=True):
            packets = controller.element_packets(self.profile, completed)
            by_id = {
                struct.unpack_from(">q", body)[0]: body[10:] for _, body in packets
            }
            state, visible, usable, _, collision_a, collision_b, _, _ = struct.unpack(
                ">h6Bi", by_id[23424][7:]
            )
            self.assertEqual(
                (state, visible, usable, collision_a, collision_b), (0, 0, 0, 0, 0)
            )
            # Native doors23460/61 begin open and remain open without any player step.
            initial = controller.element_packets(self.profile, set())
            initial = {
                struct.unpack_from(">q", body)[0]: body[10:] for _, body in initial
            }
            self.assertEqual(struct.unpack_from(">h", initial[23460], 7)[0], 0)
            self.assertEqual(initial[23460][9], 1)
            columns = SimpleNamespace(source_sha256="a" * 64)
            with patch.object(
                dungeon_native_door_collision,
                "native_blocking_cells",
                side_effect=lambda map_id, position, **kw: frozenset(
                    (tuple(position),)
                ),
            ):
                projection = controller.collision_projection(
                    self.profile, set(), columns=columns
                )
        self.assertIn((-18, -29, 0), projection["blocked"])
        self.assertNotIn((-8, -26, 0), projection["blocked"])

    def test_native_route_reaches_artifact_around_closed_door_without_opening_boss_gate(
        self,
    ):
        from wakfu_server import world_static

        configuration = json.loads(
            (ROOT / "astrub-temple-887.configuration.json").read_text()
        )
        geometry = configuration["topology"]["exploration_geometry"]
        edges = {(tuple(start), tuple(end)) for start, end in geometry["edges"]}
        completed = {"room1-victory", "room1-key", "room1-gate", "room2-victory"}
        with patch.object(world_static, "objects", return_value=self.native["objects"]):
            collision = controller.collision_projection(self.profile, completed)

        start, goal = (-12, -25, 0), (-16, -25, 0)
        direct = [start, (-13, -25, 0), (-14, -25, 0), (-15, -25, 0), goal]
        self.assertIn(direct[1], collision["blocked"])
        self.assertIn((0, -38, 0), collision["blocked"])
        adjacency = {}
        for source, destination in edges:
            adjacency.setdefault(source, []).append(destination)
        previous = {start: None}
        queue = deque([start])
        while queue and goal not in previous:
            current = queue.popleft()
            for neighbor in adjacency.get(current, ()):
                if neighbor in collision["blocked"] or neighbor in previous:
                    continue
                previous[neighbor] = current
                queue.append(neighbor)
        self.assertIn(goal, previous)
        route = []
        cursor = goal
        while cursor is not None:
            route.append(cursor)
            cursor = previous[cursor]
        route.reverse()
        self.assertNotIn((-13, -25, 0), route)
        self.assertIn((-13, -26, 0), route)

    def test_native_scene_packet_signature_preserves_required_zero_player_slots(self):
        with patch.object(mechanics, "sources", return_value=self.native):
            packet = mechanics.scenario_packet(
                self.profile, 14265, (0, 23540, 7, 0, 0, 0, 0, 0)
            )
            with self.assertRaisesRegex(ValueError, "arguments"):
                mechanics.scenario_packet(self.profile, 14265, (7,))
        self.assertEqual(struct.unpack_from(">BiiB", packet[1]), (0, 14265, 1722, 8))
        self.assertEqual(len(packet[1]), 10 + 8 * 8)

    def test_zinit_integer_and_object_event_signatures_encode_and_reject_bad_arguments(
        self,
    ):
        selected = json.loads((ROOT / "zinit-reef-980.json").read_text())
        native = json.loads((ROOT / "zinit-reef-980.native.v1.json").read_text())
        # The newer extracted events encode their arity directly as an int;
        # earlier boat events retain the equivalent {argument_count: n} form.
        self.assertEqual(native["event_signatures"]["16046"], 1)
        self.assertEqual(native["event_signatures"]["15993"], {"argument_count": 2})
        with patch.object(mechanics, "sources", return_value=native):
            integer_signature = mechanics.scenario_packet(selected, 16046, (369,))
            object_signature = mechanics.scenario_packet(selected, 15993, (369, 0))
            for event, arguments in (
                (16046, ()),
                (16046, (369, 0)),
                (15993, (369,)),
                (16046, (True,)),
                (16046, (1.5,)),
                (16046, (1 << 63,)),
            ):
                with self.subTest(
                    event=event, arguments=arguments
                ), self.assertRaisesRegex(ValueError, "arguments"):
                    mechanics.scenario_packet(selected, event, arguments)

        self.assertEqual(
            struct.unpack_from(">BiiB", integer_signature[1]), (0, 16046, 2021, 1)
        )
        self.assertEqual(len(integer_signature[1]), 18)
        self.assertEqual(
            struct.unpack_from(">BiiB", object_signature[1]), (0, 15993, 2015, 2)
        )
        self.assertEqual(len(object_signature[1]), 26)

    def test_source_qualified_story_npc_argument_accepts_native_negative_actor_uid(
        self,
    ):
        from wakfu_server import npc_world

        selected = json.loads((ROOT / "zinit-reef-980.json").read_text())
        native = json.loads((ROOT / "zinit-reef-980.native.v1.json").read_text())
        effect = next(
            effect
            for step in selected["steps"]
            for effect in step["effects"]
            if effect.get("event") == 16066
        )
        store = object()
        db = object()
        actor_id = npc_world.MIN_ID + 1
        # _arguments imports the resolver lazily from its public module.
        with patch.object(mechanics, "sources", return_value=native), patch(
            "wakfu_server.owned_story_npcs.argument_actor",
            return_value=actor_id,
        ) as resolver:
            arguments = mechanics._arguments(
                db, dict(self.character), effect, selected, store=store
            )
            packet = mechanics.scenario_packet(selected, effect["event"], arguments)

        self.assertEqual(arguments, [actor_id])
        resolver.assert_called_once_with(db, store, self.character, 3801)
        self.assertEqual(packet[0], 13411)
        self.assertEqual(
            struct.unpack(">BiiBq", packet[1]),
            (
                0,
                16066,
                native.get("scenario_bindings", {}).get("16066", native["scenario_id"]),
                1,
                actor_id,
            ),
        )

        for invalid_id in (0, 1, npc_world.MAX_ID + 1, npc_world.MIN_ID - 1):
            with self.subTest(invalid_id=invalid_id), patch.object(
                mechanics, "sources", return_value=native
            ), patch(
                "wakfu_server.owned_story_npcs.argument_actor",
                return_value=invalid_id,
            ):
                with self.assertRaisesRegex(ValueError, "actual scoped actor"):
                    mechanics._arguments(
                        db, self.character, effect, selected, store=store
                    )

        malformed = dict(effect, arguments=["story_npc:03801"])
        with patch.object(mechanics, "sources", return_value=native):
            with self.assertRaisesRegex(ValueError, "source-qualified"):
                mechanics._arguments(
                    db, self.character, malformed, selected, store=store
                )

        mismatched_source = deepcopy(native)
        mismatched_source["argument_sources"]["16066"]["story_npcs"][
            "story_npc:3801"
        ] = 3802
        with patch.object(mechanics, "sources", return_value=mismatched_source):
            with self.assertRaisesRegex(ValueError, "source-qualified"):
                mechanics._arguments(db, self.character, effect, selected, store=store)

    def test_cire_native_door_action_uses_authoritative_not_hero_role(self):
        from wakfu_server.achievements import storage
        from wakfu_server.dungeon_criteria import evaluate

        root = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"
        selected = json.loads((root / "ereboria-cire-1366.json").read_text())
        native = json.loads((root / "ereboria-cire-1366.native.v1.json").read_text())
        descriptor = native["programs"]["33379"]
        action = descriptor["groups"][0]["actions"][0]
        self.assertEqual(
            (
                descriptor["descriptor_id"],
                action["wire_action"],
                action["native_id"],
                action["criterion"],
                action["effects"][0]["action_reference"],
            ),
            (1489, 0, 1908, "not IsHero()", 3375),
        )
        character = dict(self.character, map_id=1366, instance_id=99)

        class RoleDB:
            def __init__(self, leader):
                self.leader = leader

            def execute(self, sql, params):
                if (
                    sql
                    == "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s"
                ):
                    return SimpleNamespace(
                        fetchone=lambda: None
                        if self.leader is None
                        else {"leader_id": self.leader}
                    )
                raise AssertionError(f"Unexpected read-only role query: {sql}")

        state = {"running": [], "completed": [], "objectives": []}
        with patch.object(mechanics, "sources", return_value=native), patch.object(
            storage, "load_locked", return_value=state
        ):
            self.assertIs(
                mechanics.authorize_action(
                    RoleDB(character["id"]), self.store, character, selected, 33379, 0
                ),
                action,
            )
            with self.assertRaisesRegex(ValueError, "unavailable"):
                mechanics.authorize_action(
                    RoleDB(999), self.store, character, selected, 33379, 0
                )
            self.assertIs(
                mechanics.authorize_action(
                    RoleDB(None), self.store, character, selected, 33379, 0
                ),
                action,
            )

        for criterion, queries, message in (
            ("IsHero()", {}, "Missing dungeon predicate authority"),
            ("IsHero()", {"IsHero": lambda: 1}, "lacks boolean authority"),
            (
                "IsHero(1)",
                {"IsHero": lambda: False},
                "Unsupported dungeon criterion arguments",
            ),
        ):
            with self.subTest(criterion=criterion), self.assertRaisesRegex(
                ValueError, message
            ):
                evaluate(self.store, criterion, character=character, queries=queries)
        self.assertFalse(
            evaluate(
                self.store,
                "not IsHero()",
                character=character,
                queries={"IsHero": lambda: True},
                bypass_mission_prerequisites=True,
                bypass_state_prerequisites=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
