"""Run the authorized bounded Ombrage case with explicit actual-state retention."""
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


def _loaded_api():
    name = "_private_loaded_implementation_checkpoint_v2"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            name, ".runtime/tools/loaded_implementation_checkpoint.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def _admission_binder(recipe):
    api = _loaded_api()

    def capture_before_admission(*, store, rng, runtime_class):
        factory = importlib.import_module("wakfu_server.combat_effect_runtime")
        resolver = importlib.import_module("wakfu_server.combat_effect_resolver")
        damage = importlib.import_module("wakfu_server.combat_damage_handler")
        replay = importlib.import_module("wakfu_server.combat_event_replay")
        handoff = importlib.import_module("tools.ombrage_live_phase_handoff")
        party = importlib.import_module("native_paid_party_fixture")
        publication = importlib.import_module("native_recorded_instance_fixture")
        identities = dict(store=store, rng=rng, RuntimeMessages=runtime_class)
        roots = dict(
            factory=factory.NativeEffectRuntimeFactory,
            resolver=resolver.NativeEffectResolver,
            damage=damage.NativeDamageHandler,
            replay=replay.NativeEventReplay,
            admission_binder=recipe.OMBRAGE_LOADED_IMPLEMENTATION_BINDER,
            attestation_capture=api.capture,
            attestation_verify=api.verify,
        )
        token = api.capture(
            identities=identities,
            roots=roots,
            modules=(recipe, sys.modules[__name__], handoff, party, publication),
        )
        bound = False

        def bind_runtime(checkpoint):
            nonlocal bound
            assert not bound, "The original runtime binding must not be replaced"
            bound = True
            runtime = checkpoint["runtime"]
            services = dict(
                runtime=runtime, store=store, rng=rng, RuntimeMessages=runtime_class
            )
            callbacks = dict(
                stats=runtime.runtime_stats_serializer,
                start=runtime.turn_start_provider,
                end=runtime.turn_end_provider,
                expiration=runtime.expiration_runtime_factory,
            )
            # This second token binds newly created services only. It contains
            # no module surface and never replaces the pre-admission token.
            service_token = api.capture(
                identities=services, roots=callbacks, prefixes=(), modules=()
            )

            def verify():
                assert (
                    recipe.OMBRAGE_LOADED_IMPLEMENTATION_BINDER
                    is capture_before_admission
                )
                assert (
                    recipe.OMBRAGE_ACTUAL_CHECKPOINT is None
                    or recipe.OMBRAGE_ACTUAL_CHECKPOINT is checkpoint
                )
                report = api.verify(
                    token,
                    identities=dict(
                        store=checkpoint["store"],
                        rng=checkpoint["rng"],
                        RuntimeMessages=importlib.import_module(
                            "wakfu_server.combat_runtime_messages"
                        ).RuntimeMessages,
                    ),
                    roots=roots,
                )
                current = checkpoint["runtime"]
                service_report = api.verify(
                    service_token,
                    identities=dict(
                        runtime=current,
                        store=checkpoint["store"],
                        rng=checkpoint["rng"],
                        RuntimeMessages=type(current),
                    ),
                    roots=dict(
                        stats=current.runtime_stats_serializer,
                        start=current.turn_start_provider,
                        end=current.turn_end_provider,
                        expiration=current.expiration_runtime_factory,
                    ),
                )
                report.update(
                    capture_timing="before_admission_and_before_temporary_observer_patches",
                    runtime_services_bound_once_at_creation=True,
                    service_binding=service_report,
                    disk_edits_do_not_require_global_hold=True,
                )
                return report

            checkpoint["loaded_implementation_token"] = token
            checkpoint["loaded_runtime_service_token"] = service_token
            checkpoint["loaded_implementation_verifier"] = verify
            checkpoint["loaded_implementation_description"] = api.describe(token)

        return bind_runtime

    return capture_before_admission


class AttestedOmbrageSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        try:
            return super().run(result, debug)
        finally:
            recipe = importlib.import_module("test_ombrage_native_paid_clock")
            checkpoint = recipe.OMBRAGE_ACTUAL_CHECKPOINT
            if checkpoint is not None:
                description = checkpoint.get("loaded_implementation_description", {})
                description = dict(
                    description,
                    verification=checkpoint["receipt"].get(
                        "loaded_implementation_attestation"
                    ),
                    observer_patches_restored_before_verification=True,
                )
                output = Path(
                    ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/ombrage-next-pre-admission-loaded-implementation-attestation.json"
                )
                output.write_text(json.dumps(description, indent=2, default=str) + "\n")


def qualify():
    old = importlib.import_module("test_ombrage_native_paid_clock")
    assert getattr(old, "OMBRAGE_ACTUAL_CHECKPOINT", None) is None
    module = importlib.reload(old)
    module.OMBRAGE_HOLD_ACTUAL_CHECKPOINT = True
    module.OMBRAGE_LOADED_IMPLEMENTATION_BINDER = _admission_binder(module)
    suite = AttestedOmbrageSuite()
    suite.addTests(
        unittest.defaultTestLoader.loadTestsFromName(
            "OmbrageNativePaidClockTests.test_native_endgame_budget_and_bounded_earned_clock",
            module,
        )
    )
    return suite
