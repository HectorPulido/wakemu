"""Full Ready fork semantics and paired performance stay in one bounded worker."""
import json
import os
from pathlib import Path
import unittest


class NativeRuntimePAMemoTests(unittest.TestCase):
    def test_full_ready_paired_forks_private_pa_aliases_hp_hupper_and_copied_fallback(
        self,
    ):
        from tools.benchmark_native_runtime_fork import run

        manifest = os.environ.get("WAKFU_FORK_PERFORMANCE_MANIFEST")
        before = os.environ.get("WAKFU_FORK_BEFORE_SOURCE")
        if not manifest or not before:
            raise RuntimeError(
                "Pinned native full Ready source and exact before Oracle required"
            )
        result = run(manifest, before)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["full_class_ready_qualified"])
        self.assertEqual(result["samples_per_variant"], 7)
        self.assertTrue(all(result["correctness"].values()))
        output = os.environ.get("WAKFU_FORK_PERFORMANCE_RECEIPT")
        if output:
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, indent=2) + "\n")
        print(
            "native_full_ready_fork_measurement " + json.dumps(result["measurements"]),
            flush=True,
        )
