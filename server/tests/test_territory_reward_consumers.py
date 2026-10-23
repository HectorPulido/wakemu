"""Native regional penalties must reach authoritative reward inputs."""

from decimal import Decimal
from types import SimpleNamespace
import unittest

from wakfu_server.combat_actor_snapshot import build_player_snapshot
from wakfu_server.combat_drops import native_prospection_bonus, plan_player_drops
from wakfu_server.combat_state import Actor
from wakfu_server.equipment_stats import effective_character
from wakfu_server.health import maximum
from wakfu_server.reward_policy import xp_amount
from wakfu_server.territory_bonuses import state_effects, stat_bonuses


class TerritoryRewardConsumerTests(unittest.TestCase):
    def test_native_dissatisfaction_reaches_actor_loot_gate_and_combat_xp(self):
        region = dict(state_id=1917, effects=state_effects(0, 1)["effects"])
        character = effective_character(
            dict(
                id=7,
                breed=8,
                level=7,
                hp=41,
                max_hp=maximum(8, 7),
                builds={},
                inventory_items=[],
                territory_stat_bonuses=stat_bonuses(region, health_policy={"1917": 0}),
            )
        )
        actor = Actor(
            7,
            0,
            (0, 0, 0),
            41,
            6,
            3,
            0,
            7,
            owner_id=1,
            controlled=True,
            max_hp=character["max_hp"],
        )
        build_player_snapshot(
            character,
            actor,
            wp_current=6,
            wp_maximum=6,
            running_effects=(),
        ).install(actor)
        self.assertEqual((actor.effect_stats[33], actor.effect_stats[36]), (-10, -10))
        self.assertEqual(native_prospection_bonus(actor), -10)

        row = dict(
            reference_id=2026,
            probability="0.01",
            roll_count=-1,
            quantity_min=1,
            quantity_max=1,
            is_loot_table=False,
            complex_criteria=False,
            native_csE=-1,
            native_csF=100,
            conditions=[],
        )
        args = dict(
            monsters=[dict(actor_id=-11, reference=1)],
            character_id=7,
            can_loot=True,
            fight_context={},
            rng=lambda upper: upper - 1,
            catalog=dict(source_sha256="a" * 64, monsters={1: [row]}),
        )
        baseline = plan_player_drops(**args, prospecting_bonus=0)
        self.assertEqual(len(baseline), 1)
        self.assertEqual(baseline[0].raw_probability, Decimal("0.01"))
        # The existing probability floor stays neutral; the separate native
        # threshold still receives raw PP (90), below this row's threshold100.
        self.assertEqual(
            plan_player_drops(
                **args, prospecting_bonus=native_prospection_bonus(actor)
            ),
            (),
        )
        self.assertEqual(
            native_prospection_bonus(
                SimpleNamespace(effect_stats={33: 30 + actor.effect_stats[33]})
            ),
            20,
        )

        context = dict(
            winner_team=0,
            challenge_percent=0,
            star_percent=0,
            winners=[
                dict(
                    level=7,
                    player=True,
                    eligible=True,
                    character_id=7,
                    wisdom=actor.effect_stats[36],
                )
            ],
            losers=[dict(level=4, monster_reference=500)],
        )
        xp_args = dict(
            character_id=7, group_xp=433, xp_rate_bp=10000, conquest_rate_bp=10000
        )
        self.assertEqual(xp_amount(context=context, **xp_args), 497)
        context["winners"][0]["wisdom"] = 0
        self.assertEqual(xp_amount(context=context, **xp_args), 553)
