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
    from wakfu_server.combat_state_managers import _area_pv_scopes

    preview, plan, effect, invocation = args[:4]
    if getattr(invocation, "reference", None) in (377828, 378544, 377823, 378505):
        print(
            "SADIDA_GROUP_PV",
            json.dumps(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    active=[
                        (uid, row.get("reference"))
                        for uid, row in preview.native_effect_areas.items()
                    ],
                    scoped=[
                        (row.get("uid"), row.get("reference"))
                        for owner, row in _area_pv_scopes.get()
                        if owner is preview
                    ],
                )
            ),
            flush=True,
        )
    try:
        context = original_condition(self, *args, **kwargs)
        if getattr(invocation, "reference", None) == 379581:
            from wakfu_server.combat_conditions import evaluate_condition

            leaves = (
                "NbAreasWithBaseId(1835)>0",
                "IsOwnSpecificArea(1835)",
                "IsSpellInDeck(8151)",
                'IsOnSpecificEffectArea("target",1836,True)',
                'IsOnSpecificEffectArea("target",1850,True)',
            )
            observed = {}
            for leaf in leaves:
                try:
                    observed[leaf] = evaluate_condition(leaf, context)
                except Exception as error:
                    observed[leaf] = type(error).__name__ + ": " + str(error)
            print(
                "SADIDA_8151_LEAVES",
                json.dumps(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        cell=invocation.cell,
                        leaves=observed,
                        areas=[
                            dict(
                                uid=uid,
                                reference=row.get("reference"),
                                owner=row.get("owner_id"),
                                cell=row.get("cell"),
                            )
                            for uid, row in preview.native_effect_areas.items()
                        ],
                    )
                ),
                flush=True,
            )
        return context
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
