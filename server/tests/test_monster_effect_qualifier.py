import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from qualify_monster_effect_work import (
    plan_contexts,
    qualify,
    reusable_case,
    select_spells,
)


class EffectQualifierTests(unittest.TestCase):
    def index(self):
        return dict(
            spell_index={"7": {}, "8": {}},
            blocks=[dict(block_id="family:327", spell_ids=[7, 8])],
        )

    def test_selected_block_and_explicit_spell_intersection(self):
        self.assertEqual(select_spells(self.index(), ["family:327"], [8]), [8])
        with self.assertRaises(ValueError):
            select_spells(self.index(), ["unknown"])
        with self.assertRaises(ValueError):
            select_spells(self.index(), ["family:327"], [9])

    def test_native_level_bounds_preserve_owned_spell_override(self):
        row = dict(
            spell_id=7,
            resolved_native_level_contexts=[dict(ref=1, native_actor_ranges=[[3, 8]])],
        )
        contexts = plan_contexts(
            row, lambda ref, level: [dict(spell_id=7, spell_level=2)], 5, 6, 10
        )
        self.assertEqual(
            [(c["actor_level"], c["spell_level"]) for c in contexts], [(5, 2), (6, 2)]
        )

    def test_duplicate_native_ranges_deduplicate_exact_identity(self):
        row = dict(
            spell_id=7,
            resolved_native_level_contexts=[
                dict(ref=1, native_actor_ranges=[[3, 4], [3, 4]])
            ],
        )
        contexts = plan_contexts(
            row, lambda ref, level: [dict(spell_id=7, spell_level=level)], limit=10
        )
        self.assertEqual(len(contexts), 2)

    def test_missing_actual_native_ownership_rejects_context(self):
        row = dict(
            spell_id=7,
            resolved_native_level_contexts=[dict(ref=1, native_actor_ranges=[[3, 3]])],
        )
        with self.assertRaisesRegex(ValueError, "ownership"):
            plan_contexts(row, lambda *args: [])

    def test_pending_spell_does_not_stop_next_selected_spell_and_budget_is_enforced(
        self,
    ):
        contexts = [dict(spell_id=i) for i in range(3)]
        called, saved = [], []

        def run(context):
            called.append(context["spell_id"])
            return dict(status="pending" if context["spell_id"] == 0 else "validated")

        rows, executed = qualify(
            contexts,
            run_case=run,
            cache_case=lambda c: None,
            persist=lambda rows, count: saved.append((len(rows), count)),
            maximum_cases=2,
        )
        self.assertEqual(called, [0, 1])
        self.assertEqual((len(rows), executed), (2, 2))
        self.assertEqual(saved, [(1, 1), (2, 2)])

    def cache(self):
        context = dict(reference=1, actor_level=3, spell_id=7, spell_level=2)
        case = dict(level=3, spell_id=7, spell_level=2, status="validated")
        index = dict(
            actual_case_cache=[
                dict(
                    context_ref="a",
                    proof_key="p",
                    reference=1,
                    actor_level=3,
                    spell_id=7,
                    spell_level=2,
                    original_json_pointer="/rows/0/cases/0",
                )
            ],
            receipt_contexts={
                "a": dict(
                    receipt="original.json",
                    sha256="receipt-sha",
                    candidate_manifest_sha256="candidate",
                    source_sha256={"runtime.py": "runtime-sha"},
                )
            },
        )
        original = dict(sources_stable=True, rows=[dict(cases=[dict(raw_case=case)])])
        return context, case, index, original

    def test_reuse_preserves_original_receipt_pointer_and_does_not_mutate_case(self):
        context, case, index, original = self.cache()
        calls = []

        def loader(path, digest):
            calls.append((path, digest))
            return original

        result = reusable_case(
            index, context, {"runtime.py": "runtime-sha"}, "candidate", loader
        )
        self.assertEqual(calls, [("original.json", "receipt-sha")])
        self.assertEqual(result[1]["json_pointer"], "/rows/0/cases/0")
        result[0]["status"] = "changed"
        self.assertEqual(case["status"], "validated")

    def test_source_or_native_level_changes_prevent_rebinding(self):
        context, case, index, original = self.cache()
        loader = lambda *args: self.fail("Must not load incompatible receipt")
        self.assertIsNone(
            reusable_case(
                index, context, {"runtime.py": "new-source"}, "candidate", loader
            )
        )
        context["actor_level"] = 4
        self.assertIsNone(
            reusable_case(
                index, context, {"runtime.py": "runtime-sha"}, "candidate", loader
            )
        )

    def test_mismatched_original_json_pointer_fails_closed(self):
        context, case, index, original = self.cache()
        case["spell_level"] = 9
        with self.assertRaisesRegex(ValueError, "identity"):
            reusable_case(
                index,
                context,
                {"runtime.py": "runtime-sha"},
                "candidate",
                lambda *args: original,
            )


