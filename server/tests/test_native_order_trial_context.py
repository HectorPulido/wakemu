"""Pure source checks for the uncompiled native order-trial ownership context."""

from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import Mock, patch

from wakfu_server import (
    dungeon_runtime_config,
    generic_transports,
    native_order_trial_admission as admission,
    native_order_trial_context as order_context,
    owned_noncombat_context,
    owned_story_controller,
    owned_story_exits,
    world_static,
)
from wakfu_server.actor_approach import approach_path
from wakfu_server.combat_geometry import prepare_geometry


class NativeOrderTrialContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile_dir = (
            Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"
        )
        cls.controller = json.loads(
            (cls.profile_dir / "astrub-pizzlarva-885.json").read_text()
        )
        cls.instance = json.loads(
            (cls.profile_dir / "astrub-pizzlarva-885.instance.json").read_text()
        )
        cls.exploration = json.loads(
            (cls.profile_dir / "astrub-pizzlarva-885.exploration.json").read_text()
        )
        cls.exit_source = generic_transports.source(885, 23627)
        cls.destination = next(
            row
            for row in cls.exit_source["destinations"]
            if row["destination_id"] == 2016
        )
        cls.binding = dict(
            source_id=23627,
            destination_id=2016,
            source_sha256=dungeon_runtime_config.canonical_hash(cls.exit_source),
            source_position=[0, 1, 0],
            criterion=cls.destination["criterion"],
            destination={
                key: cls.destination[key] for key in ("map_id", "x", "y", "z")
            },
        )
        cls.topology = dict(
            policy=owned_noncombat_context.NARRATIVE,
            asset_map_id=885,
            rooms=[],
            owned_story_controller=cls.controller,
            native_story_exits=[cls.binding],
        )
        cls.configuration = dict(topology=cls.topology)

    def test_original_entry_direction_and_typed_context_have_no_mission_effects(self):
        value = admission.document()
        entrance = value["sources"]["entrance"]
        native_source = next(
            row
            for row in world_static.objects(entrance["map_id"])
            if row["id"] == entrance["object_id"]
        )
        character = dict(
            id=19,
            account_id=23,
            map_id=entrance["map_id"],
            instance_id=0,
            x=entrance["approaches"][0][0],
            y=entrance["approaches"][0][1],
            z=entrance["approaches"][0][2],
        )
        proof = admission.plan(
            value,
            character,
            struct.pack(">qHH", entrance["object_id"], 0, 0),
            native_source=native_source,
        )
        self.assertEqual((proof.mode, proof.effect_reference), ("entrance", 1457))
        self.assertEqual(value["context"]["map_id"], 885)
        self.assertEqual(value["context"]["arrival"], [0, 0, 0])
        self.assertEqual(value["context"]["direction"], 7)
        self.assertEqual(self.controller["admission"]["objective_id"], None)
        self.assertEqual(
            self.controller["steps"],
            [
                {
                    "id": "order-context-ready",
                    "kind": "world_ready",
                    "reference": 885,
                    "requires": [],
                    "effects": [],
                    "evidence": self.controller["steps"][0]["evidence"],
                }
            ],
        )
        self.assertEqual(
            order_context.policy(self.configuration)["id"],
            "astrub-pizzlarva-native-context",
        )

        wrong_facing = deepcopy(value)
        wrong_facing["context"]["direction"] = 6
        with self.assertRaisesRegex(ValueError, "original coordinate program"):
            admission.validate(wrong_facing)
        with self.assertRaisesRegex(ValueError, "arrival cannot assign progress"):
            profile = deepcopy(self.controller)
            profile["steps"][0]["effects"] = [
                {"kind": "quest_objective", "quest_id": 2149, "objective_id": 12}
            ]
            invalid = dict(
                topology={
                    **self.topology,
                    "owned_story_controller": profile,
                }
            )
            order_context.policy(invalid)

    def test_native_exit_is_pinned_free_and_rejects_source_or_cost_mutation(self):
        declared = owned_story_exits.declared_sources(
            self.topology, [self.exit_source], map_id=885
        )
        self.assertEqual(declared, frozenset({23627}))
        self.assertEqual(self.destination["destination_id"], 2016)
        self.assertEqual(
            (
                self.destination["map_id"],
                self.destination["x"],
                self.destination["y"],
                self.destination["z"],
                self.destination["direction"],
                self.destination["cyW"],
                self.destination["cyX"],
                self.destination["cyZ"],
            ),
            (546, -4, -8, 3, 3, 0, 0, -1),
        )
        with self.assertRaisesRegex(ValueError, "exact native source"):
            mutated_binding = deepcopy(self.binding)
            mutated_binding["source_sha256"] = "0" * 64
            owned_story_exits.declared_sources(
                {**self.topology, "native_story_exits": [mutated_binding]},
                [self.exit_source],
                map_id=885,
            )
        with self.assertRaisesRegex(ValueError, "endpoint or native cost changed"):
            paid_source = deepcopy(self.exit_source)
            paid_source["destinations"][0]["cyX"] = 1
            paid_binding = deepcopy(self.binding)
            paid_binding["source_sha256"] = dungeon_runtime_config.canonical_hash(
                paid_source
            )
            owned_story_exits.declared_sources(
                {**self.topology, "native_story_exits": [paid_binding]},
                [paid_source],
                map_id=885,
            )

    def test_exit_authentication_allows_questless_native_return_without_side_effects(
        self,
    ):
        character = dict(id=19, account_id=23, map_id=885, instance_id=991)
        body = struct.pack(">qiBi", 23627, 2016, 0, 2)
        db, store = Mock(), Mock()
        no_mission = dict(completed=[], running=[], variables={}, objectives=[])
        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            return_value=(None, self.configuration),
        ), patch(
            "wakfu_server.owned_story_controller._scope",
            return_value=(self.controller, set()),
        ), patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value=no_mission,
        ) as load:
            result = owned_story_exits.authenticate_exit(
                db,
                store,
                character,
                body,
                source_allowed=lambda _character, _source: True,
            )
        self.assertEqual(result["destination"], self.destination)
        self.assertEqual(result["completed_steps"], set())
        self.assertEqual(no_mission["completed"], [])
        load.assert_called_once()

        with patch(
            "wakfu_server.dungeon_runtime.configuration_for_instance",
            return_value=(None, self.configuration),
        ), patch(
            "wakfu_server.owned_story_controller._scope",
            return_value=(self.controller, set()),
        ), patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value=no_mission,
        ):
            with self.assertRaisesRegex(ValueError, "source/approach"):
                owned_story_exits.authenticate_exit(
                    db,
                    store,
                    character,
                    body,
                    source_allowed=lambda _character, _source: False,
                )

    def test_native_exploration_geometry_connects_entry_to_free_exit(self):
        geometry = prepare_geometry(
            dict(
                map_id=885,
                cells=self.exploration["cells"],
                edges=self.exploration["edges"],
            )
        )
        self.assertEqual(len(geometry.cells), 251)
        start, exit_position = (0, 0, 0), (0, 1, 0)
        self.assertIn(start, geometry.cells)
        self.assertIn(exit_position, geometry.cells)
        path = approach_path(geometry, start, lambda cell: cell == exit_position)
        self.assertEqual(path, (start, exit_position))
        self.assertIn((start, exit_position), geometry.edges)

    def test_typed_context_geometry_accessor_returns_the_corrected_pinned_source(self):
        selected = order_context.policy(self.configuration)
        self.assertIsNotNone(selected)
        self.assertEqual(
            selected["geometry_source"]["sha256"],
            "7563892ab718f53da902cd1c12331dfa12048febc43e60f2b0085f050a1d9077",
        )
        document = order_context.geometry(self.configuration)
        self.assertEqual(document["map_id"], 885)
        self.assertEqual(document["schema"], "reviewed-native-order-trial-layout-v1")
        original_geometry = deepcopy(document)
        document["map_id"] = 999
        document["source_hashes"]["client/contents/maps/tplg/885.jar"] = "0" * 64
        fresh_geometry = order_context.geometry(self.configuration)
        self.assertEqual(fresh_geometry, original_geometry)

        admission_doc = order_context.admission(self.configuration)
        self.assertTrue(admission_doc["enabled"])
        original_admission = deepcopy(admission_doc)
        admission_doc["sources"]["normal"]["object_id"] = 1
        fresh_admission = order_context.admission(self.configuration)
        self.assertEqual(fresh_admission, original_admission)

        forged = deepcopy(self.topology)
        forged["owned_story_controller"]["native_order_trial_context"][
            "geometry_source"
        ]["sha256"] = ("0" * 64)
        with self.assertRaisesRegex(ValueError, "source attestation changed"):
            order_context.geometry({"topology": forged})


if __name__ == "__main__":
    unittest.main()
