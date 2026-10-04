import unittest
from unittest.mock import patch
from wakfu_server.combat_state import Actor
from wakfu_server.combat_actor_snapshot import (
    build_player_snapshot,
    build_npc_snapshot,
    native_actor_catalog,
)
from wakfu_server.equipment_stats import effective_character
from wakfu_server.health import maximum
from wakfu_server.wire import proto_field


class ActorSnapshotTests(unittest.TestCase):
    def player(self, equipment=False):
        char = dict(
            id=1,
            breed=8,
            level=6,
            hp=41,
            max_hp=maximum(8, 6),
            builds={},
            inventory_items=[],
        )
        if equipment:
            char["builds"] = {
                0: dict(
                    equipment=proto_field(
                        10, proto_field(8, 1000) + proto_field(16, 4)
                    ).hex()
                )
            }
            char["inventory_items"] = [
                dict(uid=1000, character_id=1, reference=2021, quantity=1)
            ]
        char = effective_character(char)
        actor = Actor(
            1,
            0,
            (0, 0, 0),
            41,
            7 if equipment else 6,
            3,
            0,
            6,
            owner_id=1,
            controlled=True,
            max_hp=char["max_hp"],
        )
        return char, actor

    def test_owned_build_native_defaults_and_one_time_install(self):
        char, actor = self.player(True)
        snap = build_player_snapshot(
            char, actor, wp_current=6, wp_maximum=6, running_effects=()
        )
        self.assertEqual((snap.stats[9], snap.stats[20], snap.stats[2]), (5, 9, 7))
        self.assertEqual(
            (snap.stats[92], snap.maxima[92], snap.stats[97], snap.stats[100]),
            (0, 0, 0, 0),
        )
        self.assertEqual((snap.physical_radius, snap.frozen), (0, frozenset()))
        self.assertEqual((snap.minima[20], snap.maxima[20]), (-5000, 50000))
        snap.install(actor)
        self.assertEqual(actor.effect_stats, snap.stats)
        self.assertEqual(actor.spell_ap_cost_modifiers, {})
        with self.assertRaises(ValueError):
            snap.install(actor)

    def test_existing_cost_modifier_snapshot_is_never_reset(self):
        char, actor = self.player()
        self.assertIsNone(actor.spell_ap_cost_modifiers)
        actor.spell_ap_cost_modifiers = {8: -1}
        with self.assertRaises(ValueError):
            build_player_snapshot(
                char, actor, wp_current=6, wp_maximum=6, running_effects=()
            )
        self.assertEqual(actor.spell_ap_cost_modifiers, {8: -1})

    def test_unknown_effects_and_unsupported_owned_sources_rejected(self):
        char, actor = self.player()
        with self.assertRaises(ValueError):
            build_player_snapshot(
                char, actor, wp_current=6, wp_maximum=6, running_effects=None
            )
        with self.assertRaises(ValueError):
            build_player_snapshot(
                char, actor, wp_current=6, wp_maximum=6, running_effects=(123,)
            )
        with patch(
            "wakfu_server.combat_actor_snapshot.bonuses",
            return_value=dict(unsupported=["unknown"]),
        ):
            with self.assertRaises(ValueError):
                build_player_snapshot(
                    char, actor, wp_current=6, wp_maximum=6, running_effects=()
                )

    def test_every_npc_native_maximum_level_fixture(self):
        catalog = native_actor_catalog()
        tested = 0
        for reference, profile in catalog["npc_profiles"].items():
            expected = {int(k): v for k, v in profile["at_maximum_level"].items()}
            if (
                expected[1]["current"] <= 0
                or min(expected[k]["current"] for k in (2, 3, 4)) < 0
            ):
                continue
            level = profile["maximum_level"]
            if level <= 0:
                continue
            actor = Actor(
                -1,
                1,
                (0, 0, 0),
                expected[1]["current"],
                expected[2]["current"],
                expected[3]["current"],
                expected[35]["current"],
                level,
                max_hp=expected[1]["maximum"],
            )
            snap = build_npc_snapshot(
                dict(id=-1, ref=int(reference)),
                actor,
                wp_current=expected[4]["current"],
                wp_maximum=expected[4]["maximum"],
                running_effects=(),
                catalog=catalog,
            )
            for k, row in expected.items():
                self.assertEqual(
                    (snap.stats[k], snap.minima[k], snap.maxima[k]),
                    (row["current"], row["minimum"], row["maximum"]),
                    (reference, k),
                )
            tested += 1
        self.assertGreater(tested, 2000)

    def test_live_resources_do_not_reset_damage_or_spending(self):
        char, actor = self.player()
        actor.hp = 20
        actor.ap = 2
        snap = build_player_snapshot(
            char, actor, wp_current=3, wp_maximum=6, running_effects=()
        )
        self.assertEqual((snap.stats[1], snap.stats[2], snap.stats[4]), (20, 2, 3))
        actor.ap -= 1
        with self.assertRaises(ValueError):
            snap.install(actor)

    def test_install_rejects_maximum_changes_and_wp_requires_ints(self):
        char, actor = self.player()
        snap = build_player_snapshot(
            char, actor, wp_current=3, wp_maximum=6, running_effects=()
        )
        actor.max_hp += 1
        with self.assertRaises(ValueError):
            snap.install(actor)
        actor.max_hp -= 1
        for current, maximum in ((True, 6), (3, False), (7, 6), (3, 21)):
            with self.assertRaises(ValueError):
                build_player_snapshot(
                    char,
                    actor,
                    wp_current=current,
                    wp_maximum=maximum,
                    running_effects=(),
                )

    def test_fight_initialization_is_atomic_and_seeds_owned_uid(self):
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_state import Fight
        from wakfu_server.monsters import owned_instance

        char, pc = self.player()
        monster = owned_instance(1, 8, -1, map_id=1, x=1, y=0, z=0)
        npc = Actor(
            -1,
            1,
            (1, 0, 0),
            monster["hp"],
            monster["ap"],
            monster["mp"],
            monster["initiative"],
            monster["level"],
        )
        fight = Fight(
            99,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        kwargs = dict(
            characters={pc.id: char},
            monsters={npc.id: monster},
            wp_resources={pc.id: (6, 6), npc.id: (monster["wp"], monster["wp"])},
            running_effects={pc.id: (), npc.id: ()},
            initial_effect_uid=1,
        )
        bad = dict(monster, ref=32767)
        with self.assertRaises(ValueError):
            initialize_fight_snapshots(fight, **dict(kwargs, monsters={npc.id: bad}))
        self.assertIsNone(pc.effect_stats)
        self.assertIsNone(npc.effect_stats)
        self.assertIsNone(fight.native_effect_uid_next)
        initialized = initialize_fight_snapshots(fight, **kwargs)
        self.assertEqual(set(initialized), {1, -1})
        self.assertIsNotNone(pc.effect_stats)
        self.assertIsNotNone(npc.effect_stats)
        self.assertEqual(fight.allocate_effect_uid(), 1)
        with self.assertRaises(ValueError):
            initialize_fight_snapshots(fight, **kwargs)
