"""Preserve admitted hooks around one isolated policy contract."""
import importlib
from pathlib import Path
import unittest


def qualify():
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    namespace = {}
    pin = Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/bind-roles257-source-pin-before258.py"
    )
    exec(compile(pin.read_text(), str(pin), "exec"), roles.__dict__, namespace)
    roles.bind_roles.__code__ = namespace["bind_roles"].__code__
    helper = importlib.reload(
        importlib.import_module("_qualification_recipient258_isolated")
    )
    suite = helper.qualify_failed()
    # The outer runner expands its direct input suite once. Keep the restoring
    # suite nested so its finally block actually executes.
    return unittest.TestSuite([suite])
