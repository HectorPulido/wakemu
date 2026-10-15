import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import stage_native_callback_recovery as staging


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class StagedCatalog:
    def __init__(self, manifest, *, extra_identity=False, mutated_existing=False):
        self.manifest = manifest
        self.extra_identity = extra_identity
        self.mutated_existing = mutated_existing
        self.queries = []

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        if "SELECT path,sha256,source_bytes FROM native_catalog_documents" in sql:
            return Result(
                sorted(tuple(row) for row in self.manifest["candidate_documents"])
            )
        if "IS DISTINCT FROM" in sql:
            return Result([(1 if self.mutated_existing else 0,)])
        if "b.record_key IS NULL" in sql:
            name, collection = params[2], params[3]
            additions = {
                staging.NPC: {"101"},
                staging.CELLS: {"202"},
                staging.PROFILES[0]: {"2"},
                staging.PROFILES[1]: {"2"},
            }[name]
            if self.extra_identity:
                additions = additions | {"unexpected"}
            return Result((identity,) for identity in additions)
        if "activation_policy" in sql:
            return Result([(1883,)])
        raise AssertionError(f"Unexpected staged catalog query: {sql}")


class StagingConnection:
    def __init__(self):
        self.transactions = []

    class Transaction:
        def __init__(self, owner):
            self.owner = owner

        def __enter__(self):
            self.owner.transactions.append("entered")
            return self

        def __exit__(self, exc_type, exc, traceback):
            self.owner.transactions.append("rolled_back" if exc_type else "committed")
            return False

    def transaction(self):
        return self.Transaction(self)


