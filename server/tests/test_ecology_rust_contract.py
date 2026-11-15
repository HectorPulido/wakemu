"""Golden parity checks for the isolated Rust ecology contract console."""

import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = (
    ROOT
    / "server"
    / "rust-services"
    / "crates"
    / "ecology-service"
    / "tests"
    / "fixtures"
)
VECTORS = FIXTURES / "python-contract-v1.jsonl"
NATIVE_VECTORS = FIXTURES / "native-owned-instance-v1.jsonl"


def rust_request(vector):
    operation, value = vector["operation"], vector["value"]
    if operation == "proposal":
        return {"operation": operation, **value}
    if operation == "filter_failed":
        return {
            "operation": operation,
            "value": value["row"],
            "exhausted": value["exhausted"],
        }
    if operation in {"merge_bulk", "refresh_stale"}:
        return {"operation": operation, **value}
    return {"operation": operation, "value": value}


class EcologyRustContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not VECTORS.is_file():
            raise unittest.SkipTest(f"Rust ecology vectors are missing: {VECTORS}")
        cls.vectors = [json.loads(line) for line in VECTORS.read_text().splitlines()]
        if not cls.vectors:
            raise AssertionError("Rust ecology golden vector file is empty")

    def test_rust_contract_matches_frozen_python_golden_vectors(self):
        binary = os.environ.get("WAKFU_ECOLOGY_CONTRACT_BIN")
        if not binary:
            self.skipTest(
                "Set WAKFU_ECOLOGY_CONTRACT_BIN to the candidate contract binary"
            )
        binary_path = Path(binary).expanduser().resolve()
        if not binary_path.is_file():
            self.fail(f"Ecology contract binary does not exist: {binary_path}")
        requests = [rust_request(row) for row in self.vectors]
        completed = subprocess.run(
            [str(binary_path)],
            input="".join(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                for row in requests
            ),
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        lines = completed.stdout.splitlines()
        self.assertEqual(len(lines), len(self.vectors), completed.stderr)
        for vector, line in zip(self.vectors, lines):
            with self.subTest(vector=vector["name"]):
                response = json.loads(line)
                self.assertEqual(set(response), {"result"})
                self.assertEqual(response["result"], vector["expected"])

    def test_readonly_native_probe_matches_frozen_constructor_outputs(self):
        binary = os.environ.get("WAKFU_ECOLOGY_NATIVE_PROBE_BIN")
        if not binary:
            self.skipTest("Set WAKFU_ECOLOGY_NATIVE_PROBE_BIN to the read-only probe")
        if not NATIVE_VECTORS.is_file():
            self.fail(
                f"World Python native constructor vectors are missing: {NATIVE_VECTORS}"
            )
        vectors = [json.loads(line) for line in NATIVE_VECTORS.read_text().splitlines()]
        requests = [
            {"operation": "owned_instance", **vector["request"]} for vector in vectors
        ]
        completed = subprocess.run(
            [str(Path(binary).expanduser().resolve())],
            input="".join(
                json.dumps(row, separators=(",", ":")) + "\n" for row in requests
            ),
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        lines = completed.stdout.splitlines()
        self.assertEqual(len(lines), len(vectors), completed.stderr)
        for vector, line in zip(vectors, lines):
            with self.subTest(
                reference=vector["request"]["ref"], level=vector["request"]["level"]
            ):
                response = json.loads(line)
                self.assertEqual(set(response), {"result"})
                self.assertEqual(response["result"], vector["expected"])


if __name__ == "__main__":
    unittest.main()
