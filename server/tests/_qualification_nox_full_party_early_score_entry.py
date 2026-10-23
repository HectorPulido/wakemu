"""Load the sole authorized complete native-party paid victory attempt."""
import importlib.util, sys


def qualify():
    for name in (
        "test_nox_cube24_fixed12_joint",
        "test_nox_prelude_five_modes_and_polary",
    ):
        module = sys.modules.get(name)
        assert module is None or not module.retained_components
    rushu = sys.modules.get("test_rushu_native_party_phase_one")
    assert rushu is None or rushu.RUSHU_ACTUAL_CHECKPOINT is None
    key = "_private_qualify_nox_full_party_early_score"
    spec = importlib.util.spec_from_file_location(
        key,
        ".runtime/staging/nox-cube24-fixed12-joint/qualify_nox_full_party_early_score.py",
    )
    helper = importlib.util.module_from_spec(spec)
    sys.modules[key] = helper
    spec.loader.exec_module(helper)
    return helper.qualify()
