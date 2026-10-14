"""Native eYy groups retain actual recipient/handler authority in NPC preflight."""
import unittest
from types import SimpleNamespace as NS
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_npc_area_preflight import qualified_roots, eligible_recipients


class NpcTransferAreaTests(unittest.TestCase):
    def fixture(self):
        mask = (1 << 50) | 9
        base = dict(
            children=[],
            criteria="",
            area_native="point",
            application_flag="NONE",
            removal_flag="NONE",
            native_target_selector=dict(class_="fcE"),
        )
        base["native_target_selector"] = {"class": "fcE", "mask": mask}
        first = dict(base, effect_class=3)
        second = dict(
            base, effect_class=24, native_target_selector={"class": "fcE", "mask": 8194}
        )
        root = dict(
            base,
            effect_class=865,
            children=[2, 3],
            area_class="anH",
            area_native="ring-2-4",
        )
        effects = {"1": root, "2": first, "3": second}
        caster = NS(id=-200, controlled=False, hp=100, position=(0, 0, 0), direction=0)
        fight = NS(actors={-200: caster, 7: NS(id=7, hp=60)})
        return effects, fight

    def test_authentic_group_ring_and_children_are_required(self):
        effects, fight = self.fixture()
        request = dict(actor_id=-200, target=(0, 0, 0))
        rule = dict(minimum=0, maximum=0, roots=[1])
        self.assertIsNotNone(qualified_roots(fight, request, rule, effects))
        effects["2"]["children"] = [99]
        self.assertIsNone(qualified_roots(fight, request, rule, effects))

    def test_original_child_native_eligibility_is_preserved(self):
        effects, fight = self.fixture()
        inv = EffectInvocation(1, 50, -200, 7, (0, 0, 0))
        seen = []
        handler = NS(
            native_runner_value_verified=True,
            native_eligibility=lambda effect, invocation: seen.append(
                (effect, invocation)
            )
            or False,
        )
        dispatcher = NS(
            effects=effects,
            resolve=lambda *a: [inv],
            handlers={3: handler, 24: object()},
            group_retention=object(),
            transfer_probability=lambda chance: True,
            condition_context=lambda i: None,
        )
        self.assertEqual(eligible_recipients(dispatcher, effects["1"], inv, fight), ())
        self.assertIs(seen[0][0], effects["2"])
        self.assertEqual(seen[0][1].reference, 2)

    def test_missing_callback_or_group_authority_is_rejected(self):
        effects, fight = self.fixture()
        inv = EffectInvocation(1, 50, -200, 7, (0, 0, 0))
        dispatcher = NS(
            effects=effects,
            resolve=lambda *a: [inv],
            handlers={3: object(), 24: object()},
            group_retention=object(),
            transfer_probability=lambda chance: True,
        )
        with self.assertRaisesRegex(ValueError, "child handler"):
            eligible_recipients(dispatcher, effects["1"], inv, fight)
