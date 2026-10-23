"""Run the sole admitted Tal caller, then attest its authentic retained endpoint."""
import importlib, importlib.util, json, sys, unittest
from pathlib import Path
from _qualification_resumed_scopes import _refresh_function


class AttestedEndpointSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        try:
            return super().run(result, debug)
        finally:
            recipe = importlib.import_module("test_talkasha_paid_native_rykaon")
            checkpoint = recipe.TAL_ACTUAL_CHECKPOINT
            if checkpoint is not None:
                name = "_private_loaded_implementation_checkpoint"
                if name not in sys.modules:
                    spec = importlib.util.spec_from_file_location(
                        name, ".runtime/tools/loaded_implementation_checkpoint.py"
                    )
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[name] = module
                    spec.loader.exec_module(module)
                api = sys.modules[name]
                messages = importlib.import_module(
                    "wakfu_server.combat_runtime_messages"
                )
                factory = importlib.import_module("wakfu_server.combat_effect_runtime")
                resolver = importlib.import_module(
                    "wakfu_server.combat_effect_resolver"
                )
                damage = importlib.import_module("wakfu_server.combat_damage_handler")
                replay = importlib.import_module("wakfu_server.combat_event_replay")
                current = checkpoint["current"]
                identities = dict(
                    current=current,
                    runtime=current.runtime,
                    store=checkpoint["store"],
                    rng=current.rng,
                    RuntimeMessages=messages.RuntimeMessages,
                )
                roots = dict(
                    factory=factory.NativeEffectRuntimeFactory,
                    resolver=resolver.NativeEffectResolver,
                    damage=damage.NativeDamageHandler,
                    replay=replay.NativeEventReplay,
                )
                token = api.capture(
                    identities=identities, roots=roots, modules=(recipe,)
                )

                def verify():
                    actual = recipe.TAL_ACTUAL_CHECKPOINT
                    assert actual is checkpoint
                    obj = actual["current"]
                    return api.verify(
                        token,
                        identities=dict(
                            current=obj,
                            runtime=obj.runtime,
                            store=actual["store"],
                            rng=obj.rng,
                            RuntimeMessages=messages.RuntimeMessages,
                        ),
                        roots=roots,
                    )

                recipe.admit_actual_talkasha_continuation(verifier=verify)
                checkpoint["loaded_implementation_token"] = token
                description = api.describe(token)
                description[
                    "capture_timing"
                ] = "Once at authentic endpoint claim, after all temporary observers restored; protects subsequent continuations"
                description["verification"] = verify()
                Path(
                    ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/tal262-authentic-endpoint-loaded-implementation-attestation.json"
                ).write_text(json.dumps(description, indent=2, default=str))


def qualify():
    old = importlib.import_module("test_talkasha_paid_native_rykaon")
    assert old.TAL_ACTUAL_CHECKPOINT is None
    importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_movement_binding")
    )
    _refresh_function(
        "wakfu_server.combat_encounter_roles", "bind_roles", preserve_aliases=True
    )
    _refresh_function(
        "wakfu_server.combat_event_replay",
        "__call__",
        classname="NativeEventReplay",
        preserve_aliases=True,
    )
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    replay = importlib.import_module("wakfu_server.combat_event_replay")
    assert "freeze_movement_binding" in roles.bind_roles.__code__.co_names
    assert "movement_caster" in replay.NativeEventReplay.__call__.__code__.co_names
    recipe = importlib.reload(old)
    recipe.TAL_HOLD_ACTUAL_CHECKPOINT = False
    recipe.TAL_RETAIN_ENCOUNTER_CHECKPOINT = True
    suite = AttestedEndpointSuite()
    suite.addTests(
        unittest.defaultTestLoader.loadTestsFromName(
            "TalKashaPaidNativeRykaonTests.test_paid_cardinal_lights_and_native_phase_produce_eligible_rykaon_and_8148",
            recipe,
        )
    )
    return unittest.TestSuite([suite])
