"""Representative DJ setup boundaries, without a synthetic played encounter."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_native_dj_dance as dj
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_npc_area_preflight import qualified_roots, eligible_recipients
from wakfu_server.combat_state_ledger import RunningState


class BilbyzaDjSetupTests(unittest.TestCase):
    def test_real_source_global_ordered_apply_remove_group_qualifies_without_changing_children(
        self,
    ):
        # Versioned native fixture stores the original minigame prototype
        # identities; exact root/children are the small reviewed test input.
        root = dict(
            effect_class=330,
            parameter_count=1,
            parameters=[0.0, 0.0],
            children=list(range(2, 11)),
            criteria="",
            area_class="anA",
            area_native="empty",
            native_target_selector={"class": "fcE", "mask": (1 << 47) | 8},
            application_flag="NONE",
            removal_flag="NONE",
        )
        effects = {"1": root}
        for identity in root["children"]:
            effects[str(identity)] = dict(
                effect_class=304 if identity == 2 else 321,
                children=[],
                criteria="",
                area_class="anD",
                area_native="point",
                target_masks=[None] * 7,
                native_target_selector={"class": "fcE", "mask": 1},
                application_flag="NONE",
                removal_flag="NONE",
            )
        original = deepcopy(effects)
        caster = SimpleNamespace(
            id=202, controlled=False, hp=1825, position=(0, 0, 0), direction=0
        )
        owner = SimpleNamespace(id=101, hp=1825)
        fight = SimpleNamespace(actors={202: caster, 101: owner})
        self.assertEqual(
            qualified_roots(
                fight,
                dict(actor_id=202, target=caster.position),
                dict(minimum=0, maximum=0, roots=[1]),
                effects,
            ),
            {1: root},
        )
        invocation = EffectInvocation(1, 100, 202, 202, caster.position)
        dispatcher = SimpleNamespace(
            effects=effects,
            handlers={304: object(), 321: object()},
            resolve=lambda *_: (EffectInvocation(1, 100, 202, 101, caster.position),),
            condition_context=lambda *_: None,
        )
        with patch(
            "wakfu_server.combat_conditions.evaluate_condition", return_value=True
        ):
            self.assertEqual(
                eligible_recipients(dispatcher, root, invocation, fight), (101,)
            )
        self.assertEqual(effects, original)
        compiled_effects = {
            key: dict(row, target_masks=tuple(row["target_masks"]))
            if "target_masks" in row
            else row
            for key, row in effects.items()
        }
        self.assertEqual(
            qualified_roots(
                fight,
                dict(actor_id=202, target=caster.position),
                dict(minimum=0, maximum=0, roots=[1]),
                compiled_effects,
            ),
            {1: root},
        )
        effects["11"] = dict(root, parameter_count=6, criteria="False")
        self.assertEqual(
            qualified_roots(
                fight,
                dict(actor_id=202, target=caster.position),
                dict(minimum=0, maximum=0, roots=[11, 1]),
                effects,
            ),
            {1: root},
        )
        effects["2"]["target_masks"][5] = [1001]
        self.assertIsNone(
            qualified_roots(
                fight,
                dict(actor_id=202, target=caster.position),
                dict(minimum=0, maximum=0, roots=[1]),
                effects,
            )
        )

    def test_setup_waits_for_native_order_after_1941_and_survives_json_checkpoint(self):
        def state(uid, reference, level, caster=202):
            return RunningState(
                uid, reference, level, caster, 101, 0, "none", False, (), 0, False, None
            )

        challenge = state(20, 1941, 1)
        owner = SimpleNamespace(
            id=101,
            owner_id=42,
            controlled=True,
            team=0,
            state_ledger=SimpleNamespace(entries=[challenge]),
        )
        caster = SimpleNamespace(id=202, team=1)
        fight = SimpleNamespace(
            actors={101: owner, 202: caster}, native_active_spell_id=3700
        )
        handler = SimpleNamespace(
            fight=fight, packets=[], action_id=1, allocate_uid=lambda: 30
        )
        options = dict(
            actor_reference=lambda actor: 2502 if actor is caster else None,
            actor_real_level=lambda actor: 85 if actor is owner else 100,
            active_roots=(95219,),
        )
        with patch.object(dj, "install_control_book", return_value=()) as grant:
            self.assertIsNone(
                dj.observe_native_state(
                    handler,
                    {"effect_class": 304},
                    EffectInvocation(95845, 1, 202, 101, (0, 0, 0)),
                    challenge,
                    **options
                )
            )
            grant.assert_not_called()
            fight.native_dj_setup_pending = json.loads(
                json.dumps(fight.native_dj_setup_pending)
            )
            fight.native_active_spell_id = None
            for index, reference in enumerate([1932, 1943, 1934, 1945]):
                entry = state(31 + index, reference, 1 + index, caster=101)
                owner.state_ledger.entries.append(entry)
                result = dj.observe_native_state(
                    handler,
                    {"effect_class": 304},
                    EffectInvocation(93252, 1, 101, 101, (0, 0, 0)),
                    entry,
                    **options
                )
                if index < 3:
                    self.assertIsNone(result)
                    grant.assert_not_called()
            self.assertEqual(result["index"], 0)
            self.assertEqual([row["level"] for row in result["expected"]], [1, 2, 3, 4])
            self.assertIsNone(fight.native_dj_setup_pending)
            grant.assert_called_once()


if __name__ == "__main__":
    unittest.main()
