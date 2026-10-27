"""Compare real old/new casting definitions over the same bounded publication."""
import ast
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
from unittest.mock import patch

from test_native_catalog_document_getters import NativeCatalogDocumentGetterTests


class NativeCastingProjectionTests(NativeCatalogDocumentGetterTests):
    def test_original_selected_levels_keep_dynamic_costs_and_unknown_guards(self):
        self._publication_check = self._exercise_projection
        self.test_original_json_getters_parent_guards_and_bounded_ordered_headers()

    def _exercise_projection(self, requests, publication, published_rows):
        from wakfu_server import combat_native_spell_casting as casting
        from wakfu_server import combat_spell_resource_costs as resources
        from wakfu_server.combat_conditions import (
            ConditionActor,
            ConditionContext,
            UnknownCondition,
        )
        from wakfu_server.combat_class_initialization import level_zero_catalog

        path = Path(".runtime/native-casting-selected-level/original-records.json")
        raw = path.read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "a58ac4c2d6692d5bdffbc0cfb6a7ac6f542cc180af8f9aedfcb8f5455b910286",
        )
        source = json.loads(raw)
        definitions = {
            r["key"]: r["payload"]
            for r in source["records"]
            if r["path"] == "native-spell-casting.json"
        }
        resource_records = {
            r["key"]: r["payload"]
            for r in source["records"]
            if r["path"] == "native-spell-resource-costs.json"
        }
        collection = "native-spell-casting.json/spells"
        published_rows[collection].clear()
        published_rows[collection].update(deepcopy(definitions))
        publication["collections"][collection]["count"] = len(definitions)
        publication["collections"][collection]["ordered_keys_sha256"] = hashlib.sha256(
            json.dumps(list(definitions)).encode()
        ).hexdigest()
        entry = publication["raw_documents"]["native-spell-casting.json"][
            "collections"
        ]["spells"]
        entry["count"] = publication["collections"][collection]["count"]
        entry["ordered_keys_sha256"] = publication["collections"][collection][
            "ordered_keys_sha256"
        ]
        casting.catalog.cache_clear()
        casting.selected_casting_projection.cache_clear()
        self.addCleanup(casting.catalog.cache_clear)
        self.addCleanup(casting.selected_casting_projection.cache_clear)
        before = Path(".runtime/native-casting-selected-level/before.py").read_bytes()
        self.assertEqual(
            hashlib.sha256(before).hexdigest(),
            "cc0c8df238517aa366261cf9f9c75326f760966518e29c266ef3ec68c0df2b23",
        )
        node = next(
            n
            for n in ast.parse(before).body
            if isinstance(n, ast.FunctionDef) and n.name == "definition"
        )
        node.name = "legacy_definition"
        namespace = dict(vars(casting))
        # Bind the exact same live source getter into the archived function.
        namespace["catalog"] = casting.catalog
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                "<actual archived casting definition>",
                "exec",
            ),
            namespace,
        )
        legacy = namespace["legacy_definition"]
        inventory = {"quantity": 1}
        actor = ConditionActor(
            state_ids=frozenset(),
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            effective_level=130,
            is_player=True,
        )
        context = ConditionContext(
            {"caster": actor}, item_quantity_query=lambda keys: inventory["quantity"]
        )
        active = replace(
            context, actors={"caster": replace(actor, state_ids=frozenset({702}))}
        )
        deck = replace(
            active,
            actors={
                "caster": replace(
                    active.actors["caster"], deck_spell_ids=frozenset({8274})
                )
            },
        )
        modifiers = {1: 0, 8: 0, 10: 0}
        rows = []

        def compare(reference, level, ctx, mods, **kwargs):
            expected = legacy(reference, level, ctx, mods, **kwargs)
            actual = casting.definition(reference, level, ctx, mods, **kwargs)
            self.assertEqual(actual, expected)
            return actual

        generation_counter = 1

        def change_generation():
            nonlocal generation_counter
            generation_counter += 1
            generation = format(generation_counter, "064x")
            publication.update(generation=generation, manifest_sha256=generation)
            casting.catalog.cache_clear()

        with patch.object(resources, "catalog", return_value=resource_records):
            base = compare(5623, 130, context, {})
            conditional = compare(5623, 130, active, {})
            alternative = compare(5623, 130, deck, {})
            self.assertEqual(
                base["native_casting_selection"]["selected_origin"], "baseline"
            )
            self.assertEqual(
                conditional["native_casting_selection"]["selected_origin"],
                "conditional",
            )
            self.assertNotEqual(base["costs"], conditional["costs"])
            self.assertNotEqual(
                conditional["native_casting_selection"]["matched_rules"],
                alternative["native_casting_selection"]["matched_rules"],
            )
            inventory["quantity"] = 0
            self.assertEqual(compare(5623, 130, active, {})["costs"], base["costs"])
            inventory["quantity"] = 1
            first = compare(6967, 130, context, modifiers)
            modifiers[1] = -1
            second = compare(6967, 130, context, modifiers)
            self.assertEqual(second["costs"]["ap"], max(0, first["costs"]["ap"] - 1))
            # A cached projection must still re-resolve the complete cost table.
            wrong_resources = deepcopy(resource_records)
            wrong_resources["6967"]["baseline"]["resources"]["2"][130] += 1
            with patch.object(resources, "catalog", return_value=wrong_resources):
                for fn in (legacy, casting.definition):
                    with self.assertRaisesRegex(UnknownCondition, "disagree"):
                        fn(6967, 130, context, {})
            unknown = replace(active, item_quantity_query=None)
            for fn in (legacy, casting.definition):
                with self.assertRaises(UnknownCondition):
                    fn(5623, 130, unknown, {})

            # Controlled malformed source variants preserve unknown/ambiguity.
            record = deepcopy(definitions["5623"])
            record["conditional"][0]["criteria"] = "True"
            record["conditional"][1]["criteria"] = "True"
            record["conditional"][1]["levels"][129][0] += 1
            published_rows[collection]["5623"] = record
            change_generation()
            for fn in (legacy, casting.definition):
                with self.assertRaisesRegex(UnknownCondition, "Ambiguous"):
                    fn(5623, 130, context, {}, calculate_costs=False)
            malformed_late = deepcopy(definitions["5623"])
            malformed_late["conditional"][0][
                "criteria"
            ] = "UnsupportedNativeCriterion()"
            del malformed_late["conditional"][1]["levels"]
            published_rows[collection]["5623"] = malformed_late
            change_generation()
            for fn in (legacy, casting.definition):
                with self.assertRaises(UnknownCondition):
                    fn(5623, 130, context, {}, calculate_costs=False)
            with patch.object(
                casting, "catalog", return_value={"5623": malformed_late}
            ):
                for fn in (legacy, casting.definition):
                    with self.assertRaises(UnknownCondition):
                        fn(5623, 130, context, {}, calculate_costs=False)
            equivalent = deepcopy(definitions["5623"])
            equivalent["conditional"] = equivalent["conditional"][:1]
            rule = equivalent["conditional"][0]
            rule["criteria"] = "UnsupportedNativeCriterion()"
            rule["levels"][129] = list(equivalent["costs"][129])
            rule["ranges"][129] = list(equivalent["levels"][129][:2])
            for key in casting._CASTING_FLAGS:
                rule[key] = equivalent[key]
            published_rows[collection]["5623"] = equivalent
            change_generation()
            result = compare(5623, 130, context, {}, calculate_costs=False)
            self.assertEqual(
                result["native_casting_selection"]["unknown_equivalent_rule_indices"],
                [0],
            )
            published_rows[collection]["5623"] = deepcopy(definitions["5623"])
            change_generation()
            # Caller-injected dictionaries remain uncached and observe changes.
            private = deepcopy(definitions)
            with patch.object(casting, "catalog", return_value=private):
                namespace["catalog"] = lambda: private
                private["7962"]["levels"][0][0] = 2
                self.assertEqual(
                    compare(7962, 1, context, {}, calculate_costs=False)["minimum"], 2
                )
                private["7962"]["levels"][0][0] = 3
                self.assertEqual(
                    compare(7962, 1, context, {}, calculate_costs=False)["minimum"], 3
                )
            namespace["catalog"] = casting.catalog
            zero = deepcopy(definitions["7962"])
            zero["levels"] = zero["levels"][:1]
            zero["costs"] = zero["costs"][:1]
            zero["conditional"] = []
            with patch(
                "wakfu_server.combat_class_initialization.level_zero_catalog",
                return_value={"casting": {"7962": zero}},
            ):
                result = compare(7962, 0, context, {}, calculate_costs=False)
                self.assertEqual(result["native_casting_selection"]["table_index"], 0)
            for level in (-1, True):
                for fn in (legacy, casting.definition):
                    with self.assertRaises(ValueError):
                        fn(7962, level, context, {}, calculate_costs=False)

            modifiers = {1: 0, 8: 0, 10: 0}
            casting.selected_casting_projection.cache_clear()
            for mode in ("cold", "warm"):
                count_before = len(requests)
                started = time.perf_counter_ns()
                results = [
                    casting.definition(6967, 130, context, modifiers) for _ in range(6)
                ]
                elapsed = time.perf_counter_ns() - started
                decodes = sum(
                    name == collection for name, key in requests[count_before:]
                )
                self.assertEqual(decodes, 1 if mode == "cold" else 0)
                self.assertTrue(all(value == results[0] for value in results))
                rows.append(
                    dict(mode=mode, calls=6, decodes=decodes, elapsed_ns=elapsed)
                )
            samples = []
            for pair in range(7):
                for mode in (
                    ("before", "after") if pair % 2 == 0 else ("after", "before")
                ):
                    fn = legacy if mode == "before" else casting.definition
                    started = time.perf_counter_ns()
                    results = [fn(6967, 130, context, modifiers) for _ in range(6)]
                    elapsed = time.perf_counter_ns() - started
                    self.assertTrue(all(value == results[0] for value in results))
                    samples.append(
                        dict(pair=pair, mode=mode, calls=6, elapsed_ns=elapsed)
                    )
            with patch.object(casting, "_SELECTED_MAX_ENTRIES", 2):
                casting.selected_casting_projection.cache_clear()
                for level in (1, 2, 3):
                    casting.selected_casting_projection(6967, level)
                self.assertEqual(
                    casting.selected_casting_projection.cache_info()["entries"], 2
                )
            with patch.object(casting, "_SELECTED_MAX_BYTES", 1):
                casting.selected_casting_projection.cache_clear()
                casting.selected_casting_projection(6967, 130)
                self.assertEqual(
                    casting.selected_casting_projection.cache_info()["entries"], 0
                )
            output = os.environ.get("WAKFU_CASTING_PROJECTION_RECEIPT")
            if output:
                summary = {
                    mode: statistics.median(
                        r["elapsed_ns"] / r["calls"]
                        for r in samples
                        if r["mode"] == mode
                    )
                    for mode in ("before", "after")
                }
                Path(output).write_text(
                    json.dumps(
                        dict(
                            status="PASS",
                            source_sha256=hashlib.sha256(raw).hexdigest(),
                            decode_samples=rows,
                            paired_samples=samples,
                            median_wall_ns_per_definition=summary,
                            scope="Same original finite casting/resource rows, archived old/current definition, seven alternating six-call batches; not full combat latency.",
                        ),
                        indent=2,
                    )
                    + "\n"
                )
