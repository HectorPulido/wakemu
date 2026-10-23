"""Start the sole earned Faille caller with its explicit scoped retention opt-in."""
import importlib, unittest


def qualify():
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    replay = importlib.import_module(
        "wakfu_server.combat_event_replay"
    ).NativeEventReplay.__call__
    assert "freeze_owned_start_binding" in roles.bind_roles.__code__.co_names
    assert "owned_start_caster" in replay.__code__.co_names
    module = importlib.reload(
        importlib.import_module("test_nox_owned_start_faille_producer")
    )
    module.RETAIN_COMPONENT = True
    return unittest.defaultTestLoader.loadTestsFromName(
        "NoxOwnedStartFailleProducerTests.test_first_native_weapon_paid_condition_and_owned_end_earn_faille",
        module,
    )
