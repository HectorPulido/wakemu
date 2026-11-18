"""Generated roster candidates preserve reviewed geometry and native grades."""

from copy import deepcopy
import unittest

from tools import prepare_progressive_generated_dungeons as progressive


class ProgressiveGeneratedDungeonTests(unittest.TestCase):
    def setUp(self):
        self.monsters = [
            dict(
                ref=reference,
                name=str(reference),
                min_level=10,
                max_level=30,
                raw_visual_arrays={"csc": [43] if reference == 3 else []},
                native_abilities=[{"spell_id": 1}],
            )
            for reference in (1, 2, 3)
        ]
        self.admission = dict(
            schema="native-npc-activation-v1",
            enabled_monsters={
                str(reference): dict(min_level=10, max_level=30, spell_ids=[1])
                for reference in (1, 2, 3)
            },
        )

        def monster(reference, count):
            return dict(
                ref_id=reference,
                count=count,
                role="boss" if reference == 3 else "monster",
                native_min_level=10,
                native_max_level=30,
            )

        self.configuration = dict(
            version=1,
            route={"key": "synthetic_generated_route", "definition_id": 91},
            topology=dict(
                asset_map_id=902,
                rooms=[
                    dict(
                        order=order,
                        cells=[(order, 0, 0)],
                        anchor=(order, 0, 0),
                        encounter_scene={"retained_native_custom_rule": True},
                    )
                    for order in (1, 2, 3)
                ],
                doors=[{"source_room": 1, "destination_room": 2, "anchor": (2, 0, 0)}],
                exploration_geometry={"edges": [((1, 0, 0), (2, 0, 0))]},
            ),
            level_policy=dict(
                mode="native_stage_progression",
                optional_mode="native_minimum",
                provenance="Reviewed synthetic native grade ranges",
            ),
            context_policy={"policy_version": 1, "retained_setting": True},
            evidence_hashes={"plan": "old", "topology": "retained-geometry"},
            compiled_plan=dict(
                official=False,
                reviewed_official=False,
                roster_policy_evidence={
                    "policy_mode": progressive.GENERATED,
                    "boss_references": [3],
                },
                generated_fields=[{"source": "old_generated_slot"}],
                rooms=[
                    dict(order=1, monsters=[monster(1, 8)]),
                    dict(order=2, monsters=[monster(2, 8)]),
                    dict(order=3, monsters=[monster(1, 7), monster(3, 1)]),
                ],
            ),
        )

    def prepare(self, configuration=None, **kwargs):
        return progressive.prepare(
            self.configuration if configuration is None else configuration,
            self.monsters,
            version=2,
            admission_policy=self.admission,
            **kwargs,
        )

    def test_three_rooms_use_3_6_8_actors_actual_stage_grades_and_final_boss_once(self):
        original = deepcopy(self.configuration)
        candidate = self.prepare()
        assessment = progressive.audit(candidate, self.monsters)
        self.assertEqual([room["quantity"] for room in assessment["rooms"]], [3, 6, 8])
        self.assertEqual(
            [room["weighted_mean_level"] for room in assessment["rooms"]], [10, 20, 30]
        )
        self.assertEqual(
            [room["actual_spawn_level_sum"] for room in assessment["rooms"]],
            [30, 120, 240],
        )
        self.assertTrue(assessment["strict_strength_increase"])
        self.assertTrue(assessment["strict_count_increase"])
        self.assertEqual(candidate["topology"], original["topology"])
        self.assertEqual(candidate["level_policy"], original["level_policy"])
        self.assertEqual(candidate["route"], original["route"])
        self.assertEqual(
            candidate["context_policy"],
            dict(original["context_policy"], policy_version=2),
        )
        self.assertEqual(candidate["version"], 2)
        self.assertNotEqual(
            candidate["evidence_hashes"]["plan"], original["evidence_hashes"]["plan"]
        )
        rooms = candidate["compiled_plan"]["rooms"]
        self.assertFalse(
            any(
                monster["role"] == "boss"
                for room in rooms[:-1]
                for monster in room["monsters"]
            )
        )
        self.assertEqual(
            sum(
                monster["count"]
                for monster in rooms[-1]["monsters"]
                if monster["role"] == "boss"
            ),
            1,
        )
        self.assertNotIn("generated_fields", candidate["compiled_plan"])
        self.assertEqual(self.configuration, original)

    def test_audit_distinguishes_flat_counts_from_increasing_native_stage_levels(self):
        assessment = progressive.audit(self.configuration, self.monsters)
        self.assertTrue(assessment["equal_counts"])
        self.assertFalse(assessment["strict_count_increase"])
        self.assertTrue(assessment["strict_strength_increase"])
        self.assertEqual(
            [room["weighted_mean_level"] for room in assessment["rooms"]], [10, 20, 30]
        )

    def test_reviewed_custom_branch_and_fixed_actor_sources_are_preserved(self):
        for change in ("official", "reviewed", "custom", "branch", "fixed"):
            with self.subTest(change=change):
                config = deepcopy(self.configuration)
                if change == "official":
                    config["compiled_plan"]["official"] = True
                elif change == "reviewed":
                    config["compiled_plan"]["reviewed_official"] = True
                elif change == "custom":
                    config["compiled_plan"]["roster_policy_evidence"][
                        "policy_mode"
                    ] = "reviewed_custom_encounter"
                elif change == "branch":
                    config["topology"]["branch_routes"] = ["reviewed_branch"]
                else:
                    config["topology"]["rooms"][0]["encounter_scene"][
                        "fixed_actor_placements"
                    ] = [{"id": 1}]
                before = deepcopy(config)
                with self.assertRaises(ValueError):
                    self.prepare(config)
                self.assertEqual(config, before)
        custom = deepcopy(self.configuration)
        custom["compiled_plan"]["roster_policy_evidence"][
            "policy_mode"
        ] = "reviewed_custom_encounter"
        result = progressive.batch(
            [custom, self.configuration], self.monsters, admission_policy=self.admission
        )
        self.assertEqual(
            [row["status"] for row in result["records"]],
            ["preserved_custom_or_progressive_policy", "candidate_prepared"],
        )
        self.assertEqual(len(result["candidates"]), 1)
        self.assertFalse(result["installed"])
        self.assertFalse(result["existing_runs_changed"])

    def test_unadmitted_species_blocks_candidate_without_changing_source(self):
        before = deepcopy(self.configuration)
        self.admission["enabled_monsters"].pop("3")
        with self.assertRaisesRegex(ValueError, "boss"):
            self.prepare()
        self.assertEqual(self.configuration, before)


