"""Ecology preflight and isolated failures retain safe, useful explanations."""

import ast
from contextlib import nullcontext
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.ecology_admin_errors import (
    EcologyAdminFailure,
    EcologyPreparationFailure,
)
from wakfu_server.ecology_admin_jobs import EcologyAdminJobs
from wakfu_server.ecology_admin_worker import PreparationProcess


SERVER = Path(__file__).resolve().parents[1]


class EcologyAdminFailureFeedbackTests(unittest.TestCase):
    def scope_reader(self):
        source = SERVER / "wakfu_server/maps/ecology_admin.py"
        tree = ast.parse(source.read_text())
        node = next(
            row
            for row in tree.body
            if isinstance(row, ast.FunctionDef) and row.name == "_scopes"
        )
        namespace = dict(
            __package__="wakfu_server",
            REGIONS={(986, 70701): dict(monster_capacity=0, monster_families=[])},
            region_at=lambda *_args: 70701,
        )
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        return namespace["_scopes"]

    def run_job(self, execute, *, prepare_factory=None):
        jobs = EcologyAdminJobs(
            object(),
            object(),
            prepare_factory=prepare_factory
            or (lambda: nullcontext(SimpleNamespace(pid=None))),
        )
        notifications = []
        with patch.dict(
            sys.modules,
            {"wakfu_server.ecology_admin": SimpleNamespace(execute=execute)},
        ):
            accepted = jobs.request(
                account_id=10,
                generation="original-session",
                character=dict(
                    id=67, account_id=10, map_id=986, instance_id=0, x=-42, y=-13, z=0
                ),
                command="!genesis",
                notify=notifications.append,
            )
            jobs.thread.join(timeout=3)
            self.assertFalse(jobs.thread.is_alive())
        self.assertEqual(len(notifications), 1)
        return jobs.status(accepted["handle"]), notifications[0]

    def test_unsupported_habitat_fails_before_preparation_or_population_mutations(self):
        read_scopes = self.scope_reader()
        preparation, mutation = Mock(), Mock()
        database = Mock()

        def execute(store, groups, character, command, **options):
            scopes = read_scopes(database, character, False, genesis=True)
            preparation(scopes)
            mutation(scopes)

        result, notice = self.run_job(execute)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "no_monster_habitat")
        self.assertIn("hábitat nativo de monstruos", result["message"])
        self.assertIn("No native monster habitat", result["reason"])
        self.assertTrue(result["traceback"])
        self.assertEqual(
            (result["added"], result["removed"], result["scopes"]), (0, 0, [])
        )
        self.assertEqual(notice["error_code"], "no_monster_habitat")
        preparation.assert_not_called()
        mutation.assert_not_called()
        database.execute.assert_not_called()
        # The same zero-capacity location still permits an ordinary no-op nuke.
        self.assertEqual(
            read_scopes(database, dict(map_id=986, instance_id=0, x=-42, y=-13), False),
            [(986, 0, 70701)],
        )

    def test_successful_job_keeps_completed_counts_and_notice(self):
        def execute(*args, **options):
            outcome = dict(added=3, removed=0, scopes=[(527, 0, 7)], operation_ids=[9])
            options["publish"](outcome)
            return outcome

        result, notice = self.run_job(execute)
        self.assertEqual(
            (result["status"], result["added"], result["scopes"]),
            ("completed", 3, [(527, 0, 7)]),
        )
        self.assertEqual(result["operation_ids"], [9])
        self.assertIn("terminada", notice["message"])
        self.assertNotIn("error_code", result)

    def test_child_reason_and_trace_reach_admin_but_never_become_arbitrary_player_text(
        self,
    ):
        child = """
import struct,sys
from types import SimpleNamespace
from wakfu_server.ecology_admin_worker import main
from wakfu_server.ecology_admin_errors import EcologyAdminFailure
import wakfu_server
mode=sys.argv[1]
def prepare(*args):
    if mode == 'known':
        raise EcologyAdminFailure('no_monster_habitat')
    raise RuntimeError('Internal backend detail token=supersecretvalue')
sys.modules['wakfu_server.ecology_admin_planner']=SimpleNamespace(prepare=prepare)
wakfu_server.native_catalog=SimpleNamespace(release=lambda: 'ecology-feedback-test')
main()
"""
        for mode in ("known", "unexpected"):
            with self.subTest(mode=mode):
                factory = lambda: PreparationProcess(
                    timeout=3, command=[sys.executable, "-c", child, mode]
                )

                def execute(*args, **options):
                    options["prepare_scope"]("monsters", 986, 70701)
                    self.fail("failed preparation reached population execution")

                result, notice = self.run_job(execute, prepare_factory=factory)
                self.assertEqual(result["status"], "failed")
                self.assertTrue(
                    any(frame["function"] == "prepare" for frame in result["traceback"])
                )
                self.assertEqual(result["preparation_failures"][0]["map_id"], 986)
                self.assertEqual(result["preparation_failures"][0]["region_id"], 70701)
                if mode == "known":
                    self.assertEqual(result["error_type"], "EcologyAdminFailure")
                    self.assertEqual(result["error_code"], "no_monster_habitat")
                    self.assertIn("hábitat nativo", notice["message"])
                else:
                    self.assertEqual(result["error_type"], "RuntimeError")
                    self.assertIsNone(result["error_code"])
                    self.assertIn("Internal backend detail", result["reason"])
                    self.assertIn("[redacted]", result["reason"])
                    for private_text in (
                        "supersecretvalue",
                        "Internal backend detail",
                        "Traceback",
                        "RuntimeError",
                    ):
                        self.assertNotIn(private_text, notice["message"])
                    self.assertIn("consola del servidor", notice["message"])

    def test_preparation_protocol_does_not_accept_an_unknown_public_reason(self):
        child = """
import struct,sys
from wakfu_server.ecology_admin_worker import encode
size=struct.unpack('>I',sys.stdin.buffer.read(4))[0]
sys.stdin.buffer.read(size)
sys.stdout.buffer.write(encode(dict(ok=False,error_type='RuntimeError',error_code='Internal token=unsafe',reason='private failure',traceback=[])))
sys.stdout.buffer.flush()
"""
        with PreparationProcess(
            timeout=3, command=[sys.executable, "-c", child]
        ) as prepare:
            with self.assertRaises(EcologyPreparationFailure) as error:
                prepare("monsters", 986, 70701)
        self.assertIsNone(error.exception.details["error_code"])
        self.assertEqual(error.exception.details["reason"], "private failure")


if __name__ == "__main__":
    unittest.main()
