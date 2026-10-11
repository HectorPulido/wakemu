"""Read-only diagnostics for actual Sadida scenarios; no execution bypasses."""
import gc

gc.disable()
import json
import os
import sys
import unittest
from unittest.mock import patch
from wakfu_server.combat_state_handler import NativeStateHandler
from wakfu_server.combat_runtime_adapter import (
    NativeServerRuntimeAdapter as RuntimeAdapter,
)

original_parameters = NativeStateHandler._parameters
original_condition = RuntimeAdapter.condition


def parameters(self, effect, values, invocation, **kwargs):
    if invocation.reference in (378060, 378061, 378068, 378069):
        print(
            "SADIDA_BIRTH_STATE",
            json.dumps(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    cell=invocation.cell,
                    level=invocation.level,
                    parameters=values["parameters"],
                    criteria=effect["criteria"],
                )
            ),
            flush=True,
        )
    try:
        return original_parameters(self, effect, values, invocation, **kwargs)
    except Exception:
        print(
            "SADIDA_STATE_FAILURE",
            json.dumps(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    cell=invocation.cell,
                    level=invocation.level,
                    parameters=values["parameters"],
                    criteria=effect["criteria"],
                )
            ),
            flush=True,
        )
        raise


def condition(self, *args, **kwargs):
    try:
        return original_condition(self, *args, **kwargs)
    except Exception:
        invocation = args[3]
        effect = args[2]
        print(
            "SADIDA_CONDITION_FAILURE",
            json.dumps(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    cell=invocation.cell,
                    level=invocation.level,
                    criteria=effect["criteria"],
                    trigger=getattr(invocation, "native_trigger_context", None),
                )
            ),
            flush=True,
        )
        raise


with patch.object(NativeStateHandler, "_parameters", parameters), patch.object(
    RuntimeAdapter, "condition", condition
):
    suite = unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.stdout.flush()
sys.stderr.flush()
os._exit(0 if result.wasSuccessful() else 1)
