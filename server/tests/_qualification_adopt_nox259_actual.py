"""Adopt the admitted Nox START policy without replacing public classes."""
import hashlib, importlib, json, unittest
from pathlib import Path
from _qualification_resumed_scopes import _refresh_function


def refresh():
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    source = Path(roles.__file__).read_text()
    assert "freeze_owned_start_binding" in source
    assert "freeze_encounter_seed" not in source
    importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_owned_start_binding")
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
    replay = importlib.import_module(
        "wakfu_server.combat_event_replay"
    ).NativeEventReplay.__call__
    assert "owned_start_caster" in replay.__code__.co_names
    output = Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components"
    )
    output.joinpath("bind-roles259-source-pin-before260.py").write_text(source)
    output.joinpath("nox259-loaded-role-and-replay-proof.json").write_text(
        json.dumps(
            dict(
                role_source_sha=hashlib.sha256(source.encode()).hexdigest(),
                role_names=roles.bind_roles.__code__.co_names,
                replay_names=replay.__code__.co_names,
            ),
            indent=2,
        )
    )
    return unittest.TestSuite()
