"""Run the sole authorized full-build Rushu cycle5 and retain its actual services."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


def _loaded_api():
    name = "_nox_loaded_implementation_checkpoint"
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
        party = importlib.import_module("native_paid_party_fixture")
        publication = importlib.import_module("native_recorded_instance_fixture")
        identities = dict(store=store, rng=rng, RuntimeMessages=runtime_class)
        roots = dict(
            factory=factory.NativeEffectRuntimeFactory,
            resolver=resolver.NativeEffectResolver,
            damage=damage.NativeDamageHandler,
            replay=replay.NativeEventReplay,
            admission_binder=recipe.RUSHU_LOADED_IMPLEMENTATION_BINDER,
            attestation_capture=api.capture,
            attestation_verify=api.verify,
        )
        token = api.capture(
            identities=identities,
            roots=roots,
            modules=(recipe, sys.modules[__name__], party, publication),
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
                    recipe.RUSHU_LOADED_IMPLEMENTATION_BINDER
                    is capture_before_admission
                )
                assert (
                    recipe.RUSHU_ACTUAL_CHECKPOINT is None
                    or recipe.RUSHU_ACTUAL_CHECKPOINT is checkpoint
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


def qualify():
    previous = importlib.import_module("test_rushu_native_party_phase_one")
    assert getattr(previous, "RUSHU_ACTUAL_CHECKPOINT", None) is None
    module = importlib.reload(previous)
    module.RUSHU_HOLD_ACTUAL_CHECKPOINT = True
    module.RUSHU_LOADED_IMPLEMENTATION_BINDER = _admission_binder(module)
    return unittest.defaultTestLoader.loadTestsFromName(
        "RushuNativePartyPhaseOneTests.test_normal_party_heals_and_rotates_native_nearest_recipient",
        module,
    )
