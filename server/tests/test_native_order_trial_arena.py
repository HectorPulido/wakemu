"""The order-trial arena preserves the pinned floor and native QI surfaces."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import struct
import unittest

from wakfu_server import native_order_trial_admission as admission
from wakfu_server import native_order_trial_arena as order_arena
from wakfu_server import native_order_trial_context as order_context
from wakfu_server import combat_wire
from wakfu_server import combat_terrain
from wakfu_server.combat_qi_surface_selection import native_surface_indices
from wakfu_server.combat_actor_snapshot import native_actor_catalog


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "server/wakfu_server/maps/owned_story_profiles/astrub-pizzlarva-885.configuration.json"
)
SOURCES = (
    Path(__file__).with_name("fixtures") / "native_pizzlarva_admission_sources.json"
)


class NativeOrderTrialArenaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configuration = json.loads(CONFIG.read_text())
        cls.native_sources = {row["id"]: row for row in json.loads(SOURCES.read_text())}
        cls.profile = admission.document()
        cls.policy = order_context.policy(cls.configuration)
        cls.scoped = {"configuration": cls.configuration, "policy": cls.policy}

    def proof_for(self, mode):
        source = self.profile["sources"][mode]
        x, y, z = source["approaches"][0]
        character = dict(
            id=17,
            account_id=4,
            instance_id=144115188075855873,
            map_id=885,
            x=x,
            y=y,
            z=z,
        )
        proof = admission.plan(
            self.profile,
            character,
            struct.pack(">qHH", source["object_id"], 0, 0),
            native_source=self.native_sources[source["object_id"]],
        )
        return replace(proof, generation="isolated-order-arena-test"), character

    def test_normal_and_hard_arenas_use_exact_floor_surfaces_and_singleton_deployment(
        self,
    ):
        geometry = order_context.geometry(self.configuration)
        for mode in ("normal", "hard"):
            with self.subTest(mode=mode):
                proof, character = self.proof_for(mode)
                arena = order_arena.prepare(self.scoped, character, proof)
                self.assertEqual(arena["map_id"], 885)
                self.assertEqual(arena["instance_id"], 1)
                self.assertEqual(
                    arena["native_order_instance_id"], character["instance_id"]
                )
                self.assertEqual(
                    combat_wire.decode_topology(combat_wire.topology(arena))[
                        "instance_id"
                    ],
                    1,
                )
                self.assertEqual(len(arena["validated_cells"]), 206)
                self.assertEqual(len(arena["valid_edges"]), 758)
                self.assertEqual(
                    arena["placement_cells"],
                    {
                        1: {(character["x"], character["y"], character["z"])},
                        0: {
                            tuple(
                                geometry["reviewed_arcade_layout"][mode][
                                    "reviewed_spawn_anchor"
                                ]
                            )
                        },
                    },
                )
                selected_surfaces = native_surface_indices(
                    combat_terrain.prepare_terrain(885).surfaces,
                    arena["validated_cells"],
                )
                self.assertEqual(len(selected_surfaces), 206)
                for (x, y), surface_index in selected_surfaces.items():
                    offset = (y - arena["y"]) * arena["width"] + x - arena["x"]
                    self.assertEqual(arena["cell_masks"][offset], surface_index)
                self.assertEqual(
                    arena["native_qi_surface_provenance"]["source_sha256"],
                    geometry["source_hashes"]["client/contents/maps/tplg/885.jar"],
                )
                self.assertTrue(arena["native_full_room_scope"])
                self.assertNotIn("native_initial_glyphs", arena)
                self.assertNotIn("actors", arena)
                self.assertEqual(
                    arena["native_environment_participant_footprints"],
                    {
                        "schema": "wakemu-initial-environment-participants-v1",
                        "map_id": 885,
                        "actors": [
                            {
                                "id": character["id"],
                                "reference": None,
                                "position": [character[key] for key in ("x", "y", "z")],
                                "physical_radius": native_actor_catalog()[
                                    "default_actor_radius"
                                ],
                                "source": "native-actor-characteristics.default_actor_radius",
                            }
                        ],
                    },
                )

    def test_arena_rejects_wrong_source_pose_owner_or_context_pin(self):
        proof, character = self.proof_for("normal")
        with self.assertRaisesRegex(ValueError, "authenticated native mode owner"):
            order_arena.prepare(
                self.scoped,
                character,
                replace(proof, owner_id=proof.owner_id + 1),
            )
        with self.assertRaisesRegex(ValueError, "actual accepted button approach"):
            order_arena.prepare(
                self.scoped,
                {**character, "x": character["x"] + 1},
                proof,
            )
        with self.assertRaisesRegex(ValueError, "actual accepted button approach"):
            order_arena.prepare(
                self.scoped,
                character,
                replace(proof, source_id=proof.source_id + 1),
            )

        forged = deepcopy(self.configuration)
        forged["topology"]["owned_story_controller"]["native_order_trial_context"][
            "geometry_source"
        ]["sha256"] = ("0" * 64)
        with self.assertRaisesRegex(ValueError, "source attestation changed"):
            order_context.policy(forged)


if __name__ == "__main__":
    unittest.main()
