"""Guard the local native probe's read-only database/cache boundary."""
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


source = Path(__file__).resolve().parents[1] / "tools" / "wakia_native_probe.py"
spec = importlib.util.spec_from_file_location("wakia_native_probe", source)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class NativeProbeReadOnlyTests(unittest.TestCase):
    def providers(self, read_only="on"):
        class Redis:
            def execute_command(self, *args, **kwargs):
                return args

        class Pipeline:
            def __init__(self, *commands):
                self.command_stack = [(command, {}) for command in commands]
                self.watching = False

            def execute_command(self, *args, **kwargs):
                if self.watching:
                    return self.immediate_execute_command(*args, **kwargs)
                return self.pipeline_execute_command(*args, **kwargs)

            def immediate_execute_command(self, *args, **kwargs):
                return ("immediate", args)

            def pipeline_execute_command(self, *args, **kwargs):
                self.command_stack.append((args, kwargs))
                return "queued"

            def execute(self, *args, **kwargs):
                return "read"

        class Connection:
            def execute(self, sql):
                if sql != "SHOW transaction_read_only":
                    raise AssertionError(sql)
                return SimpleNamespace(fetchone=lambda: (read_only,))

        @contextmanager
        def connection():
            yield Connection()

        catalog = SimpleNamespace(
            _database=lambda: SimpleNamespace(connection=connection)
        )
        redis = SimpleNamespace(Redis=Redis, client=SimpleNamespace(Pipeline=Pipeline))
        return redis, catalog

    def test_postgres_mode_is_verified_and_redis_writes_are_rejected(self):
        redis, catalog = self.providers()
        with patch.dict(
            sys.modules, {"redis": redis, "wakfu_server.native_catalog": catalog}
        ), patch.dict(os.environ, {"PGOPTIONS": "-c application_name=wakia-probe"}):
            probe.readonly_providers()
            self.assertIn("default_transaction_read_only=on", os.environ["PGOPTIONS"])
            self.assertEqual(
                redis.Redis().execute_command("GET", "key"), ("GET", "key")
            )
            with self.assertRaises(PermissionError):
                redis.Redis().execute_command("SET", "key", "value")
            with self.assertRaises(PermissionError):
                redis.Redis().execute_command("EVAL", "return 1", 0)
            self.assertEqual(redis.client.Pipeline(("GET", "key")).execute(), "read")
            with self.assertRaises(PermissionError):
                redis.client.Pipeline(("GET", "key"), ("SET", "key", "value")).execute()
            watched = redis.client.Pipeline()
            watched.watching = True
            self.assertEqual(
                watched.execute_command("GET", "key"), ("immediate", ("GET", "key"))
            )
            with self.assertRaises(PermissionError):
                watched.execute_command("SET", "key", "value")
            with self.assertRaises(PermissionError):
                watched.immediate_execute_command("SET", "key", "value")
            with self.assertRaises(PermissionError):
                watched.pipeline_execute_command("SET", "key", "value")

    def test_refuses_postgres_if_read_only_mode_is_not_active(self):
        redis, catalog = self.providers(read_only="off")
        with patch.dict(
            sys.modules, {"redis": redis, "wakfu_server.native_catalog": catalog}
        ), patch.dict(os.environ, {}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "read-only PostgreSQL"):
                probe.readonly_providers()

    def test_termination_cleans_up_without_resuming_the_probe(self):
        root = Path(__file__).resolve().parents[2]
        script = root / "server/tools/wakia-native-probe.sh"
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory)
            log = fake_bin / "docker.log"
            docker = fake_bin / "docker"
            docker.write_text(
                """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
case "$1 $2" in
  'context show') printf '%s\\n' local ;;
  'context inspect') printf '%s\\n' unix:///fake/docker.sock ;;
  'compose ps') printf '%s\\n' test-world ;;
  'compose config') printf '%s\\n' '{"services":{"wakia":{"image":"fake-image"}}}' ;;
  'inspect --format')
    case "$3" in
      *project.working_dir*) printf '%s\\n' "$FAKE_PROJECT_ROOT" ;;
      *com.docker.compose.project*) printf '%s\\n' wakfu-local ;;
      *) printf '%s\\n' yes ;;
    esac ;;
  'run -d') kill -TERM "$PPID" ;;
  'stop '*) exit 0 ;;
  *) exit 2 ;;
esac
"""
            )
            docker.chmod(0o755)
            env = dict(
                os.environ,
                PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
                FAKE_DOCKER_LOG=str(log),
                FAKE_PROJECT_ROOT=str(root),
                DOCKER_HOST="",
            )
            result = subprocess.run(
                ["sh", str(script)], env=env, capture_output=True, text=True, timeout=10
            )
            calls = log.read_text().splitlines()
        self.assertEqual(result.returncode, 143, result.stderr)
        self.assertEqual(sum(line.startswith("stop wakia-probe-") for line in calls), 1)
        self.assertFalse(any(line.startswith("exec ") for line in calls), calls)


if __name__ == "__main__":
    unittest.main()