class EffectQualifierMalformedCacheTests(unittest.TestCase):
    def test_invalid_source_footprint_is_not_reusable_or_loaded(self):
        for footprint in (None, [], "source-hash", 1, {}, {"runtime.py": None}):
            with self.subTest(footprint=footprint):
                context, _, index, _ = EffectQualifierTests().cache()
                index["receipt_contexts"]["a"]["source_sha256"] = footprint
                self.assertIsNone(
                    reusable_case(
                        index,
                        context,
                        {"runtime.py": "runtime-sha"},
                        "candidate",
                        lambda *args: self.fail(
                            "Malformed cache must not load a receipt"
                        ),
                    )
                )
        context, _, index, _ = EffectQualifierTests().cache()
        del index["receipt_contexts"]["a"]["source_sha256"]
        self.assertIsNone(
            reusable_case(
                index,
                context,
                {"runtime.py": "runtime-sha"},
                "candidate",
                lambda *args: self.fail("Missing footprint must not load a receipt"),
            )
        )


class EffectQualifierResumeTests(unittest.TestCase):
    def test_resume_requires_exact_source_candidate_and_native_identity(self):
        from qualify_monster_effect_work import resume_cases

        context = dict(reference=1, actor_level=3, spell_id=7, spell_level=2)
        document = dict(
            schema="monster-effect-work-qualification-v1",
            sources_stable=True,
            candidate_unchanged=True,
            candidate_manifest_sha256="candidate",
            source_sha256_before={"runtime": "same"},
            source_sha256_after={"runtime": "same"},
            cases=[
                dict(
                    context=context,
                    raw_case=dict(level=3, spell_id=7, spell_level=2, status="pending"),
                )
            ],
        )
        self.assertEqual(
            resume_cases(document, {"runtime": "same"}, "candidate")[(1, 3, 7, 2)][1], 0
        )
        with self.assertRaises(ValueError):
            resume_cases(document, {"runtime": "changed"}, "candidate")
        with self.assertRaises(ValueError):
            resume_cases(document, {"runtime": "same"}, "changed-candidate")
        document["cases"][0]["raw_case"]["spell_level"] = 3
        with self.assertRaises(ValueError):
            resume_cases(document, {"runtime": "same"}, "candidate")


class EffectQualifierDependencyTests(unittest.TestCase):
    def test_transitive_nested_fixture_imports_are_pinned_unrelated_tools_are_excluded(
        self,
    ):
        import tempfile
        from qualify_monster_effect_work import tool_dependency_paths

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = root / "server/tools"
            tools.mkdir(parents=True)
            (tools / "validate_monster_spell_activation.py").write_text(
                "from passive_helper import proof\n"
            )
            (tools / "passive_helper.py").write_text(
                "def proof():\n    from geometry_helper import geometry\n"
            )
            (tools / "geometry_helper.py").write_text("geometry = 1\n")
            (tools / "unrelated_index_builder.py").write_text("unrelated = 1\n")
            self.assertEqual(
                {p.stem for p in tool_dependency_paths(root)},
                {
                    "validate_monster_spell_activation",
                    "passive_helper",
                    "geometry_helper",
                },
            )


if __name__ == "__main__":
    unittest.main()
