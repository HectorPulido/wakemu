"""Adopt the qualified PV reservation and recurring policy in two held scopes."""
import ast
import copy
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

TRANSITIONS = {}


class AdoptTwoQualifiedChanges(unittest.TestCase):
    def runTest(self):
        from wakfu_server.combat_state import Fight
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
        from wakfu_server.combat_server_spell import server_runtime

        listeners = importlib.import_module(
            "wakfu_server.combat_encounter_table_listeners"
        )
        factory = importlib.import_module("wakfu_server.combat_effect_runtime")
        resolver = importlib.import_module("wakfu_server.combat_effect_resolver")
        damage = importlib.import_module("wakfu_server.combat_damage_handler")
        replay = importlib.import_module("wakfu_server.combat_event_replay")
        spec = importlib.util.spec_from_file_location(
            "_private_scoped_policy_code_transition",
            ".runtime/tools/qualified_scoped_policy_code_transition.py",
        )
        helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = helper
        spec.loader.exec_module(helper)
        nox = sys.modules["test_nox_full_party_victory_v4"]
        nr = nox.retained_components[0]
        rushu = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = rushu.RUSHU_ACTUAL_CHECKPOINT
        na = sys.modules["_nox_loaded_implementation_checkpoint_v2_canonical"]
        ra = sys.modules["_nox_loaded_implementation_checkpoint"]

        def nox_bindings(label):
            self.assertEqual(label, "admission")
            self.assertIs(nox.retained_components[0], nr)
            runtime = nr["case"].runtime
            return (
                dict(
                    runtime=runtime,
                    store=nr["fixture"].store,
                    rng=nr["case"].rng,
                    RuntimeMessages=RuntimeMessages,
                ),
                dict(
                    dispatcher=EffectDispatcher,
                    amount=NativeRunnerAmount,
                    turn_start=runtime.turn_start_provider,
                    turn_end=runtime.turn_end_provider,
                    expiration_factory=runtime.expiration_runtime_factory,
                    server_runtime=server_runtime,
                ),
            )

        def rushu_bindings(label):
            self.assertIs(rushu.RUSHU_ACTUAL_CHECKPOINT, cp)
            runtime = cp["runtime"]
            identities = dict(
                store=cp["store"], rng=cp["rng"], RuntimeMessages=RuntimeMessages
            )
            if label == "admission":
                roots = dict(
                    factory=factory.NativeEffectRuntimeFactory,
                    resolver=resolver.NativeEffectResolver,
                    damage=damage.NativeDamageHandler,
                    replay=replay.NativeEventReplay,
                    admission_binder=rushu.RUSHU_LOADED_IMPLEMENTATION_BINDER,
                    attestation_capture=ra.capture,
                    attestation_verify=ra.verify,
                )
            else:
                self.assertEqual(label, "services")
                identities["runtime"] = runtime
                roots = dict(
                    stats=runtime.runtime_stats_serializer,
                    start=runtime.turn_start_provider,
                    end=runtime.turn_end_provider,
                    expiration=runtime.expiration_runtime_factory,
                )
            return identities, roots

        def source_node(path, name, classname=None):
            tree = ast.parse(Path(path).read_text(), str(path))
            nodes = tree.body
            if classname:
                parent = next(
                    n
                    for n in nodes
                    if isinstance(n, ast.ClassDef) and n.name == classname
                )
                node = next(
                    n
                    for n in parent.body
                    if isinstance(n, ast.FunctionDef) and n.name == name
                )
                body = [
                    ast.ClassDef(
                        name=classname,
                        bases=[],
                        keywords=[],
                        body=[node],
                        decorator_list=[],
                    )
                ]
            else:
                node = next(
                    n
                    for n in nodes
                    if isinstance(n, ast.FunctionDef) and n.name == name
                )
                body = [node]
            return ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))

        namespace = {}
        exec(
            compile(
                source_node(listeners.__file__, "_validate_callback"),
                listeners.__file__,
                "exec",
                dont_inherit=True,
            ),
            namespace,
        )
        callback_code = namespace["_validate_callback"].__code__
        namespace = {}
        state_path = importlib.import_module("wakfu_server.combat_state").__file__
        exec(
            compile(
                source_node(state_path, "allocate_area_uid", "Fight"),
                state_path,
                "exec",
                dont_inherit=True,
            ),
            namespace,
        )
        area_code = namespace["Fight"].allocate_area_uid.__code__
        # Read the immutable candidate in a private namespace; never swap the
        # loaded validator just to parse a policy that requires the new rule.
        policy_ns = dict(listeners.__dict__)
        exec(
            compile(
                source_node(listeners.__file__, "_validate_callback"),
                listeners.__file__,
                "exec",
                dont_inherit=True,
            ),
            policy_ns,
        )
        exec(
            compile(
                source_node(listeners.__file__, "_version"),
                listeners.__file__,
                "exec",
                dont_inherit=True,
            ),
            policy_ns,
        )
        candidate = copy.deepcopy(
            policy_ns["_version"]("wakemu-nox-owned-boundaries-v4")
        )
        patches = [
            (listeners._validate_callback, callback_code),
            (Fight.allocate_area_uid, area_code),
        ]
        prior_expiry = cp["authorized_recipe_expiration_transition"]
        original_rushu_verify = cp["authorized_service_transition_verifier"]
        nt = helper.prepare(
            name="nox-v4-before-fatality-recurring-policy",
            api=na,
            original_tokens={"admission": nr["loaded_code_attestation"]},
            verify_original=lambda: nox.verify_retained_component(nr),
            runtime=nr["case"].runtime,
            store=nr["fixture"].store,
            rng=nr["case"].rng,
            bindings=nox_bindings,
            patches=patches,
            new_nox_policy=candidate,
        )
        rt = helper.prepare(
            name="rushu-a11-preserved-expiration-service-segment",
            api=ra,
            original_tokens={
                "admission": cp["loaded_implementation_token"],
                "services": prior_expiry["new_tokens"]["services"],
            },
            verify_original=original_rushu_verify,
            runtime=cp["runtime"],
            store=cp["store"],
            rng=cp["rng"],
            bindings=rushu_bindings,
            patches=patches,
        )
        old_codes = [(fn, fn.__code__) for fn, new in patches]
        nf = nr["case"].fight
        old_policy = nf.native_encounter_table_listener_policy
        old_profile_policy = nf.boss_score_profile["table_listener_policy"]
        try:
            for fn, new in patches:
                fn.__code__ = new
            nf.native_encounter_table_listener_policy = copy.deepcopy(candidate)
            nf.boss_score_profile["table_listener_policy"] = copy.deepcopy(candidate)
            helper.complete(nt)
            helper.complete(rt)
        except BaseException:
            for fn, old in old_codes:
                fn.__code__ = old
            nf.native_encounter_table_listener_policy = old_policy
            nf.boss_score_profile["table_listener_policy"] = old_profile_policy
            raise

        def verify_nox(record=None):
            assert record is None or record is nr
            assert (
                len(nox.retained_components) == 1 and nox.retained_components[0] is nr
            )
            return helper.verify_adopted(nt)

        def verify_rushu():
            assert rushu.RUSHU_ACTUAL_CHECKPOINT is cp
            return helper.verify_adopted(rt)

        nr["authorized_scoped_policy_transition"] = nt
        nr["authorized_scoped_policy_transition_verifier"] = verify_nox
        cp["authorized_scoped_policy_transition"] = rt
        cp["authorized_scoped_policy_transition_verifier"] = verify_rushu
        cp["authorized_service_transition_verifier"] = verify_rushu
        TRANSITIONS.update(nox=nt, rushu=rt)
        facts = dict(
            nox=nt["receipt"],
            rushu=rt["receipt"],
            nox_verification=verify_nox(nr),
            rushu_verification=verify_rushu(),
            previous_rushu_expiration_transition=prior_expiry["receipt"],
            original_tokens_replaced=False,
            unchanged_since_admission_claimed=False,
            gameplay_actions=False,
        )
        Path(
            ".runtime/parallel-readiness-20261021/qualified-area-pv-and-nox267-dual-live-scope-transition.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([AdoptTwoQualifiedChanges()])
