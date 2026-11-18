"""Native staged waves reuse terrain only behind authentic earlier victory gates."""

from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.combat_geometry import prepare_geometry
from wakfu_server import owned_story_mechanics as mechanics
from wakfu_server.owned_story_encounters import compile_rooms
from wakfu_server.owned_story_configuration import validate_sequential_arenas
from wakfu_server.combat_mission_allies import admit, validate, VOYAGE_POLICY
from wakfu_server import owned_story_admission as admission

ROOT = Path(__file__).parents[1]
PROFILES = ROOT / "wakfu_server/maps/owned_story_profiles"


class OwnedStoryStageTests(unittest.TestCase):
    def setUp(self):
        self.encounters = json.loads(
            (PROFILES / "zinit-voyage-980.encounters.json").read_text()
        )
        self.controller = json.loads(
            (PROFILES / "zinit-voyage-980.controller-fragment.json").read_text()
        )
        self.native = json.loads(
            (PROFILES / "zinit-voyage-980.native-fragment.json").read_text()
        )
        self.terrain = json.loads(
            (ROOT / "tests/fixtures/native_zinit_ship_deck.json").read_text()
        )
        self.monsters = {
            row["ref"]: row
            for row in json.loads(
                (ROOT / "tests/fixtures/native_zinit_ship_monsters.json").read_text()
            )
        }

    def compile(self, document=None):
        return compile_rooms(
            document or self.encounters,
            geometry=prepare_geometry(self.terrain),
            exploration=self.terrain,
            monster=self.monsters.__getitem__,
        )

    def test_native_three_five_six_waves_reuse_only_victory_qualified_deck(self):
        rooms, topology = self.compile()
        self.assertEqual(
            [sum(row["count"] for row in room["monsters"]) for room in rooms], [3, 5, 6]
        )
        self.assertTrue(all(room["cells"] == topology[0]["cells"] for room in topology))
        validate_sequential_arenas(self.controller, topology)
        invalid = deepcopy(topology)
        invalid[1]["requires"] = ["voyage-stage-1-admission"]
        with self.assertRaisesRegex(ValueError, "earlier actual victory"):
            validate_sequential_arenas(self.controller, invalid)
        no_explicit_reuse = deepcopy(self.encounters)
        no_explicit_reuse.pop("sequential_arenas")
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.compile(no_explicit_reuse)

    def test_each_phase_preserves_native_program_and_real_spawn_arguments(self):
        selected = dict(map_id=980)
        character = dict(instance_id=99)
        for room, event, scenario, refs in (
            (1, 15993, 2015, [3771, 3771, 3771]),
            (2, 16008, 2018, [3783, 3783, 3783, 3784, 3784]),
            (3, 15999, 2016, [3769, 3769, 3769, 3770, 3770, 3770]),
        ):
            members = [dict(id=-n - 1, ref=ref) for n, ref in enumerate(refs)]
            db = Mock()
            db.execute.return_value.fetchone.return_value = dict(
                members=members, status="available", asset_map_id=980
            )
            effect = dict(
                event=event,
                arguments=list(
                    self.native["argument_sources"][str(event)]["room_actors"]
                ),
            )
            with patch.object(mechanics, "sources", return_value=self.native):
                arguments = mechanics._arguments(db, character, effect, selected)
                packet, body = mechanics.scenario_packet(selected, event, arguments)
                self.assertEqual(packet, 13411)
                self.assertEqual(
                    struct.unpack(">BiiB", body[:10]),
                    (0, event, scenario, len(arguments)),
                )
                self.assertEqual(arguments, [-n - 1 for n in range(len(arguments))])
                members[0]["ref"] = 1
                with self.assertRaisesRegex(ValueError, "actual native room actor"):
                    mechanics._arguments(db, character, effect, selected)
        self.assertEqual(self.native["scenes"], {})
        self.assertIsNone(self.controller["admission"]["objective_id"])
        self.assertTrue(
            all(
                effect["kind"] != "quest_objective"
                for step in self.controller["steps"]
                for effect in step["effects"]
            )
        )

    def test_owned_stage_admits_native_ally_only_for_exact_durable_original_group(self):
        character = dict(id=7, account_id=2, map_id=980, instance_id=99, x=0, y=-3, z=0)
        members = [
            dict(id=-n - 1, ref=3771, map_id=980, instance_id=99, x=n, y=-3, z=0)
            for n in range(3)
        ]
        selected = dict(
            map_id=980, steps=[dict(kind="room_admission", reference=1, requires=[])]
        )
        db = Mock()
        db.execute.side_effect = [
            SimpleNamespace(fetchone=lambda: dict(current_room=1, status="active")),
            SimpleNamespace(
                fetchone=lambda: dict(
                    members=members, status="available", asset_map_id=980
                )
            ),
        ]
        store = SimpleNamespace(connection=lambda: nullcontext(db))
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            return_value=({}, {}),
        ), patch.object(
            admission.controller, "policy", return_value=selected
        ), patch.object(
            admission.controller, "_scope", return_value=(selected, set())
        ), patch(
            "wakfu_server.owned_story_refresh.pending", return_value=None
        ), patch.object(
            mechanics, "sources", return_value=self.native
        ), patch.object(
            mechanics, "executor", return_value=Mock()
        ), patch.object(
            admission.controller,
            "_settle",
            return_value=dict(packets=[(13411, b"native")]),
        ) as settle:
            result = admission.prepare(store, character, members)
            self.assertEqual(result["packets"], [(13411, b"native")])
            self.assertEqual(
                validate(result["mission_allies"], character, members)["helpers"],
                (("sailor", 3781, 15, "player", "self"),),
            )
            self.assertEqual(settle.call_args.kwargs["kind"], "room_admission")
            self.assertEqual(settle.call_args.kwargs["reference"], 1)
        wrong = deepcopy(members)
        wrong[0]["ref"] = 3783
        with self.assertRaises(ValueError):
            admit(character, wrong, policy=VOYAGE_POLICY, room=1)

    def test_available_observer_uses_the_durable_group_without_constructing_an_ally(
        self,
    ):
        character = dict(id=7, account_id=2, map_id=980, instance_id=99, x=0, y=-3, z=0)
        members = [dict(id=-1, ref=3771, map_id=980, instance_id=99, x=1, y=-3, z=0)]
        selected = dict(
            map_id=980, steps=[dict(kind="room_available", reference=1, requires=[])]
        )
        db = Mock()

        def execute(sql, *args):
            value = (
                dict(current_room=1, status="active")
                if "dungeon_room_runs" in sql
                else dict(members=members, status="available", asset_map_id=980)
            )
            return SimpleNamespace(fetchone=lambda: value)

        db.execute.side_effect = execute
        store = SimpleNamespace(connection=lambda: nullcontext(db))
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            return_value=({}, {}),
        ), patch.object(
            admission.controller, "policy", return_value=selected
        ), patch.object(
            admission.controller, "_scope", return_value=(selected, set())
        ), patch(
            "wakfu_server.owned_story_refresh.pending", return_value=None
        ), patch.object(
            mechanics, "sources", return_value=self.native
        ), patch.object(
            mechanics, "executor", return_value=Mock()
        ), patch.object(
            admission.controller,
            "_settle",
            return_value=dict(packets=[(13411, b"intro")]),
        ) as settle, patch(
            "wakfu_server.combat_mission_allies.admit"
        ) as ally:
            self.assertEqual(
                admission.observe_room_available(store, character), [(13411, b"intro")]
            )
            self.assertEqual(settle.call_args.kwargs["kind"], "room_available")
            ally.assert_not_called()
