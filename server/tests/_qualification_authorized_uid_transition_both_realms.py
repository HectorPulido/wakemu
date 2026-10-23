"""Perform one reviewed allocator-code transition across both original live realms."""
import importlib, importlib.util, json, sys, unittest
from pathlib import Path

TRANSITIONS = {}


class AdoptQualifiedUidCode(unittest.TestCase):
    def runTest(self):
        from wakfu_server.combat_state import Fight
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
        from wakfu_server.combat_server_spell import server_runtime

        factory = importlib.import_module("wakfu_server.combat_effect_runtime")
        resolver = importlib.import_module("wakfu_server.combat_effect_resolver")
        damage = importlib.import_module("wakfu_server.combat_damage_handler")
        replay = importlib.import_module("wakfu_server.combat_event_replay")
        key = "_private_qualified_uid_code_transition"
        spec = importlib.util.spec_from_file_location(
            key, ".runtime/tools/qualified_uid_code_transition.py"
        )
        helper = importlib.util.module_from_spec(spec)
        sys.modules[key] = helper
        spec.loader.exec_module(helper)
        nox = sys.modules["test_nox_full_party_early_score"]
        nr = nox.retained_components[0]
        rushu = sys.modules["test_rushu_dd230_native_opening"]
        cp = rushu.RUSHU_ACTUAL_CHECKPOINT
        na = sys.modules["_nox_loaded_implementation_checkpoint_v2_canonical"]
        ra = sys.modules["_nox_loaded_implementation_checkpoint"]

        def nox_bindings(label):
            assert (
                label == "admission"
                and len(nox.retained_components) == 1
                and nox.retained_components[0] is nr
            )
            case = nr["case"]
            runtime = case.runtime
            return (
                dict(
                    runtime=runtime,
                    store=nr["fixture"].store,
                    rng=case.rng,
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
            assert rushu.RUSHU_ACTUAL_CHECKPOINT is cp
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
                assert label == "services"
                identities["runtime"] = runtime
                roots = dict(
                    stats=runtime.runtime_stats_serializer,
                    start=runtime.turn_start_provider,
                    end=runtime.turn_end_provider,
                    expiration=runtime.expiration_runtime_factory,
                )
            return identities, roots

        method = Fight.allocate_effect_uid
        replacement = helper.approved_code(na, method)
        originals = dict(
            nox=nr["loaded_code_attestation"],
            rushu_admission=cp["loaded_implementation_token"],
            rushu_services=cp["loaded_runtime_service_token"],
        )

        def identity_row(runtime, store, rng):
            return dict(
                runtime=id(runtime),
                fight=id(runtime.fight),
                store=id(store),
                rng=id(rng),
                fight_class=id(type(runtime.fight)),
                counter=runtime.fight.native_effect_uid_next,
            )

        before = dict(
            nox=identity_row(nr["case"].runtime, nr["fixture"].store, nr["case"].rng),
            rushu=identity_row(cp["runtime"], cp["store"], cp["rng"]),
        )
        nt = helper.prepare(
            name="nox-full-native-original",
            api=na,
            original_tokens={"admission": originals["nox"]},
            verify_original=lambda: nox.verify_retained_component(nr),
            runtime=nr["case"].runtime,
            store=nr["fixture"].store,
            rng=nr["case"].rng,
            bindings=nox_bindings,
            method=method,
            replacement=replacement,
        )
        rt = helper.prepare(
            name="rushu-dd230-original",
            api=ra,
            original_tokens={
                "admission": originals["rushu_admission"],
                "services": originals["rushu_services"],
            },
            verify_original=rushu.verify_actual_checkpoint,
            runtime=cp["runtime"],
            store=cp["store"],
            rng=cp["rng"],
            bindings=rushu_bindings,
            method=method,
            replacement=replacement,
        )
        old_code = method.__code__
        try:
            method.__code__ = replacement
            helper.complete(nt)
            helper.complete(rt)
        except BaseException:
            method.__code__ = old_code
            raise
        self.assertIs(Fight.allocate_effect_uid, method)

        def verify_nox(record=None):
            assert record is None or record is nr
            assert (
                len(nox.retained_components) == 1 and nox.retained_components[0] is nr
            )
            return helper.verify_adopted(nt, nr)

        def verify_rushu():
            assert rushu.RUSHU_ACTUAL_CHECKPOINT is cp
            return helper.verify_adopted(rt)

        nr["authorized_uid_transition"] = nt
        nr["authorized_uid_transition_verifier"] = verify_nox
        cp["authorized_uid_transition"] = rt
        cp["authorized_uid_transition_verifier"] = verify_rushu
        TRANSITIONS.update(nox=nt, rushu=rt)
        after = dict(
            nox=identity_row(nr["case"].runtime, nr["fixture"].store, nr["case"].rng),
            rushu=identity_row(cp["runtime"], cp["store"], cp["rng"]),
        )
        self.assertEqual(before, after)
        self.assertIs(nr["loaded_code_attestation"], originals["nox"])
        self.assertIs(cp["loaded_implementation_token"], originals["rushu_admission"])
        self.assertIs(cp["loaded_runtime_service_token"], originals["rushu_services"])
        receipt = dict(
            policy="authorized-code-only-transition-both-live-realms",
            before=before,
            after=after,
            no_gameplay_actions=True,
            only_allocator_code_changed=True,
            original_tokens_replaced=False,
            unchanged_since_admission_claimed=False,
            nox=nt["receipt"],
            rushu=rt["receipt"],
            verification_nox=verify_nox(nr),
            verification_rushu=verify_rushu(),
        )
        Path(
            ".runtime/parallel-readiness-20261021/uid-namespace-qualified-code-transition-both-live-realms.json"
        ).write_text(json.dumps(receipt, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([AdoptQualifiedUidCode()])
