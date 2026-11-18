"""Conditional story exits use actual native branches and locked quest state."""

from copy import deepcopy
import json
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from wakfu_server import generic_transports, owned_story_exits as exits
from wakfu_server.dungeon_runtime_config import canonical_hash


class OwnedStoryExitTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=7, account_id=3, map_id=887, instance_id=99, x=0, y=0, z=0
        )
        self.completed = []
        self.sources = {
            identity: generic_transports.source(887, identity)
            for identity in (23582, 23614)
        }
        bindings = []
        for identity, source in self.sources.items():
            for target in source["destinations"]:
                bindings.append(
                    dict(
                        source_id=identity,
                        destination_id=target["destination_id"],
                        source_position=[source[k] for k in ("x", "y", "z")],
                        source_sha256=canonical_hash(source),
                        criterion=target["criterion"],
                        destination={k: target[k] for k in ("map_id", "x", "y", "z")},
                    )
                )
        self.configuration = dict(topology=dict(native_story_exits=bindings))
        self.addCleanup(patch.stopall)
        patch.object(
            exits.owned_story_controller,
            "_scope",
            return_value=(dict(map_id=887), set()),
        ).start()
        patch.object(
            exits.dungeon_runtime,
            "configuration_for_instance",
            return_value=({}, self.configuration),
        ).start()
        patch.object(
            exits.storage,
            "load_locked",
            side_effect=lambda *_: dict(completed=self.completed),
        ).start()

    def resolve(self, source, destination, *, allowed=True):
        return exits.authenticate_exit(
            None,
            None,
            self.character,
            struct.pack(">qiBi", source, destination, 0, 2),
            source_allowed=lambda *_: allowed,
        )

    def test_all_four_actual_native_branches_respect_completed_state_and_keep_literal_destination(
        self,
    ):
        for source, destination, completed, target in (
            (23582, 2074, [2170], 898),
            (23582, 2002, [], 527),
            (23614, 2075, [2170], 898),
            (23614, 2003, [], 747),
        ):
            with self.subTest(source=source, destination=destination):
                self.completed = completed
                result = self.resolve(source, destination)
                self.assertEqual(result["destination"]["map_id"], target)
                self.assertEqual(
                    result["destination"]["criterion"], result["binding"]["criterion"]
                )
                self.completed = [] if completed else [2170]
                with self.assertRaisesRegex(ValueError, "criterion"):
                    self.resolve(source, destination)

    def test_hash_endpoint_approach_mode_and_unknown_predicate_cannot_bypass_scope(
        self,
    ):
        original = deepcopy(self.configuration)
        for mutation in ("hash", "endpoint", "approach", "mode"):
            self.configuration.clear()
            self.configuration.update(deepcopy(original))
            row = next(
                r
                for r in self.configuration["topology"]["native_story_exits"]
                if r["destination_id"] == 2003
            )
            if mutation == "hash":
                row["source_sha256"] = "0" * 64
            elif mutation == "endpoint":
                row["destination"]["map_id"] = 999
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                if mutation == "mode":
                    exits.authenticate_exit(
                        None,
                        None,
                        self.character,
                        struct.pack(">qiBi", 23614, 2003, 1, 2),
                        source_allowed=lambda *_: True,
                    )
                else:
                    self.resolve(23614, 2003, allowed=mutation != "approach")
        for predicate in (
            "True",
            "IsAchievementComplete(2170) or True",
            "! IsAchievementComplete(2170)",
        ):
            with self.subTest(predicate=predicate), self.assertRaises(ValueError):
                exits.criterion_allowed(predicate, set())

    def test_actual_crypt_and_nest_exit_pins_reject_changed_authority_or_native_cost(
        self,
    ):
        root = Path(__file__).parent
        sources = json.loads(
            (root / "fixtures/native_astrub_crypt_nest_sources.json").read_text()
        )
        for slug, map_id, identities in (
            ("astrub-crypt-889", 889, {23618}),
            ("astrub-nest-728", 728, {20652, 26431}),
        ):
            document = json.loads(
                (
                    root.parent
                    / f"wakfu_server/maps/owned_story_profiles/{slug}.configuration.json"
                ).read_text()
            )
            topology = document["topology"]
            selected_sources = [row for row in sources if row["map_id"] == map_id]
            self.assertEqual(
                exits.declared_sources(topology, selected_sources, map_id=map_id),
                identities,
            )
            binding = topology["native_story_exits"][0]
            source = next(
                row for row in selected_sources if row["id"] == binding["source_id"]
            )

            changed_endpoint = deepcopy(binding)
            changed_endpoint["destination"]["x"] += 1
            changed_topology = deepcopy(topology)
            changed_topology["native_story_exits"][0] = changed_endpoint
            with self.subTest(slug=slug, mutation="endpoint"), self.assertRaises(
                ValueError
            ):
                exits.declared_sources(
                    changed_topology, selected_sources, map_id=map_id
                )

            changed_source = deepcopy(source)
            changed_source["destinations"][0]["cyZ"] += 1
            changed_sources = [
                changed_source if row["id"] == source["id"] else row
                for row in selected_sources
            ]
            with self.subTest(slug=slug, mutation="native-cost"), self.assertRaises(
                ValueError
            ):
                exits.declared_sources(topology, changed_sources, map_id=map_id)

            unqualified = deepcopy(topology)
            unqualified.pop("owned_story_controller", None)
            unqualified.pop("owned_object_trials", None)
            with self.subTest(slug=slug, mutation="archetype"), self.assertRaisesRegex(
                ValueError, "authority"
            ):
                exits.declared_sources(unqualified, selected_sources, map_id=map_id)

    def test_published_story_exit_configs_project_native_sources_and_preserve_compound_criteria(
        self,
    ):
        from wakfu_server.storage import native_catalog

        with native_catalog._database().connection() as db:
            with db.cursor() as cursor:
                cursor.execute(
                    "SELECT route_key, configuration "
                    "FROM dungeon_runtime_configurations"
                )
                rows = cursor.fetchall()

        route_keys = set()
        branch_count = 0
        compound_found = False
        for row in rows:
            configuration = row["configuration"]
            topology = configuration.get("topology", {})
            bindings = topology.get("native_story_exits", ())
            if not bindings:
                continue
            route_keys.add(row["route_key"])
            branch_count += len(bindings)
            map_id = topology["asset_map_id"]
            sources = [
                generic_transports.source(map_id, identity)
                for identity in {binding["source_id"] for binding in bindings}
            ]
            self.assertTrue(all(source is not None for source in sources))
            compound = [
                binding for binding in bindings if " and " in binding["criterion"]
            ]
            if compound:
                compound_found = True
                with patch.object(
                    exits,
                    "criterion_allowed",
                    side_effect=AssertionError(
                        "projection must preserve native criterion"
                    ),
                ):
                    declared = exits.declared_sources(topology, sources, map_id=map_id)
                self.assertTrue(
                    {binding["source_id"] for binding in compound} <= declared
                )
            else:
                declared = exits.declared_sources(topology, sources, map_id=map_id)
            self.assertEqual(
                declared,
                {binding["source_id"] for binding in bindings},
                configuration.get("slug"),
            )

        self.assertEqual(len(route_keys), 22)
        self.assertEqual(branch_count, 32)
        self.assertTrue(compound_found)

    def test_unfinished_wrapper_uses_ordinary_cleanup_and_cannot_handle_completed_cinematic_branch(
        self,
    ):
        from wakfu_server import dungeon_exit

        received = []

        def leave(*_args, **kwargs):
            received.append(kwargs)
            return kwargs["destination_for"](None, self.character, {})

        with patch.object(dungeon_exit, "_leave", side_effect=leave):
            result = exits.leave_unfinished(
                None,
                3,
                "lease",
                7,
                struct.pack(">qiBi", 23614, 2003, 0, 2),
                source_allowed=lambda *_: True,
                in_fight=lambda *_: False,
            )
            self.assertEqual(result["map_id"], 747)
            self.assertTrue(callable(received[-1]["in_fight"]))
            self.completed = [2170]
            with self.assertRaisesRegex(ValueError, "native continuation"):
                exits.leave_unfinished(
                    None,
                    3,
                    "lease",
                    7,
                    struct.pack(">qiBi", 23582, 2074, 0, 2),
                    source_allowed=lambda *_: True,
                    in_fight=lambda *_: False,
                )
