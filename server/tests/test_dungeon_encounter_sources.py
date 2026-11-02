"""Public-namespace typed source precedence; no game catalog or database."""
from copy import deepcopy
import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server import dungeon_encounter_sources as sources
from wakfu_server import dungeon_local_roster_policy as compiler


class EncounterSourceTests(unittest.TestCase):
    def setUp(self):
        self.plan = dict(
            slug="fixture",
            definition_id=129,
            document_sha256="a" * 64,
            rooms=[
                dict(order=n, monsters=[dict(ref_id=4400 if n == 4 else 4208, count=1)])
                for n in (1, 2, 3, 4)
            ],
        )
        self.native = dict(id=129, native_type="DUNGEON_3_ROOMS", player_count_cng=1)
        proof = dict(
            authority="reviewed fixture source",
            source_hashes={"native-client": "b" * 64},
        )
        self.recipe = dict(
            schema=sources.SCHEMA,
            reviewed=True,
            definition_id=129,
            source_plan_sha256=sources.digest(self.plan),
            native_required_count=3,
            proof=proof,
            stages=[
                dict(order=n, source_room_order=old, source_kind="initial_encounter")
                for n, old in enumerate((1, 2, 4), 1)
            ],
            excluded_sections=[
                dict(
                    source_room_order=3,
                    source_kind="superseded_guide_encounter_section",
                    reason="Dated body conflicts with original eQM and physical source",
                    proof=deepcopy(proof),
                )
            ],
            native_phases=[
                dict(
                    encounter_order=3,
                    source_kind="native_spawn_only_phase",
                    initial_reference=4400,
                    spawn_reference=4211,
                    proof=deepcopy(proof),
                )
            ],
        )

    def test_native_count_conflict_cannot_be_ignored_by_guide_compiler(self):
        before = deepcopy(self.plan)
        with self.assertRaisesRegex(ValueError, "reviewed typed source recipe"):
            sources.reconcile(self.plan, self.native)
        with self.assertRaisesRegex(ValueError, "reviewed typed source recipe"):
            compiler.draft(self.plan, self.native, [])
        self.assertEqual(self.plan, before)

    def test_explicit_recipe_keeps_prior_rosters_and_all_old_source_sections(self):
        before = deepcopy(self.plan)
        result = sources.reconcile(self.plan, self.native, self.recipe)
        self.assertEqual([r["order"] for r in result["rooms"]], [1, 2, 3])
        self.assertEqual([r["source_order"] for r in result["rooms"]], [1, 2, 4])
        self.assertEqual(result["rooms"][0]["monsters"], before["rooms"][0]["monsters"])
        self.assertEqual(result["rooms"][1]["monsters"], before["rooms"][1]["monsters"])
        self.assertEqual(result["rooms"][2]["monsters"], before["rooms"][3]["monsters"])
        self.assertEqual(result["preserved_source_sections"], before["rooms"])
        self.assertFalse(
            result["source_kind_conflict"]["excluded_sections_are_optional"]
        )
        self.assertFalse(
            result["source_kind_conflict"]["excluded_sections_are_native_phases"]
        )
        self.assertEqual(self.plan, before)

    def test_spawn_only_phase_is_metadata_not_an_initial_actor_or_extra_room(self):
        result = sources.reconcile(self.plan, self.native, self.recipe)
        self.assertEqual(len(result["rooms"]), 3)
        self.assertFalse(
            any(m["ref_id"] == 4211 for r in result["rooms"] for m in r["monsters"])
        )
        invalid = deepcopy(self.recipe)
        invalid["stages"][2]["source_kind"] = "native_spawn_only_phase"
        with self.assertRaises(ValueError):
            sources.reconcile(self.plan, self.native, invalid)
        invalid = deepcopy(self.recipe)
        invalid["native_phases"][0]["spawn_reference"] = 4400
        with self.assertRaisesRegex(ValueError, "duplicate an initial actor"):
            sources.reconcile(self.plan, self.native, invalid)

    def test_player_count_and_untyped_enums_do_not_imply_room_count(self):
        native = dict(id=129, native_type="DUNGEON_3_PLAYERS", player_count_cng=3)
        self.assertIsNone(sources.native_required_count(native))
        self.assertEqual(sources.reconcile(self.plan, native), self.plan)
        conflicting = dict(self.native, type="DUNGEON_4_ROOMS")
        with self.assertRaises(ValueError):
            sources.reconcile(self.plan, conflicting)

    def test_unreviewed_wrong_source_and_omitted_sections_fail_closed(self):
        for mutate in (
            lambda r: r.update(reviewed=False),
            lambda r: r.update(source_plan_sha256="0" * 64),
            lambda r: r.update(excluded_sections=[]),
            lambda r: r["excluded_sections"][0].update(
                source_kind="optional_encounter"
            ),
            lambda r: r["native_phases"][0].update(proof={}),
        ):
            invalid = deepcopy(self.recipe)
            mutate(invalid)
            with self.assertRaises(ValueError):
                sources.reconcile(self.plan, self.native, invalid)

    def test_draft_retains_raw_input_and_reports_reviewed_count_authority(self):
        definition = dict(self.native, raw_cno=[4208, 4400])
        catalog = [
            dict(ref=4208, min_level=1, max_level=5, native_abilities=[1]),
            dict(ref=4400, min_level=6, max_level=10, native_abilities=[]),
        ]
        admission = SimpleNamespace(
            admitted=lambda *a, **k: True,
            require=lambda *a, **k: None,
            current_policy=lambda: {},
        )
        with patch.dict(
            sys.modules, {"wakfu_server.dungeon_monster_admission": admission}
        ):
            result = compiler.draft(
                self.plan,
                definition,
                catalog,
                encounter_recipe=self.recipe,
                boss_references=(4400,),
                admission_policy={},
            )
        self.assertEqual(result["original_plan"], self.plan)
        self.assertEqual(result["room_count"], 3)
        self.assertEqual(
            result["room_count_source"], "reviewed_native_encounter_source_recipe"
        )
        self.assertEqual(result["encounter_source_recipe"], self.recipe)
        self.assertEqual(
            result["rooms"][2]["monsters"], self.plan["rooms"][3]["monsters"]
        )

    def test_matching_legacy_count_remains_unchanged_without_recipe(self):
        native = dict(id=129, type="DUNGEON_4_ROOMS")
        result = sources.reconcile(self.plan, native)
        self.assertEqual(result, self.plan)
        self.assertIsNot(result, self.plan)

    def test_noncombat_transit_requires_literal_native_bindings_and_preserves_source(
        self,
    ):
        recipe = deepcopy(self.recipe)
        recipe["excluded_sections"][0].update(
            source_kind="noncombat_native_transit_section",
            standalone_encounter=False,
            native_region_ids=[9],
            native_transport_source_ids=[31594],
        )
        result = sources.reconcile(self.plan, self.native, recipe)
        self.assertEqual([r["source_order"] for r in result["rooms"]], [1, 2, 4])
        self.assertEqual(result["preserved_source_sections"], self.plan["rooms"])
        self.assertFalse(
            result["source_kind_conflict"]["excluded_sections_are_optional"]
        )

    def test_noncombat_transit_without_positive_native_transport_proof_fails(self):
        recipe = deepcopy(self.recipe)
        row = recipe["excluded_sections"][0]
        row.update(
            source_kind="noncombat_native_transit_section",
            standalone_encounter=False,
            native_region_ids=[9],
            native_transport_source_ids=[],
        )
        with self.assertRaisesRegex(ValueError, "native regions and transport"):
            sources.reconcile(self.plan, self.native, recipe)
        row["native_transport_source_ids"] = [31594]
        row["standalone_encounter"] = True
        with self.assertRaisesRegex(ValueError, "native regions and transport"):
            sources.reconcile(self.plan, self.native, recipe)

    def test_noncombat_transit_kind_cannot_be_relabelled_as_optional_or_phase(self):
        recipe = deepcopy(self.recipe)
        for kind in ("optional", "native_spawn_only_phase", "unknown"):
            recipe["excluded_sections"][0]["source_kind"] = kind
            with self.assertRaisesRegex(ValueError, "source-kind evidence"):
                sources.reconcile(self.plan, self.native, recipe)


if __name__ == "__main__":
    unittest.main()
