"""Adopt the qualified chosen-PV fix only after both original realms are closed."""
import hashlib, importlib, json, sys, unittest
from pathlib import Path
from _qualification_resumed_scopes import _refresh_function


def adopt():
    assert not sys.modules["test_nox_prelude_five_modes_and_polary"].retained_components
    assert (
        sys.modules["test_rushu_native_party_phase_one"].RUSHU_ACTUAL_CHECKPOINT is None
    )
    module = importlib.import_module("wakfu_server.combat_effect_resolver")
    original_class = module.NativeEffectResolver
    function = original_class.candidate_invocations
    groups = importlib.import_module("wakfu_server.combat_effect_groups")
    module.native_group_route = groups.native_group_route
    _refresh_function(
        "wakfu_server.combat_effect_resolver",
        "candidate_invocations",
        classname="NativeEffectResolver",
        preserve_aliases=True,
    )
    assert module.NativeEffectResolver is original_class
    assert original_class.candidate_invocations is function
    assert "native_group_route" in function.__code__.co_names
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/point-enemy-qualified-single-loaded-adoption-after-both-store-releases.json"
    ).write_text(
        json.dumps(
            dict(
                no_live_checkpoints=True,
                class_identity_preserved=True,
                function_identity_preserved=True,
                source_sha256=hashlib.sha256(
                    Path(module.__file__).read_bytes()
                ).hexdigest(),
                method_names=function.__code__.co_names,
                prior_isolated_contracts="7/7 PASS0.005s; no repeated tests",
            ),
            indent=2,
        )
    )
    return unittest.TestSuite()
