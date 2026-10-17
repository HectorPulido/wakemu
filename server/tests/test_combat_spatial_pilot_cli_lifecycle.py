"""Short-lived native probe cleanup must not create owners or hide failures."""
from contextlib import redirect_stdout
from functools import lru_cache
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import combat_spatial_pilot_content_import as probe


class SpatialPilotCLILifecycleTests(unittest.TestCase):
    def factory(self, kind, calls, *, fail=False, pool_closes=True):
        pool = SimpleNamespace(closed=False)
        if kind == "redis":
            pool.disconnect = lambda: calls.append("redis.disconnect")

        def close():
            calls.append(kind + ".close")
            if fail:
                raise RuntimeError(kind + " close failed")
            if kind == "database" and pool_closes:
                pool.closed = True

        owner = SimpleNamespace(close=close, pool=pool, connection_pool=pool)

        @lru_cache(maxsize=1)
        def connect():
            calls.append(kind + ".connect")
            return owner

        return connect

    def test_empty_caches_do_not_open_new_connections(self):
        calls = []
        factories = tuple(
            (kind, self.factory(kind, calls)) for kind in ("database", "redis")
        )
        with patch("gc.freeze", side_effect=lambda: calls.append("freeze")):
            probe._finish_cli_assets(factories)
        self.assertEqual(calls, ["freeze"])
        self.assertTrue(
            all(factory.cache_info().currsize == 0 for _, factory in factories)
        )

    def test_all_existing_resources_close_before_freeze(self):
        calls = []
        factories = tuple(
            (kind, self.factory(kind, calls)) for kind in ("database", "redis")
        )
        for _, factory in factories:
            factory()
        calls.clear()
        with patch("gc.freeze", side_effect=lambda: calls.append("freeze")):
            probe._finish_cli_assets(factories)
        self.assertEqual(
            calls, ["database.close", "redis.close", "redis.disconnect", "freeze"]
        )

    def test_cleanup_failure_propagates_and_other_owner_still_closes(self):
        calls = []
        database = self.factory("database", calls, fail=True)
        redis = self.factory("redis", calls)
        database()
        redis()
        calls.clear()
        with patch("gc.freeze") as freeze:
            with self.assertRaises(ExceptionGroup) as raised:
                probe._finish_cli_assets((("database", database), ("redis", redis)))
        self.assertEqual(
            [str(error) for error in raised.exception.exceptions],
            ["database close failed"],
        )
        self.assertEqual(calls, ["database.close", "redis.close", "redis.disconnect"])
        freeze.assert_not_called()

    def test_failed_redis_close_still_disconnects_owned_pool(self):
        calls = []
        redis = self.factory("redis", calls, fail=True)
        redis()
        calls.clear()
        with patch("gc.freeze") as freeze:
            with self.assertRaises(ExceptionGroup) as raised:
                probe._finish_cli_assets((("redis", redis),))
        self.assertEqual(
            [str(error) for error in raised.exception.exceptions],
            ["redis close failed"],
        )
        self.assertEqual(calls, ["redis.close", "redis.disconnect"])
        freeze.assert_not_called()

    def test_unclosed_database_pool_blocks_freeze(self):
        calls = []
        database = self.factory("database", calls, pool_closes=False)
        database()
        with patch("gc.freeze") as freeze, self.assertRaises(ExceptionGroup):
            probe._finish_cli_assets((("database", database),))
        freeze.assert_not_called()

    def test_original_redis_owner_survives_overlay_factory_replacement(self):
        from wakfu_server import native_catalog

        calls = []
        database = self.factory("database", calls)
        redis = self.factory("redis", calls)
        redis()
        calls.clear()
        with patch.object(native_catalog, "_database", database), patch.object(
            native_catalog, "_redis", redis
        ):
            captured = probe._cli_asset_owner_factories()
            native_catalog._redis = lambda: self.fail(
                "Overlay must not construct a client"
            )
            with patch("gc.freeze"):
                probe._finish_cli_assets(captured)
        self.assertEqual(calls, ["redis.close", "redis.disconnect"])

    def test_main_finishes_successful_result_before_printing(self):
        calls = []
        arguments = SimpleNamespace(
            command="execute",
            candidate=Path("candidate"),
            output=Path("receipt.json"),
            backend="pilot",
            admit=True,
        )
        result = {"status": "complete-serialized-receipt"}
        with patch.object(
            probe.argparse.ArgumentParser, "parse_args", return_value=arguments
        ), patch.object(
            probe, "_cli_asset_owner_factories", return_value=()
        ) as capture, patch.object(
            probe,
            "execute",
            side_effect=lambda *a: calls.append("serialized") or result,
        ), patch.object(
            probe, "_finish_cli_assets", side_effect=lambda *a: calls.append("cleanup")
        ), redirect_stdout(
            io.StringIO()
        ) as output:
            probe.main()
        capture.assert_called_once_with()
        self.assertEqual(calls, ["serialized", "cleanup"])
        self.assertIn("complete-serialized-receipt", output.getvalue())

    def test_build_cli_uses_same_completion_lifecycle(self):
        calls = []
        arguments = SimpleNamespace(
            command="build",
            output=Path("candidate"),
            reference=3217,
            level=1,
            spell=4536,
        )
        with patch.object(
            probe.argparse.ArgumentParser, "parse_args", return_value=arguments
        ), patch.object(
            probe, "_cli_asset_owner_factories", return_value=()
        ), patch.object(
            probe,
            "build",
            side_effect=lambda *a: calls.append("sealed") or {"sealed": True},
        ), patch.object(
            probe, "_finish_cli_assets", side_effect=lambda *a: calls.append("cleanup")
        ), redirect_stdout(
            io.StringIO()
        ):
            probe.main()
        self.assertEqual(calls, ["sealed", "cleanup"])

    def test_failed_operation_or_cleanup_never_prints_success(self):
        arguments = SimpleNamespace(
            command="execute",
            candidate=Path("candidate"),
            output=Path("receipt.json"),
            backend="pilot",
            admit=True,
        )
        for failing_phase in ("execute", "_finish_cli_assets"):
            with self.subTest(phase=failing_phase), patch.object(
                probe.argparse.ArgumentParser, "parse_args", return_value=arguments
            ), patch.object(
                probe, "_cli_asset_owner_factories", return_value=()
            ), patch.object(
                probe, "execute", return_value={"status": "prepared"}
            ), patch.object(
                probe, "_finish_cli_assets"
            ) as finish, patch.object(
                probe, failing_phase, side_effect=RuntimeError("failure")
            ), redirect_stdout(
                io.StringIO()
            ) as output:
                with self.assertRaisesRegex(RuntimeError, "failure"):
                    probe.main()
                self.assertEqual(output.getvalue(), "")
                if failing_phase == "execute":
                    finish.assert_not_called()

    def test_import_does_not_freeze_or_initialize_resource_lifecycle(self):
        spec = importlib.util.spec_from_file_location(
            "imported_native_probe", probe.__file__
        )
        module = importlib.util.module_from_spec(spec)
        from wakfu_server import native_catalog

        with patch("gc.freeze") as freeze, patch.object(
            native_catalog, "_database"
        ) as database, patch.object(native_catalog, "_redis") as redis:
            spec.loader.exec_module(module)
        freeze.assert_not_called()
        database.assert_not_called()
        redis.assert_not_called()
