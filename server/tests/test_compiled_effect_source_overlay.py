"""Paired bounded-original source compilation, not a deployed cold-start claim."""
from copy import deepcopy
import gc
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
import tracemalloc
import unittest


class CompiledEffectSourceOverlayTests(unittest.TestCase):
    def test_original_definitions_order_identity_point_areas_and_paired_allocation(
        self,
    ):
        from tools.sublimation_bounded_census import BoundedDataset
        from wakfu_server.combat_static_catalogs import CompiledEffects
        from wakfu_server.combat_effect_runtime import _merge_effects

        path = os.environ.get("WAKFU_PERFORMANCE_MANIFEST")
        if not path:
            raise RuntimeError(
                "Explicit bounded original performance manifest required"
            )
        dataset = BoundedDataset(path)
        dataset.install_catalog_backend()
        original = dataset.closure["effects"]
        state_catalog = dataset.states
        # Preserve actual original rows. Separate a representative source delta,
        # including state/source overlap and genuine point-area metadata.
        references = list(original)
        self.assertEqual(len(references), 2036)
        delta_ids = set(references[-96:])
        point_ids = [
            key
            for key, row in original.items()
            if row.get("area_class") in ("anE", "anJ")
        ]
        self.assertTrue(point_ids)
        delta_ids.add(point_ids[0])
        state_overlap = next(
            key for key in references if key in state_catalog["effects"]
        )
        delta_ids.add(state_overlap)
        base_sources = {
            key: row for key, row in original.items() if key not in delta_ids
        }
        additions = {key: row for key, row in original.items() if key in delta_ids}
        base = CompiledEffects(base_sources, state_catalog)
        full_sources = _merge_effects(base_sources, {"effects": additions})
        legacy = CompiledEffects(full_sources, state_catalog)
        current = base.with_effect_sources(additions)
        self.assertEqual(tuple(current.effects), tuple(legacy.effects))
        self.assertEqual(tuple(current.source_effects), tuple(legacy.source_effects))
        self.assertEqual(dict(current.effects), dict(legacy.effects))
        self.assertIs(current.source_states, base.source_states)
        self.assertIs(current.effects._base, base.effects)
        for key, row in base_sources.items():
            self.assertIs(current.source_effects[key], row)
            self.assertIs(current.effects[key], base.effects[key])
        self.assertEqual(
            current.effects[point_ids[0]]["native_area_points"],
            legacy.effects[point_ids[0]]["native_area_points"],
        )
        self.assertIs(deepcopy(current.effects), current.effects)
        self.assertIs(deepcopy(current.source_effects), current.source_effects)
        with self.assertRaises(TypeError):
            current.effects[references[0]] = {}
        with self.assertRaises(TypeError):
            current.effects[references[0]]["effect_class"] = 999
        # Existing source rows retain the original identity and annotations.
        existing = next(iter(base_sources))
        equivalent = dict(
            base_sources[existing], fixture_annotation="not a native identity"
        )
        self.assertIs(base.with_effect_sources({existing: equivalent}), base)
        for key in (existing, state_overlap):
            bad = deepcopy(original[key])
            bad["criteria"] = "False"
            with self.subTest(collision=key):
                with self.assertRaisesRegex(ValueError, "Conflicting native"):
                    base.with_effect_sources({key: bad})
        self.assertEqual(dict(base.source_effects), base_sources)
        self.assertIs(base.with_effect_sources({}), base)
        # The real NPC path passes a full source merge; the weapon path passes
        # only additions. Both must preserve exactly the same compiled graph.
        self.assertEqual(
            dict(base.with_effect_sources(full_sources).effects), dict(legacy.effects)
        )
        self.assertEqual(
            tuple(base.with_effect_sources(full_sources).effects), tuple(legacy.effects)
        )
        del current, legacy
        gc.collect()

        def legacy_build():
            return CompiledEffects(
                _merge_effects(base_sources, {"effects": additions}), state_catalog
            )

        def overlay_build():
            return base.with_effect_sources(additions)

        observations = {"legacy_reference": [], "source_overlay": []}
        for repeat in range(7):
            pairs = (
                ("legacy_reference", legacy_build),
                ("source_overlay", overlay_build),
            )
            if repeat % 2:
                pairs = tuple(reversed(pairs))
            for name, build in pairs:
                gc.collect()
                tracemalloc.start()
                before = time.perf_counter_ns()
                result = build()
                elapsed = time.perf_counter_ns() - before
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                observations[name].append(
                    dict(elapsed_ns=elapsed, peak_traced_bytes=peak)
                )
                self.assertEqual(
                    len(result.effects),
                    len(base.effects)
                    + sum(key not in base.effects for key in additions),
                )
                del result
        summary = {
            name: dict(
                median_elapsed_ns=statistics.median(row["elapsed_ns"] for row in rows),
                median_peak_traced_bytes=statistics.median(
                    row["peak_traced_bytes"] for row in rows
                ),
                samples=rows,
            )
            for name, rows in observations.items()
        }
        self.assertLess(
            summary["source_overlay"]["median_peak_traced_bytes"],
            summary["legacy_reference"]["median_peak_traced_bytes"],
        )
        receipt = dict(
            schema="wakemu-compiled-source-overlay-paired-benchmark-v1",
            scope="Paired original bounded graph microbenchmark, not old deployed cold start",
            original_source_effects=len(original),
            original_states=len(state_catalog["states"]),
            added_source_effects=len(additions),
            manifest=path,
            manifest_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            source_sha256=hashlib.sha256(
                (
                    Path(__file__).resolve().parents[1]
                    / "wakfu_server/combat/combat_static_catalogs.py"
                ).read_bytes()
            ).hexdigest(),
            measurements=summary,
        )
        output = os.environ.get("WAKFU_PERFORMANCE_RECEIPT")
        if output:
            target = Path(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(receipt, indent=2) + "\n")
        print(
            "bounded_source_overlay_measurement "
            + json.dumps(
                {
                    name: {key: value for key, value in row.items() if key != "samples"}
                    for name, row in summary.items()
                }
            ),
            flush=True,
        )
