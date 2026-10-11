"""Real activated NPC controller ownership excludes players and summons."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_npc_ai_initialization import initial_ai_actors
from wakfu_server.combat_actor import _ai_control_byte


class NpcAIInitializationTests(unittest.TestCase):
    def selected(
        self, *, controlled=False, level=3, summons=None, action_book=None, enabled=True
    ):
        actor = SimpleNamespace(
            controlled=controlled,
            effective_level=level,
            native_summon_action_book=action_book,
        )
        fight = SimpleNamespace(
            actors={-200: actor}, native_summon_registrations=summons or {}
        )
        policy = dict(
            schema="native-npc-activation-v1",
            legacy_spell_ids=[],
            enabled_monsters={"5710": dict(min_level=1, max_level=3, spell_ids=[4641])}
            if enabled
            else {},
        )
        with patch(
            "wakfu_server.combat_npc_attack.npc_spell_catalog",
            return_value={"activation_policy": policy},
        ), patch(
            "wakfu_server.monsters.native_abilities", return_value=[{"spell_id": 4641}]
        ):
            return initial_ai_actors(fight, {-200: {"ref": 5710}})

    def test_activated_owned_ordinary_npc_receives_controller(self):
        self.assertEqual(self.selected(), frozenset({-200}))
        self.assertEqual(_ai_control_byte(True), b"\x01")
        self.assertEqual(_ai_control_byte(False), b"\x00")

    def test_unactivated_and_out_of_range_npcs_keep_default(self):
        self.assertEqual(self.selected(enabled=False), frozenset())
        self.assertEqual(self.selected(level=4), frozenset())

    def test_players_and_summons_keep_their_existing_controller_path(self):
        self.assertEqual(self.selected(controlled=True), frozenset())
        self.assertEqual(self.selected(summons={-200: {"owner": 7}}), frozenset())
        self.assertEqual(self.selected(action_book={"profile": 5710}), frozenset())

    def test_empty_monster_scope_does_not_read_activation_catalog(self):
        with patch(
            "wakfu_server.combat_npc_attack.npc_spell_catalog",
            side_effect=AssertionError("No NPC controller needed"),
        ):
            self.assertEqual(initial_ai_actors(SimpleNamespace(), {}), frozenset())

    def test_ai_assignment_rebuilds_initial_wire_without_initial_states(self):
        from wakfu_server.combat_bootstrap import should_rebuild_placement

        fight = SimpleNamespace(
            native_npc_initialization_receipts={},
            native_npc_ai_actors=frozenset({-200}),
        )
        self.assertTrue(should_rebuild_placement(fight, []))
        fight.native_npc_ai_actors = frozenset()
        self.assertFalse(should_rebuild_placement(fight, []))

    def test_fresh_snapshot_assigns_only_selected_npc_and_publishes_actual_wire(self):
        from test_combat_actor_snapshot import ActorSnapshotTests
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.monsters import owned_instance
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_actor import actual_monster_actor_stats

        character, player = ActorSnapshotTests().player()
        monster = owned_instance(1, 8, -200, map_id=1, x=1, y=0, z=0)
        npc = Actor(
            -200,
            1,
            (1, 0, 0),
            monster["hp"],
            monster["ap"],
            monster["mp"],
            monster["initiative"],
            8,
        )
        fight = Fight(
            99,
            [player, npc],
            {player.position, npc.position},
            {0: {player.position}, 1: {npc.position}},
        )
        with patch(
            "wakfu_server.combat_npc_ai_initialization.initial_ai_actors",
            return_value=frozenset({npc.id}),
        ):
            initialize_fight_snapshots(
                fight,
                characters={player.id: character},
                monsters={npc.id: monster},
                wp_resources={
                    player.id: (6, 6),
                    npc.id: (monster["wp"], monster["wp"]),
                },
                running_effects={player.id: (), npc.id: ()},
                initial_effect_uid=1,
            )
        self.assertTrue(npc.native_controlled_by_ai)
        self.assertFalse(player.native_controlled_by_ai)
        self.assertEqual(fight.native_npc_ai_actors, frozenset({npc.id}))
        with patch(
            "wakfu_server.combat_actor.monster_actor_stats",
            return_value=b"actual-npc-wire",
        ) as encoder:
            self.assertEqual(
                actual_monster_actor_stats(
                    monster,
                    npc,
                    fight.id,
                    wp_current=monster["wp"],
                    wp_maximum=monster["wp"],
                ),
                b"actual-npc-wire",
            )
            self.assertIs(encoder.call_args.kwargs["native_controlled_by_ai"], True)
