"""Actual Eliotrope portal replacement through the native passive branch."""
import os
import unittest
import test_combat_eliotrope_runtime as runtime


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropePortalLifecycleRuntimeTests(unittest.TestCase):
    fixture = runtime.EliotropeRuntimeTests.fixture
    cast = runtime.EliotropeRuntimeTests.cast
    next_owned_turn = runtime.EliotropeRuntimeTests.next_owned_turn
    place_portal = runtime.EliotropeRuntimeTests.place_portal

    def test_portalivio_replaces_at_native_two_portal_limit(self):
        data = self.fixture(passives=(7206,))
        for index in range(2):
            tx = self.place_portal(
                data,
                near=data[2].actors[7 if index == 0 else -7].position,
                action_id=11 + index,
            )
            data = (*data[:2], tx.fight, *data[3:])
        before = {
            a["uid"]
            for a in data[2].native_effect_areas.values()
            if a.get("reference") == 823
        }
        self.assertEqual(len(before), 2)
        self.next_owned_turn(data)
        from unittest.mock import patch
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        selected = {
            145038,
            145048,
            346477,
            395958,
            145047,
            395962,
            395964,
            346478,
            346487,
            346488,
            346490,
        }
        calls, diagnostics, candidates = [], [], []
        from wakfu_server.combat_multiple_target_group import select_multiple_targets

        def multiple(values, population, **kwargs):
            population = tuple(population)
            tracked = any(item.reference == 346478 for item in population)
            if tracked or not population:
                candidates.append(
                    dict(
                        parameters=values["parameters"],
                        targets=[
                            (item.reference, item.target_id, item.cell)
                            for item in population
                        ],
                    )
                )
            condition = kwargs["condition"]

            def checked(item):
                result = condition(item)
                if item.reference == 346478:
                    candidates.append(
                        dict(
                            criterion_target=item.target_id,
                            cell=item.cell,
                            accepted=result,
                        )
                    )
                return result

            return select_multiple_targets(
                values, population, **dict(kwargs, condition=checked)
            )

        original = EffectDispatcher.execute

        def execute(dispatcher, invocation, **kwargs):
            result = original(dispatcher, invocation, **kwargs)
            if invocation.reference in selected and len(calls) < 256:
                calls.append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        cell=invocation.cell,
                        level=invocation.level,
                        criteria=dispatcher.effects[str(invocation.reference)].get(
                            "criteria"
                        ),
                        result=result,
                    )
                )
            return result

        def diagnostic(**row):
            if row.get("effect_reference") in selected and len(diagnostics) < 256:
                diagnostics.append(row)

        try:
            with patch.object(EffectDispatcher, "execute", execute), patch(
                "wakfu_server.combat_multiple_target_group.select_multiple_targets",
                multiple,
            ), combat_diagnostic_scope(diagnostic, limit=4096):
                tx = self.place_portal(
                    data, near=data[2].actors[7].position, action_id=20
                )
        except AssertionError as error:
            self.fail(
                str(
                    dict(
                        reason=str(error),
                        calls=calls,
                        diagnostics=diagnostics,
                        candidates=candidates,
                    )
                )
            )
        after = {
            a["uid"]
            for a in tx.fight.native_effect_areas.values()
            if a.get("reference") == 823
        }
        self.assertEqual(len(after), 2)
        self.assertEqual(len(after - before), 1)
        self.assertEqual(len(before - after), 1)
        self.assertEqual(
            {
                a["uid"]
                for a in data[2].native_effect_areas.values()
                if a.get("reference") == 823
            },
            before,
        )

    def test_actual_portal_checkpoint_preserves_owned_native_area(self):
        import json
        from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot

        data = self.fixture()
        tx = self.place_portal(data, near=data[2].actors[7].position, action_id=11)
        saved = snapshot(tx.fight)
        restored = Checkpoints._read_snapshot(json.loads(json.dumps(saved)))
        rows = {
            uid: row
            for uid, row in saved["native_effect_areas"].items()
            if row.get("reference") == 823
        }
        self.assertEqual(len(rows), 1)
        for uid, row in rows.items():
            self.assertEqual(restored["native_effect_areas"][uid], row)
            self.assertEqual(row["owner_id"], 7)
            self.assertEqual(row["native_type_id"], 19)
