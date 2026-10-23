"""Link reviewed terminal reconstruction to both held scopes without gameplay."""
import copy
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

TRANSITIONS = {}


class AdoptTerminal269(unittest.TestCase):
    def runTest(self):
        from wakfu_server.combat_kill import NativeKillHandler

        roles = importlib.import_module("wakfu_server.combat_encounter_roles")
        server = importlib.import_module("wakfu_server.combat_server_spell")
        prior = sys.modules[
            "_qualification_returned_qq_dual_live_scope_adoption"
        ].TRANSITIONS
        nox = sys.modules["test_nox_full_party_victory_v5"]
        nr = nox.retained_components[0]
        rushu = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = rushu.RUSHU_ACTUAL_CHECKPOINT
        nv = nr["authorized_scoped_policy_transition_verifier"]
        rv = cp["authorized_service_transition_verifier"]
        nv(nr)
        rv()
        cleanup = importlib.import_module(
            "wakfu_server.combat_encounter_terminal_cleanup"
        )
        with cleanup._database().connection() as db:
            active = db.execute(
                "SELECT policy FROM encounter_terminal_cleanup_active WHERE map_id=%s AND monster_references=%s::integer[]",
                (1435, [5664]),
            ).fetchone()
        candidate = copy.deepcopy(cleanup._version(active["policy"]))
        frozen = json.loads(
            Path(
                ".runtime/parallel-readiness-20261021/nox269-focused-source-freeze.json"
            ).read_text()
        )
        inventory = {
            name: dict(path=path, sha256=frozen[path])
            for name, path in (
                ("bind_roles", "server/wakfu_server/combat/combat_encounter_roles.py"),
                (
                    "prepare_server_turn_end",
                    "server/wakfu_server/combat/combat_server_spell.py",
                ),
                ("_apply", "server/wakfu_server/combat/combat_kill.py"),
            )
        }
        spec = importlib.util.spec_from_file_location(
            "_private_qualified_terminal269_transition",
            ".runtime/tools/qualified_terminal_cleanup_269_transition.py",
        )
        helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = helper
        spec.loader.exec_module(helper)
        end = server.prepare_server_turn_end
        end_outer = end
        depth = 0
        while hasattr(end, "__wrapped__"):
            end = end.__wrapped__
            depth += 1
        patches = helper.approved_patches(
            prior["nox"]["api"],
            [roles.bind_roles, end, NativeKillHandler._apply],
            inventory,
        )
        prepared = {}
        for name, verify, newpolicy in (
            ("nox", lambda: nv(nr), candidate),
            ("rushu", rv, None),
        ):
            previous = prior[name]
            prepared[name] = helper.prepare(
                name=name + "-terminal269-code-segment",
                api=previous["api"],
                original_tokens=previous["new_tokens"],
                verify_original=verify,
                runtime=previous["runtime"],
                store=previous["store"],
                rng=previous["rng"],
                bindings=previous["bindings"],
                previous_transition=previous,
                patches=patches,
                source_inventory=inventory,
                module_sha=frozen[
                    "server/wakfu_server/combat/combat_encounter_terminal_cleanup.py"
                ],
                new_nox_policy=newpolicy,
            )
        # Both independent preparations approved the same wrapper source. Install
        # one object shared by the two linked attestation segments.
        prepared["rushu"]["wrapper"] = prepared["nox"]["wrapper"]
        original_codes = [(fn, fn.__code__) for fn, new in patches]
        existed = hasattr(server, "prepare_server_terminal_cleanup")
        old_wrapper = getattr(server, "prepare_server_terminal_cleanup", None)
        nf = nr["case"].fight
        old_exists = hasattr(nf, "native_encounter_terminal_cleanup_policy")
        old_policy = getattr(nf, "native_encounter_terminal_cleanup_policy", None)
        try:
            for fn, new in patches:
                fn.__code__ = new
            server.prepare_server_terminal_cleanup = prepared["nox"]["wrapper"]
            nf.native_encounter_terminal_cleanup_policy = copy.deepcopy(candidate)
            helper.complete(prepared["nox"])
            helper.complete(prepared["rushu"])
        except BaseException:
            for fn, old in original_codes:
                fn.__code__ = old
            if existed:
                server.prepare_server_terminal_cleanup = old_wrapper
            else:
                delattr(server, "prepare_server_terminal_cleanup")
            if old_exists:
                nf.native_encounter_terminal_cleanup_policy = old_policy
            else:
                delattr(nf, "native_encounter_terminal_cleanup_policy")
            raise
        self.assertIs(server.prepare_server_turn_end, end_outer)

        def verify_nox(record=None):
            assert record is None or record is nr
            assert nox.retained_components[0] is nr
            return helper.verify_adopted(prepared["nox"])

        def verify_rushu():
            assert rushu.RUSHU_ACTUAL_CHECKPOINT is cp
            return helper.verify_adopted(prepared["rushu"])

        nr["authorized_terminal269_transition"] = prepared["nox"]
        nr["authorized_scoped_policy_transition_verifier"] = verify_nox
        cp["authorized_terminal269_transition"] = prepared["rushu"]
        cp["authorized_service_transition_verifier"] = verify_rushu
        cp["authorized_scoped_policy_transition_verifier"] = verify_rushu
        TRANSITIONS.update(prepared)
        facts = dict(
            nox=prepared["nox"]["receipt"],
            rushu=prepared["rushu"]["receipt"],
            wrapper_depth_preserved=depth,
            shared_new_wrapper=True,
            no_gameplay_actions=True,
            native_cleanup_executed=False,
            nox_verification=verify_nox(nr),
            rushu_verification=verify_rushu(),
        )
        Path(
            ".runtime/parallel-readiness-20261021/qualified-terminal269-dual-live-scope-transition.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([AdoptTerminal269()])