class ProgressiveSourceRecipeTests(unittest.TestCase):
    setUp = ProgressiveGeneratedDungeonTests.setUp
    prepare = ProgressiveGeneratedDungeonTests.prepare

    def source_paths(self):
        config = deepcopy(self.configuration)
        config["provenance"] = "synthetic reviewed source recipe"
        config["route"].update(template_id=92, start_map_id=902)
        config["compiled_plan"].update(
            slug="source-recipes",
            roster_ready=True,
            diagnostics=[],
            source_url="https://example.invalid/source-recipe",
            source_sha256="a" * 64,
            document_sha256="b" * 64,
            definition_id=91,
            template_id=92,
            asset_map_id=902,
        )
        config["topology"]["doors"] = []
        config["compiled_plan"]["generated_fields"] = [
            dict(order=order, source="old generated source slot") for order in (1, 2, 3)
        ]
        return config

    def test_optional_and_scripted_terminal_recipes_remain_exact(self):
        from wakfu_server.dungeon_optional_rooms import POLICY

        config = self.source_paths()
        plan = config["compiled_plan"]
        plan["rooms"][-1]["monsters"][-1]["role"] = "unknown_scripted_controller"
        optional = deepcopy(plan["rooms"][1])
        optional["order"] = 4
        optional["native_source_identity"] = "optional-side-encounter"
        plan["rooms"].append(optional)
        config["topology"]["rooms"].append(
            dict(order=4, anchor=(4, 0, 0), cells=[(4, 0, 0)])
        )
        config["topology"]["optional_room_policy"] = dict(
            policy=POLICY,
            main_room_orders=[1, 2, 3],
            optional_rooms=[
                dict(
                    order=4,
                    source_order=4,
                    access=dict(
                        status="unresolved_native_access",
                        evidence="native source review",
                    ),
                )
            ],
            source_evidence={"4": "native source review"},
        )
        before = deepcopy(config)
        candidate = self.prepare(config)
        self.assertEqual(candidate["topology"], before["topology"])
        self.assertEqual(
            candidate["compiled_plan"]["rooms"][-2:],
            before["compiled_plan"]["rooms"][-2:],
        )
        self.assertEqual(
            [
                sum(m["count"] for m in r["monsters"])
                for r in candidate["compiled_plan"]["rooms"]
            ],
            [3, 6, 8, 8],
        )
        self.assertEqual(config, before)

    def test_fixed_actor_and_terminal_boss_keep_native_identity_positions_and_counts(
        self,
    ):
        config = self.source_paths()
        first = config["compiled_plan"]["rooms"][0]
        first["monsters"] = [
            dict(first["monsters"][0], count=1),
            dict(config["compiled_plan"]["rooms"][1]["monsters"][0], count=7),
        ]
        for order, reference in ((1, 1), (3, 3)):
            room = config["topology"]["rooms"][order - 1]
            room["cells"].append((order, 1, 0))
            room["encounter_scene"].update(
                full_room_scope=True,
                fixed_actor_placements=[
                    dict(
                        reference=reference,
                        cell=(order, 1, 0),
                        direction=3,
                        source=dict(
                            kind="authorized_native_content_reconstruction",
                            uri="fixture:native-source",
                            sha256="a" * 64,
                        ),
                    )
                ],
            )
        before = deepcopy(config)
        candidate = self.prepare(config)
        self.assertEqual(candidate["topology"], before["topology"])
        self.assertEqual(
            candidate["compiled_plan"]["rooms"][-1],
            before["compiled_plan"]["rooms"][-1],
        )
        rows = candidate["compiled_plan"]["rooms"][0]["monsters"]
        self.assertEqual(
            [(row["ref_id"], row["count"]) for row in rows], [(1, 1), (2, 2)]
        )
        for original, changed in zip(
            before["compiled_plan"]["rooms"], candidate["compiled_plan"]["rooms"]
        ):
            self.assertLessEqual(
                {m["ref_id"] for m in changed["monsters"]},
                {m["ref_id"] for m in original["monsters"]},
            )

    def entry_configuration(self):
        from wakfu_server.dungeon_entry_paths import POLICY

        config = self.source_paths()
        originals = deepcopy(config["compiled_plan"]["rooms"])
        plan = config["compiled_plan"]
        plan["rooms"] = [
            dict(deepcopy(originals[0 if order % 2 else 1]), order=order)
            for order in (1, 2, 3, 4)
        ] + [dict(deepcopy(originals[2]), order=5)]
        config["topology"]["rooms"] = [
            dict(order=order, anchor=[order, 0, 0], cells=[[order, 0, 0]])
            for order in (1, 2, 3, 4, 5)
        ]
        config["topology"].update(
            policy="native_mixed_victory_policy",
            entry_path_policy=dict(
                policy=POLICY,
                provenance="synthetic qualified alternative entrances",
                shared_terminal_source_order=5,
                native_required_count=3,
                paths=[
                    dict(
                        key=key,
                        main_source_orders=main,
                        postboss_source_orders=post,
                        terminal_source_order=5,
                        review_status="qualified",
                    )
                    for key, main, post in (
                        ("north", [1, 2, 5], [3, 4]),
                        ("south", [3, 4, 5], [1, 2]),
                    )
                ],
                entry_sources=[
                    dict(map_id=902, source_id=1, destination_id=2, path="north"),
                    dict(map_id=902, source_id=3, destination_id=4, path="south"),
                ],
                entry_transfers=[],
            ),
        )
        return config

    def test_qualified_entry_paths_share_final_source_without_flat_reassignment(self):
        config = self.entry_configuration()
        before = deepcopy(config)
        candidate = self.prepare(config)
        self.assertEqual(candidate["topology"], before["topology"])
        rows = candidate["compiled_plan"]["rooms"]
        self.assertEqual(
            [sum(m["count"] for m in row["monsters"]) for row in rows], [3, 6, 3, 6, 8]
        )
        self.assertEqual(rows[-1], before["compiled_plan"]["rooms"][-1])
        assessment = progressive.audit(candidate, self.monsters)
        self.assertEqual(set(assessment["paths"]), {"north", "south"})
        for path in assessment["paths"].values():
            self.assertEqual(
                [row["quantity"] for row in path["rooms"] if row["main"]], [3, 6, 8]
            )
        for original, changed in zip(before["compiled_plan"]["rooms"], rows):
            self.assertLessEqual(
                {m["ref_id"] for m in changed["monsters"]},
                {m["ref_id"] for m in original["monsters"]},
            )
        self.assertEqual(config, before)

    def test_conflicting_shared_source_rank_is_rejected_without_mutation(self):
        config = self.entry_configuration()
        path = config["topology"]["entry_path_policy"]["paths"][1]
        path.update(main_source_orders=[2, 3, 5], postboss_source_orders=[1, 4])
        before = deepcopy(config)
        with self.assertRaisesRegex(
            ValueError, "conflicting logical progression ranks"
        ):
            self.prepare(config)
        self.assertEqual(config, before)

    def test_optional_vote_rebinds_only_the_validated_plan_pin(self):
        from unittest.mock import patch
        from wakfu_server import dungeon_optional_votes
        from wakfu_server.dungeon_runtime_config import canonical_hash

        rule = deepcopy(dungeon_optional_votes.rules()[0])
        config = self.source_paths()
        config["route"].update(key=rule["route_key"], start_map_id=rule["map_id"])
        config["compiled_plan"]["asset_map_id"] = rule["map_id"]
        config["compiled_plan"]["rooms"][-1]["monsters"][-1][
            "role"
        ] = "scripted_terminal_actor"
        config["topology"]["asset_map_id"] = rule["map_id"]
        config["topology"]["optional_vote_access"] = dict(
            rule_key=rule["key"],
            rule_sha256=dungeon_optional_votes.digest(rule),
            plan_sha256=config["compiled_plan"]["document_sha256"],
        )
        before = deepcopy(config)
        real_rule_for = dungeon_optional_votes.rule_for
        # Use the checked native rule and its actual source revision. Only the
        # process revision provider is isolated; contract validation stays real.
        with patch(
            "wakfu_server.native_catalog.release", return_value=rule["native_revision"]
        ):
            self.assertEqual(real_rule_for(config), rule)
            with patch.object(
                dungeon_optional_votes, "rule_for", wraps=real_rule_for
            ) as checked:
                candidate = self.prepare(config)
            self.assertEqual(checked.call_count, 2)
            self.assertIs(checked.call_args_list[0].args[0], config)
            self.assertIs(checked.call_args_list[1].args[0], candidate)
            self.assertEqual(real_rule_for(candidate), rule)
            new_binding = candidate["topology"]["optional_vote_access"]
            self.assertEqual(
                new_binding["plan_sha256"],
                candidate["compiled_plan"]["document_sha256"],
            )
            self.assertNotEqual(
                new_binding["plan_sha256"],
                before["topology"]["optional_vote_access"]["plan_sha256"],
            )
            restored_topology = deepcopy(candidate["topology"])
            restored_topology["optional_vote_access"]["plan_sha256"] = before[
                "topology"
            ]["optional_vote_access"]["plan_sha256"]
            self.assertEqual(restored_topology, before["topology"])
            self.assertEqual(
                candidate["evidence_hashes"]["topology"],
                canonical_hash(candidate["topology"]),
            )
            stale = deepcopy(candidate)
            stale["topology"]["optional_vote_access"]["plan_sha256"] = before[
                "topology"
            ]["optional_vote_access"]["plan_sha256"]
            with self.assertRaisesRegex(ValueError, "pinned contract changed"):
                real_rule_for(stale)
        self.assertEqual(config, before)
