"""Two actual Sadida owners isolate absorption and share friendly tree armor."""
import math
import os
import random
import struct
import unittest

from xelor_multiowner_fixture import TwoXelorFixture
from test_enutrof_remaining_companion_actions import (
    EnutrofRemainingCompanionActionsTests,
)


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaMultiownerConsequencesTests(unittest.TestCase):
    reach = EnutrofRemainingCompanionActionsTests.reach

    def fixture(self):
        fight, characters, monster, decks = TwoXelorFixture().fixture(
            caster_breed=10,
            second_player_breed=10,
            level=200,
            active_spells=(925,),
            second_player_spells=(921,),
            second_player_position=(-6, -7, -1),
            third_player_position=(-8, -6, -1),
            enemy_position=(-4, -7, -1),
            compact_arena=False,
            initialization_seed=17,
        )
        from wakfu_server.combat_server_spell import prepare_server_turn_start

        rng = random.Random(17)
        fight, _ = prepare_server_turn_start(
            characters[7],
            {-7: monster},
            fight,
            decks[7],
            actor_id=fight.current.id,
            action_id=4,
            rng=rng,
            area_callbacks=True,
            player_characters=characters,
            deck_blobs=decks,
        )
        return fight, characters, monster, decks, rng

    def cast(self, data, identity, reference, target):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.fight_checkpoint_store import snapshot

        fight, characters, monster, decks, rng = data
        self.reach(fight, characters, monster, decks, identity, rng)
        actor = fight.actors[identity]
        owner = (
            actor.native_summon_source["controller_id"]
            if getattr(actor, "native_summon_source", None)
            else identity
        )
        if owner != identity:
            uid = next(
                row["uid"]
                for row in actor_action_book(actor)["actions"]
                if row["reference"] == reference
            )
        else:
            grant = granted_spells(fight, owner).get(reference)
            uid = grant["uid"] if grant else (owner << 32) | reference

        def los(origin, destination, current):
            return authoritative_visible(
                characters[owner]["map_id"],
                origin,
                destination,
                current,
                blocking_footprints={
                    a.id: {a.position[:2]} for a in current.actors.values() if a.hp > 0
                },
            )

        before = snapshot(fight)
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        trace = []
        with combat_diagnostic_scope(lambda **row: trace.append(row), limit=4096):
            tx = prepare_server_spell(
                struct.pack(">qqiih", identity, uid, *target),
                characters[owner],
                {-7: monster},
                fight,
                characters[owner]["account_id"],
                decks[owner],
                action_id=80,
                line_of_sight=los,
                critical=False,
                rng=rng,
                player_characters=characters,
                deck_blobs=decks,
            )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(
            any(tx.outcomes),
            {
                "actor": identity,
                "reference": reference,
                "target": target,
                "resources": (actor.ap, actor.mp, actor.effect_stats[4]),
                "actors": [
                    (
                        a.id,
                        a.position,
                        a.hp,
                        [s.reference for s in a.state_ledger.entries],
                    )
                    for a in fight.actors.values()
                ],
                "areas": [
                    (row["uid"], row["reference"], row["cell"], row.get("owner_id"))
                    for row in fight.native_effect_areas.values()
                ],
                "effects": [
                    {
                        key: row.get(key)
                        for key in (
                            "effect_reference",
                            "status",
                            "reason",
                            "caster_id",
                            "target_id",
                        )
                    }
                    for row in trace
                ],
            },
        )
        return (tx.fight, *data[1:]), tx

    def summon(self, fight, owner, profile):
        from wakfu_server.combat_summon_spellbook import actor_action_book

        return next(
            a
            for a in fight.actors.values()
            if a.hp > 0
            and getattr(a, "native_summon_source", None)
            and a.native_summon_source["controller_id"] == owner
            and actor_action_book(a)["profile"] == profile
        )

    def test_absorption_and_explosion_preserve_other_owners_doll(self):
        from wakfu_server.combat_qi_fight import current_registry

        data = self.fixture()
        data, _ = self.cast(data, 7, 8137, (-8, -8, -1))
        data, _ = self.cast(data, 7, 925, (-8, -8, -1))
        own = self.summon(data[0], 7, 3747)
        data, _ = self.cast(data, 8, 8137, (-6, -6, -1))
        data, _ = self.cast(data, 8, 921, (-6, -6, -1))
        foreign = self.summon(data[0], 8, 3748)
        # Capture only after real intervening turns: native8200/377889 grows
        # this doll's own Chain Reaction8205/8209 at its1002 end boundary.
        self.reach(*data[:4], 7, data[4])
        foreign = data[0].actors[foreign.id]
        foreign_before = (
            foreign.hp,
            foreign.position,
            tuple((s.uid, s.reference, s.level) for s in foreign.state_ledger.entries),
        )
        data, _ = self.cast(data, 7, 911, (-7, -7, -1))
        after_absorption = data[0].actors[foreign.id]
        self.assertEqual(
            (
                after_absorption.hp,
                after_absorption.position,
                tuple(
                    (s.uid, s.reference, s.level)
                    for s in after_absorption.state_ledger.entries
                ),
            ),
            foreign_before,
        )
        source = self.summon(data[0], 7, 3746)
        states = {s.reference for s in source.state_ledger.entries}
        self.assertIn(8193, states)
        self.assertNotIn(8187, states)
        self.assertEqual(data[0].actors[own.id].hp, 0)
        self.reach(*data[:4], source.id, data[4])
        foreign = data[0].actors[foreign.id]
        foreign_before = (
            foreign.hp,
            foreign.position,
            tuple((s.uid, s.reference, s.level) for s in foreign.state_ledger.entries),
        )
        data, tx = self.cast(data, source.id, 5024, source.position)
        self.assertEqual(
            tuple(tx.plan["costs"][k] for k in ("ap", "mp", "wp")), (3, 0, 0)
        )
        self.assertEqual(data[0].actors[source.id].hp, 0)
        after = data[0].actors[foreign.id]
        self.assertEqual(
            (
                after.hp,
                after.position,
                tuple(
                    (s.uid, s.reference, s.level) for s in after.state_ledger.entries
                ),
            ),
            foreign_before,
        )
        for identity in (7, 8, 9, -7, foreign.id):
            self.assertTrue(
                any(
                    row and row["identity"] == ["actor", identity]
                    for row in data[0].native_qi_slots
                )
            )
        for identity in (own.id, source.id):
            self.assertFalse(
                any(
                    row and row["identity"] == ["actor", identity]
                    for row in data[0].native_qi_slots
                )
            )
        current_registry(data[0])

    def test_tree_armor_uses_source_owner_hp_and_includes_adjacent_other_owner(self):
        from wakfu_server.combat_parameters import _float32

        data = self.fixture()
        data, _ = self.cast(data, 7, 926, data[0].actors[8].position)
        vudul = self.summon(data[0], 7, 3745)
        data, _ = self.cast(data, 8, 8137, (-6, -5, -1))
        data, _ = self.cast(data, 8, 8137, (-6, -5, -1))
        foreign_tree = self.summon(data[0], 8, 5577)
        # Native378650 enforces TEAM-wide tree spacing: no existing8217
        # within Manhattan2 of the new seed, even for a different owner.
        self.assertGreater(
            abs(foreign_tree.position[0] + 7) + abs(foreign_tree.position[1] + 7), 2
        )
        data, _ = self.cast(data, 7, 8137, (-7, -7, -1))
        data, _ = self.cast(data, 7, 8137, (-7, -7, -1))
        tree = self.summon(data[0], 7, 5577)
        self.reach(*data[:4], vudul.id, data[4])
        owner = data[0].actors[7]
        expected = math.floor(
            _float32(_float32(0.05) * (owner.max_hp + owner.effect_maxima[92])) + 0.5
        )
        before = {
            a.id: (a.hp, a.position, a.effect_stats[97])
            for a in data[0].actors.values()
        }
        eligible = {
            a.id
            for a in data[0].actors.values()
            if a.hp > 0
            and a.team == owner.team
            and max(
                abs(a.position[0] - tree.position[0]),
                abs(a.position[1] - tree.position[1]),
            )
            == 1
        }
        self.assertTrue({7, 8} <= eligible)
        self.assertNotIn(foreign_tree.id, eligible)
        source = data[0].actors[vudul.id]
        # The real tree aura produced8226 level2. Native379533→378643
        # grants ARMOR_GIVEN =15+5*2, rather than a zero-bonus fixture.
        blessing = [
            state for state in source.state_ledger.entries if state.reference == 8226
        ]
        self.assertEqual(len(blessing), 1)
        self.assertEqual(blessing[0].level, 2)
        self.assertEqual(source.effect_stats[120], 25)
        for identity in eligible:
            self.assertEqual(data[0].actors[identity].effect_stats[121], 0)
        data, tx = self.cast(data, vudul.id, 8140, tree.position)
        self.assertEqual(
            tuple(tx.plan["costs"][k] for k in ("ap", "mp", "wp")), (3, 0, 0)
        )
        for identity, old in before.items():
            actor = data[0].actors[identity]
            self.assertEqual((actor.hp, actor.position), old[:2])
            # Native1013 default coefficient mode3: source bonus excludes
            # self, target121 adds before float32 scaling and floor rounding.
            bonus = 0 if identity == vudul.id else 25
            factor = _float32(1 + _float32(_float32(bonus) / 100))
            expected_armor = math.floor(_float32(_float32(expected) * factor))
            self.assertEqual(
                actor.effect_stats[97] - old[2],
                expected_armor if identity in eligible else 0,
            )
