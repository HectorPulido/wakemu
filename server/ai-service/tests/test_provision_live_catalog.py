"""Live catalogue provisioning never mutates or restarts the shared world."""
import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import patch
from scripts import provision_live_catalog as provisioner


class LiveCatalogProvisionTests(unittest.TestCase):
    def run_provision(self, sealed=None):
        def command(*args, **kwargs):
            if "wakfu_ai.context.catalog_bootstrap" in args:
                return json.dumps(dict(sha256="a" * 64, entries=100, bytes=999999999))
            if "-i" in args:
                return json.dumps(
                    sealed if sealed is not None else dict(complete=True, entries=100)
                )
            return ""

        with patch.object(
            provisioner, "identity", return_value="same-world"
        ), patch.object(
            provisioner, "command", side_effect=command
        ) as calls, contextlib.redirect_stdout(
            io.StringIO()
        ) as output:
            provisioner.provision("world", "ai")
        return calls, json.loads(output.getvalue())

    def test_all_bytes_are_provisioned_without_world_source_mutation_or_restart(self):
        calls, result = self.run_provision()
        self.assertEqual(result["catalogue"]["bytes"], 999999999)
        self.assertTrue(result["sealed"]["complete"])
        allowed_world_read = (
            "docker",
            "exec",
            "world",
            "python3",
            "/app/ai-service/prepare_catalog_cache.py",
        )
        world_execs = []
        for call in calls.call_args_list:
            if call.args[:2] == ("docker", "exec"):
                if "world" in call.args:
                    world_execs.append(call.args)
                    self.assertEqual(call.args, allowed_world_read)
                else:
                    self.assertIn("ai", call.args)
        self.assertEqual(world_execs, [allowed_world_read])
        self.assertTrue(
            any(
                call.args[:3] == ("docker", "cp", "world:/app/.")
                for call in calls.call_args_list
            )
        )

    def test_world_change_rejects_capture_before_any_ai_mutation(self):
        with patch.object(
            provisioner, "identity", side_effect=["old", "new"]
        ), patch.object(
            provisioner, "command", return_value=""
        ) as command, self.assertRaisesRegex(
            RuntimeError, "World changed"
        ):
            provisioner.provision("world", "ai")
        self.assertEqual(command.call_count, 2)
        self.assertEqual(
            command.call_args_list[0].args,
            (
                "docker",
                "exec",
                "world",
                "python3",
                "/app/ai-service/prepare_catalog_cache.py",
            ),
        )
        self.assertEqual(
            command.call_args_list[1].args[:3], ("docker", "cp", "world:/app/.")
        )
        self.assertFalse(
            any(
                call.args[:3] == ("docker", "exec", "ai")
                for call in command.call_args_list
            )
        )

    def test_world_change_after_sealing_rejects_provisioned_result(self):
        with patch.object(
            provisioner, "identity", side_effect=["same", "same", "changed"]
        ) as identity, patch.object(
            provisioner, "command"
        ) as command, contextlib.redirect_stdout(
            io.StringIO()
        ), self.assertRaisesRegex(
            RuntimeError, "World changed during complete catalogue provisioning"
        ):

            def answer(*args, **kwargs):
                if "wakfu_ai.context.catalog_bootstrap" in args:
                    return json.dumps(dict(sha256="b" * 64, entries=12, bytes=456))
                if "-i" in args:
                    return json.dumps(dict(complete=True, entries=12))
                return ""

            command.side_effect = answer
            provisioner.provision("world", "ai")
        self.assertTrue(
            any(
                "wakfu_ai.context.catalog_bootstrap" in call.args
                for call in command.call_args_list
            )
        )
        self.assertTrue(any("-i" in call.args for call in command.call_args_list))
        self.assertEqual(identity.call_count, 3)

    def test_failed_world_docker_copy_does_not_mutate_ai_or_continue(self):
        def command(*args, **kwargs):
            if args[:2] == ("docker", "cp"):
                raise subprocess.CalledProcessError(1, args)
            return ""

        with patch.object(
            provisioner, "identity", return_value="same-world"
        ), patch.object(
            provisioner, "command", side_effect=command
        ) as calls, self.assertRaises(
            subprocess.CalledProcessError
        ):
            provisioner.provision("world", "ai")
        self.assertEqual(calls.call_count, 2)
        self.assertEqual(
            calls.call_args_list[0].args,
            (
                "docker",
                "exec",
                "world",
                "python3",
                "/app/ai-service/prepare_catalog_cache.py",
            ),
        )
        self.assertEqual(
            calls.call_args_list[1].args[:3], ("docker", "cp", "world:/app/.")
        )
        self.assertFalse(
            any(
                call.args[:3] == ("docker", "exec", "ai")
                for call in calls.call_args_list
            )
        )

    def test_malformed_bootstrap_json_fails_before_sealing(self):
        def command(*args, **kwargs):
            if "wakfu_ai.context.catalog_bootstrap" in args:
                return "{not-json"
            return ""

        with patch.object(
            provisioner, "identity", return_value="same-world"
        ), patch.object(
            provisioner, "command", side_effect=command
        ) as calls, self.assertRaises(
            json.JSONDecodeError
        ):
            provisioner.provision("world", "ai")
        self.assertTrue(
            any(
                "wakfu_ai.context.catalog_bootstrap" in call.args
                for call in calls.call_args_list
            )
        )
        self.assertFalse(any("-i" in call.args for call in calls.call_args_list))

    def test_malformed_seal_json_fails_without_final_success_output(self):
        output = io.StringIO()

        def command(*args, **kwargs):
            if "wakfu_ai.context.catalog_bootstrap" in args:
                return json.dumps(dict(sha256="c" * 64, entries=3, bytes=456))
            if "-i" in args:
                return "[]broken"
            return ""

        with patch.object(
            provisioner, "identity", return_value="same-world"
        ), patch.object(
            provisioner, "command", side_effect=command
        ) as calls, contextlib.redirect_stdout(
            output
        ), self.assertRaises(
            json.JSONDecodeError
        ):
            provisioner.provision("world", "ai")
        self.assertTrue(any("-i" in call.args for call in calls.call_args_list))
        self.assertEqual(output.getvalue(), "")

    def test_incomplete_or_wrong_entry_count_is_rejected(self):
        for sealed in (
            dict(complete=False, entries=100),
            dict(complete=True, entries=99),
        ):
            with self.subTest(sealed=sealed), self.assertRaisesRegex(
                RuntimeError, "complete live"
            ):
                self.run_provision(sealed)
