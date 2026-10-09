"""Source-backed 4464 finisher tree and delivery boundary regressions."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from wakfu_server.characters.cosmetics import OwnedCosmetics
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
)
from wakfu_server.combat_cosmetic_conditions import (
    fresh_player_cosmetic_state,
    has_active_cosmetic,
    active_cosmetic_id,
)
from wakfu_server.combat_death_script import NativeDeathScriptHandler
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server.combat_finisher_events import prepare_owned_finisher
from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server import native_catalog


class OwnedFinisherTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        protocol = Path(__file__).parents[1] / "protocol"
        with native_catalog.open(
            protocol / "combat-state-definitions.json", "rt"
        ) as source:
            cls.catalog = json.load(source)
        cls.effects = cls.catalog["effects"]
        cls.states = cls.catalog["states"]

    def _context(
        self, selected=(20753,), *, model=2, turn=4, allies=0, ko=0, pvp=False
    ):
        selected = tuple(selected)
        active = {5: selected} if selected else {}
        actor = ConditionActor(
            actor_id=7,
            is_player=True,
            is_native_fighter=True,
            summon_count=0,
            world_properties=frozenset(),
            characteristics={"KO_TIME_BEFORE_DEATH": ko},
        )
        return ConditionContext(
            {"caster": actor, "target": actor},
            fight_current_table_turn=turn,
            allies_count_query=lambda selector: allies,
            fight_model_query=lambda: model,
            active_cosmetic_id_query=lambda category: active_cosmetic_id(
                SimpleNamespace(
                    is_native_fighter=True,
                    selected_values={5: selected},
                    active_cosmetics=active,
                ),
                category,
            ),
            has_active_cosmetic_query=lambda category, reference: has_active_cosmetic(
                SimpleNamespace(
                    is_native_fighter=True,
                    selected_values={5: selected},
                    active_cosmetics=active,
                ),
                category,
                reference,
            ),
            random_number_query=lambda maximum, exclusions: 0,
            pvp_query=lambda: pvp,
        )

    def test_4464_is_shared_by_every_installed_breed_and_keeps_native_tree(self):
        breeds = json.loads(
            native_catalog.read_text(
                Path(__file__).parents[1] / "protocol/breed-innate-definitions.json"
            )
        )["breeds"]
        self.assertEqual(len(breeds), 18)
        self.assertTrue(
            all(
                4464 in {row["reference"] for row in breed["innate_states"]}
                for breed in breeds
            )
        )
        root = self.effects["185234"]
        middle = self.effects["185235"]
        branch = self.effects["185727"]
        leaf = self.effects["185395"]
        self.assertEqual(self.states["4464"]["effect_ids"][0], 185234)
        self.assertEqual(root["children"], [185235])
        self.assertEqual(root["target_masks"][5], [1018, 1024])
        self.assertEqual(middle["target_masks"][5], [1012])
        self.assertIn(185727, self.effects["185236"]["children"])
        self.assertIn("GetFightCurrentTableTurn() > 3", branch["criteria"])
        self.assertIn(
            'GetAlliesCount("target") - NbSummons("target")', branch["criteria"]
        )
        self.assertIn("KO_TIME_BEFORE_DEATH", branch["criteria"])
        self.assertEqual(leaf["effect_class"], 1099)
        self.assertEqual(leaf["criteria"], "HasActiveCosmeticId(5, 20753)")
        self.assertEqual(leaf["parameters"][0], 1100010.0)

    def test_original_native_criteria_keep_turn_last_enemy_ko_pvp_and_cosmetic_guards(
        self,
    ):
        root = self.effects["185234"]["criteria"]
        group = self.effects["185727"]["criteria"]
        leaf = self.effects["185395"]["criteria"]

        self.assertTrue(evaluate_condition(root, self._context()))
        self.assertTrue(evaluate_condition(group, self._context()))
        self.assertTrue(evaluate_condition(leaf, self._context()))

        self.assertFalse(evaluate_condition(root, self._context(model=76)))
        self.assertFalse(evaluate_condition(root, self._context(selected=())))
        self.assertFalse(evaluate_condition(group, self._context(turn=3)))
        self.assertFalse(evaluate_condition(group, self._context(allies=1)))
        self.assertFalse(evaluate_condition(group, self._context(ko=1)))
        self.assertTrue(evaluate_condition(group, self._context(ko=1, pvp=True)))
        self.assertFalse(evaluate_condition(leaf, self._context(selected=(20754,))))

    def test_owned_account_tree_assigns_before_lethal_packet_and_cleans_after_l3(self):
        actor = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 1, True)
        opponent = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1)
        fight = Fight(
            71,
            [actor, opponent],
            {actor.position, opponent.position},
            {0: {actor.position}, 1: {opponent.position}},
        )
        fight.ready(1)
        fight.native_active_spell_id = -1
        character = {"id": 7, "account_id": 88}
        account = OwnedCosmetics(88, ((5, 20753, 0, 0),)).equip_finishers(
            character, (20753,)
        )
        character["owned_cosmetics"] = account.to_record()
        from wakfu_server.combat_cosmetic_conditions import (
            initialize_fresh_player_cosmetics,
        )

        initialize_fresh_player_cosmetics(actor, character)
        context = self._context()
        leaf = self.effects["185395"]
        handler_packets = []
        handler = NativeDeathScriptHandler(
            fight,
            handler_packets,
            action_id=5,
            allocate_uid=lambda: 901,
            context=lambda effect, invocation: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            rng=lambda: 0,
        )
        order = []
        cleanup_packets = []

        def replay(source, *, authority):
            source.validate()
            order.append((source.event_ids, source.channel))
            if source.event_ids == (1012,):
                self.assertTrue(
                    evaluate_condition(self.effects["185234"]["criteria"], context)
                )
                self.assertTrue(
                    evaluate_condition(self.effects["185727"]["criteria"], context)
                )
                self.assertTrue(evaluate_condition(leaf["criteria"], context))
                invocation = EffectInvocation(
                    185395, 1, 7, -7, fight.actors[-7].position
                )
                self.assertTrue(handler(leaf, {}, invocation))
                order.append(("assignment", handler_packets[-1][0]))
            elif source.event_ids == (1015,):
                # This boundary test models the evaluated cleanup packet; the
                # native end-to-end test verifies its real codec and placement.
                cleanup_packets.append((13560, b"\x00"))
            return ()

        source = NativeEventSource(
            900,
            339483,
            100,
            7,
            -7,
            actor.position,
            (1013,),
            6,
            -7,
            None,
            False,
            False,
            False,
            True,
        )
        event = prepare_owned_finisher(fight, source, replay=replay, authority=object())
        self.assertEqual(fight.actors[-7].native_death_script_id, 1100010)
        self.assertEqual(handler_packets[0][0], 12613)

        lifecycle = object.__new__(OrdinaryHealingEvents)
        lifecycle.replay = replay
        lifecycle.authority = object()
        lifecycle.preview = fight
        lifecycle.retention = SimpleNamespace(packets=cleanup_packets)
        lifecycle._queue_finisher_cleanup(event)
        order.append(("lethal_packet", 12613))
        lifecycle._finish_finisher_cleanup(event.uid)
        self.assertEqual(
            order,
            [
                ((1018,), 60),
                ((1012,), 60),
                ("assignment", 12613),
                ("lethal_packet", 12613),
                ((1015,), 40),
            ],
        )
        self.assertEqual(
            fight.native_finisher_after_death_packets["-7"],
            [[13560, "00"]],
        )


if __name__ == "__main__":
    unittest.main()
