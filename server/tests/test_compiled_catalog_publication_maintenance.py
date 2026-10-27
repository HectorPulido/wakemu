"""Publication maintenance ordering without compiling or loading native catalogs."""
from contextlib import contextmanager
import hashlib
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from tools import publish_compiled_combat_catalog as publisher


class CompiledCatalogMaintenanceTests(unittest.TestCase):
    def test_new_publication_maintains_statistics_before_commit_and_reuse_skips_it(
        self,
    ):
        for reused in (False, True):
            with self.subTest(reused=reused):
                events = []
                raw = b"published"
                generation = hashlib.sha256(raw).hexdigest()
                identity = dict.fromkeys(
                    (
                        "policy",
                        "source_revision",
                        "source_inventory_sha256",
                        "compiler_contract_sha256",
                        "config_sha256",
                    ),
                    "pin",
                )
                row = (
                    dict(generation=generation, manifest_raw=raw, complete=True)
                    if reused
                    else None
                )

                class Connection:
                    def execute(self, query, parameters=None):
                        if query.startswith("ANALYZE "):
                            events.append("analyze")
                        return SimpleNamespace(fetchone=lambda: row)

                class Database:
                    @contextmanager
                    def connection(self):
                        events.append("begin")
                        try:
                            yield Connection()
                        except BaseException:
                            events.append("rollback")
                            raise
                        else:
                            events.append("commit")

                native = ModuleType("wakfu_server.native_catalog")
                native._database = lambda: Database()
                backend = ModuleType("wakfu_server.native_compiled_catalog")
                backend.expected_publication_identity = lambda: identity
                backend.canonical_bytes = publisher.ordered_bytes
                backend._compiler_source_bytes = SimpleNamespace(
                    cache_clear=lambda: None
                )
                backend.warm_publication = lambda value: events.append("warm")
                package = ModuleType("wakfu_server")
                package.native_catalog = native
                modules = {
                    "wakfu_server": package,
                    "wakfu_server.native_catalog": native,
                    "wakfu_server.native_compiled_catalog": backend,
                }

                def publish(*args, identity_check=None):
                    identity_check()
                    events.extend(("publish", "analyze", "seal"))
                    return generation

                spool = SimpleNamespace(
                    db=SimpleNamespace(close=lambda: events.append("close_spool"))
                )
                with patch.dict(sys.modules, modules), patch.dict(
                    "os.environ", {}, clear=False
                ), patch.object(
                    publisher, "PublicationSpool", return_value=spool
                ), patch.object(
                    publisher, "compile_manifest", return_value={}
                ), patch.object(
                    publisher, "publish", side_effect=publish
                ), patch.object(
                    publisher, "log"
                ):
                    self.assertEqual(
                        publisher.ensure_publication(warm_redis=True), generation
                    )
                self.assertEqual(
                    events,
                    ["begin", "commit", "warm"]
                    if reused
                    else [
                        "begin",
                        "publish",
                        "analyze",
                        "seal",
                        "close_spool",
                        "commit",
                        "warm",
                    ],
                )


class PublishStatisticsBoundaryTests(unittest.TestCase):
    def test_real_publish_analyzes_once_before_sealing_and_failure_never_seals(self):
        import json

        manifest = dict.fromkeys(
            (
                "policy",
                "source_revision",
                "source_inventory_sha256",
                "compiler_contract_sha256",
                "config_sha256",
            ),
            "0" * 64,
        )
        spool = SimpleNamespace(
            collections={}, keys={}, db=SimpleNamespace(execute=lambda _: [])
        )
        for fail in (False, True):
            with self.subTest(fail=fail):
                events = []
                db = MagicMock()

                def execute(sql, params=None):
                    if sql.startswith("SELECT count"):
                        events.append("count")
                    elif sql.startswith("ANALYZE"):
                        events.append("analyze")
                        if fail:
                            raise RuntimeError("Statistics collection failed")
                    elif sql.startswith("UPDATE native_compiled_catalog_releases"):
                        events.append("seal")
                    return SimpleNamespace(fetchone=lambda: {"n": 0})

                db.execute.side_effect = execute
                call = lambda: publisher.publish(
                    db,
                    spool,
                    manifest,
                    lambda value: json.dumps(value, sort_keys=True).encode(),
                    identity_check=lambda: events.append("identity"),
                )
                with patch.object(publisher, "log"):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, "Statistics"):
                            call()
                    else:
                        call()
                self.assertEqual(
                    events,
                    ["count", "identity", "analyze"] + ([] if fail else ["seal"]),
                )