class NativeCallbackRecoveryToolTests(unittest.TestCase):
    def test_object_start_and_insertion_ignore_nested_and_escaped_effects_text(self):
        base = (
            b'{"metadata":{"effects":{"nested":1},"text":"escaped \\" '
            b'{ effects: not-a-key }"},"effects":{"old":{"value":"}\\"{"}},'
            b'"tail":true}'
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, candidate = root / "base.json", root / "candidate.json"
            source.write_bytes(base)
            offset = staging.object_start(source, "effects")
            self.assertEqual(base[offset - 1 : offset], b"{")
            insertion = staging.insert_effects(
                source, candidate, {"new": {"text": 'escaped " brace }'}}
            )
            decoded = json.loads(candidate.read_bytes())
            self.assertEqual(
                decoded["effects"],
                {"new": {"text": 'escaped " brace }'}, "old": {"value": '}"{'}},
            )
            staging.verify_preserved_bytes(source, candidate, insertion)

    def test_byte_preservation_rejects_tampered_prefix_and_insertion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, candidate = root / "base.json", root / "candidate.json"
            base.write_bytes(b'{"effects":{"old":1},"tail":"keep"}')
            insertion = staging.insert_effects(base, candidate, {"added": {"value": 2}})
            original = candidate.read_bytes()
            candidate.write_bytes(b"!" + original[1:])
            with self.assertRaisesRegex(ValueError, "Existing NPC document bytes"):
                staging.verify_preserved_bytes(base, candidate, insertion)
            changed = bytearray(original)
            changed[insertion["offset"]] ^= 1
            candidate.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "Callback insertion changed"):
                staging.verify_preserved_bytes(base, candidate, insertion)

    def _package(self, root):
        base_dir = root / "base"
        base_dir.mkdir()
        base_docs = {
            staging.NPC: {
                "effects": {"old": {}},
                "activation_policy": {"enabled": 1883},
            },
            staging.CELLS: {
                "schema": "native-eYk-class-cell-group-v1",
                "effects": {
                    "201": {
                        "criterion_present": True,
                        "area_class": "eYk",
                        "raw_parameters": [1],
                    }
                },
                "npc_dependency_exports": [],
            },
            staging.PROFILES[0]: {
                "profiles": {"1": {"abilities": []}},
                "npc_dependency_exports": [],
            },
            staging.PROFILES[1]: {
                "profiles": {"1": {"fight_properties": []}},
                "npc_dependency_exports": [],
            },
        }
        candidates = {
            staging.NPC: {
                "effects": {"old": {}, "101": {}},
                "activation_policy": {"enabled": 1883},
            },
            staging.CELLS: {
                **base_docs[staging.CELLS],
                "effects": {
                    **base_docs[staging.CELLS]["effects"],
                    "202": {
                        "criterion_present": False,
                        "area_class": "eYk",
                        "raw_parameters": [],
                    },
                },
                "npc_dependency_exports": [
                    {"original_inputs_stable": True, "effect_ids": [202]}
                ],
            },
            staging.PROFILES[0]: {
                "profiles": {"1": {"abilities": []}, "2": {"abilities": [7]}},
                "npc_dependency_exports": [{"original_inputs_stable": True}],
            },
            staging.PROFILES[1]: {
                "profiles": {
                    "1": {"fight_properties": []},
                    "2": {"initial_state_triples": []},
                },
                "npc_dependency_exports": [{"original_inputs_stable": True}],
            },
        }
        hashes, rows = {}, []
        for name in staging.PATHS:
            base_path, candidate_path = base_dir / name, root / name
            base_path.write_text(json.dumps(base_docs[name]), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidates[name]), encoding="utf-8")
            checksum = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
            hashes[name] = checksum
            rows.append([name, checksum, candidate_path.stat().st_size])
        rows.sort()
        manifest = {
            "schema": "native-callback-recovery-package-v1",
            "base_revision": "base-revision",
            "candidate_revision": "candidate-revision",
            "candidate_documents": rows,
            "effect_ids": [101],
            "expected_enabled_count": 1883,
            "delta": {"executable_effects": 1, "cell_groups": 1, "summon_profiles": 2},
        }
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def test_verify_staged_checks_exact_additive_deltas(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._package(root)
            connection = StagedCatalog(manifest)
            result = staging.verify_staged(connection, root)
            self.assertEqual(result["result"], "PASS")
            self.assertEqual(result["enabled_monsters"], 1883)
            self.assertTrue(result["existing_indexed_rows_preserved"])
            self.assertEqual(
                sum("b.record_key IS NULL" in sql for sql, _ in connection.queries), 4
            )

    def test_verify_staged_rejects_unreviewed_identity_delta(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._package(root)
            with self.assertRaisesRegex(ValueError, "identity delta mismatch"):
                staging.verify_staged(
                    StagedCatalog(manifest, extra_identity=True), root
                )

    def test_verify_staged_rejects_mutated_existing_indexed_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._package(root)
            with self.assertRaisesRegex(ValueError, "changed existing indexed rows"):
                staging.verify_staged(
                    StagedCatalog(manifest, mutated_existing=True), root
                )

    def test_stage_wrapper_requires_expected_revision_and_runs_indexed_guard(self):
        for stage_revision, verify_error in (
            ("candidate-revision", False),
            ("wrong-revision", False),
            ("candidate-revision", True),
        ):
            with self.subTest(stage_revision=stage_revision, verify_error=verify_error):
                connection = StagingConnection()
                with tempfile.TemporaryDirectory() as directory:
                    verify_staged = SimpleNamespace(called=False)

                    def staged_guard(_connection, _directory):
                        verify_staged.called = True
                        if verify_error:
                            raise ValueError("indexed identity delta mismatch")
                        return {"result": "PASS"}

                    stage_release = lambda *_args, **_kwargs: {
                        "revision": stage_revision,
                        "staged": True,
                        "already_staged": stage_revision == "candidate-revision",
                    }
                    fake_module = SimpleNamespace(stage=stage_release)
                    with patch.object(
                        staging,
                        "verify",
                        return_value={
                            "base_revision": "base-revision",
                            "candidate_revision": "candidate-revision",
                        },
                    ), patch.object(
                        staging, "verify_staged", side_effect=staged_guard
                    ), patch.dict(
                        sys.modules, {"stage_spell_resource_cost_catalog": fake_module}
                    ):
                        if stage_revision != "candidate-revision" or verify_error:
                            with self.assertRaises(ValueError):
                                staging.stage(connection, directory)
                            self.assertEqual(connection.transactions[-1], "rolled_back")
                        else:
                            result = staging.stage(connection, directory)
                            self.assertEqual(
                                result["indexed_validation"], {"result": "PASS"}
                            )
                            self.assertTrue(result["already_staged"])
                            self.assertTrue(verify_staged.called)
                            self.assertEqual(connection.transactions[-1], "committed")


if __name__ == "__main__":
    unittest.main()
