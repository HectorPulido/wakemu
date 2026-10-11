"""Actual native Xelor gameplay regression, staged outside the server freeze."""
import unittest
import json
import math
from unittest.mock import patch
from wakfu_server.combat_damage_handler import NativeDamageHandler
import test_xelor_runtime_pipeline as helpers
import test_combat_xelor_own_hour_runtime as paths


class XelorDejaVuRuntimeTests(unittest.TestCase):
    def test_deja_vu_reduces_actual_damage_only_on_odd_native_hour(self):
        h = helpers.XelorRuntimePipelineTests()
        rows = []
        for passive in (False, True):
            for odd in (False, True):
                data = h.fixture(level=60, passives=(7185,) if passive else ())
                # Select a lawful dial placement whose native swap leaves legal754 range.
                # No movement/resource overrides; this avoids genuine adjacent tackle costs.
                source = data[2]
                origin = source.actors[7].position
                candidates = sorted(
                    source.walkable,
                    key=lambda c: (abs(c[0] - origin[0]) + abs(c[1] - origin[1]), c),
                )
                chosen = None
                for cell in candidates:
                    distance = abs(cell[0] - origin[0]) + abs(cell[1] - origin[1])
                    if not 1 <= distance <= 3 or (
                        cell[0] != origin[0] and cell[1] != origin[1]
                    ):
                        continue
                    try:
                        candidate = h.cast(data, 5345, cell)
                    except ValueError:
                        continue
                    preview = candidate.fight
                    own, enemy = preview.actors[7].position, preview.actors[-7].position
                    distance = abs(own[0] - enemy[0]) + abs(own[1] - enemy[1])
                    hours = [
                        r
                        for r in preview.native_effect_areas.values()
                        if r.get("owner_id") == 7 and 1546 <= r["reference"] <= 1557
                    ]
                    if len(hours) == 12 and 2 <= distance <= 4 and own[2] == enemy[2]:
                        chosen = candidate
                        break
                assert (
                    chosen is not None
                ), "No full native dial placement with lawful754 range"
                data = h.adopt(data, chosen.fight)
                fight = data[2]
                if odd:
                    payment = h.cast(data, 775, fight.actors[-7].position, action_id=31)
                    data = h.adopt(data, payment.fight)
                before = data[2].actors[-7].hp
                modifiers = []
                original = NativeDamageHandler._calculate

                def observe(self, effect, invocation, **kwargs):
                    modifiers.append(kwargs.get("additional_final", 0))
                    return original(self, effect, invocation, **kwargs)

                with patch.object(NativeDamageHandler, "_calculate", observe):
                    attack = h.cast(
                        data, 754, data[2].actors[-7].position, action_id=32
                    )
                after = attack.fight.actors[-7].hp
                rows.append(
                    {
                        "passive": passive,
                        "odd": odd,
                        "hp_before": before,
                        "hp_after": after,
                        "modifiers": modifiers,
                        "damage": before - after,
                        "hour": h.states(attack.fight.actors[7])[6759],
                        "owner": attack.fight.actors[7].position,
                        "target": attack.fight.actors[-7].position,
                    }
                )
        print(json.dumps(rows))
        by = {(r["passive"], r["odd"]): r for r in rows}
        assert all(r["hp_after"] > 0 and r["damage"] > 0 for r in rows), rows
        assert by[True, False]["damage"] == by[False, False]["damage"], rows
        # Native UP.bt/GT.l uses stochastic floor/ceiling rounding, not truncation.
        expected = by[False, True]["damage"] * 0.75
        assert (
            math.floor(expected) <= by[True, True]["damage"] <= math.ceil(expected)
        ), rows
        for key, row in by.items():
            assert row["modifiers"] == ([-25] if key == (True, True) else [0]), rows
