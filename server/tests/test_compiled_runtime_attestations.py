"""Generation attestations cannot authorize unrelated source changes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import compiled_runtime_attestations as attest


PATH = "wakfu_server/combat/combat_placement_policy.py"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Database:
    def __init__(self, release):
        self.release = release
        self.attestations = []

    def execute(self, sql, params):
        if sql.startswith("SELECT generation,manifest_raw"):
            return Result(
                [self.release] if params[0] == self.release["generation"] else []
            )
        if sql.startswith("INSERT INTO native_compiled_runtime_projections"):
            generation, path, source, policy, digest = params
            self.attestations.append(
                dict(
                    generation=generation,
                    source_path=path,
                    source_sha256=source,
                    policy_sha256=policy,
                    projection_sha256=digest,
                )
            )
            return Result([])
        if sql.startswith("SELECT source_path,source_sha256"):
            generation, policy, paths = params
            return Result(
                [
                    r
                    for r in self.attestations
                    if r["generation"] == generation
                    and r["policy_sha256"] == policy
                    and r["source_path"] in paths
                ]
            )
        raise AssertionError(sql)


class RuntimeAttestationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / PATH
        self.path.parent.mkdir(parents=True)
        self.old = b"constant = 1\ndef _arena(x):\n return x\ndef freeze(value):\n return value\ndef compiler():\n return constant\n"
        self.path.write_bytes(self.old)
        self.old_sha = hashlib.sha256(self.old).hexdigest()
        self.manifest = dict(
            policy="p",
            source_revision="r",
            source_inventory_sha256="i",
            compiler_contract_sha256="c",
            config_sha256="g",
            compiler_sources={PATH: self.old_sha},
            collections={},
        )
        raw = canonical(self.manifest)
        self.generation = hashlib.sha256(raw).hexdigest()
        self.db = Database(
            dict(
                generation=self.generation,
                manifest_raw=raw,
                manifest=self.manifest,
                complete=True,
            )
        )

    def _baseline(self):
        self.assertEqual(
            attest.record_exact_publication(
                self.db, self.generation, self.manifest, self.root, canonical
            ),
            1,
        )

    def _new_identity(self, content):
        self.path.write_bytes(content)
        return {
            **self.manifest,
            "compiler_sources": {PATH: hashlib.sha256(content).hexdigest()},
        }

    def test_verified_runtime_body_change_reuses_only_matching_attestation(self):
        self._baseline()
        current = self._new_identity(self.old.replace(b"return x\n", b"return x + 7\n"))
        self.assertEqual(
            attest.verified_unchanged_paths(
                self.db, self.generation, self.manifest, current, self.root
            ),
            {PATH},
        )
        self.db.attestations[0]["source_sha256"] = "0" * 64
        self.assertFalse(
            attest.verified_unchanged_paths(
                self.db, self.generation, self.manifest, current, self.root
            )
        )

    def test_relevant_or_unverified_changes_fall_back(self):
        self._baseline()
        for raw in (
            self.old.replace(b"constant = 1", b"constant = 2"),
            self.old.replace(b"_arena(x)", b"_arena(x, y=0)"),
            b"invalid (",
        ):
            current = self._new_identity(raw)
            self.assertFalse(
                attest.verified_unchanged_paths(
                    self.db, self.generation, self.manifest, current, self.root
                )
            )

    def test_baseline_requires_complete_matching_manifest_and_source(self):
        self.db.release["complete"] = False
        self.assertEqual(
            attest.record_exact_publication(
                self.db, self.generation, self.manifest, self.root, canonical
            ),
            0,
        )
        self.db.release["complete"] = True
        self.path.write_text("changed")
        self.assertEqual(
            attest.record_exact_publication(
                self.db, self.generation, self.manifest, self.root, canonical
            ),
            0,
        )
        self.assertFalse(self.db.attestations)


if __name__ == "__main__":
    unittest.main()
