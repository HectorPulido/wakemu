"""Actual native Xelor resources, grants and dial lifecycle through common entry."""
import random
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_active_spells as native_fixture
import test_aniripsa_grant_summon_pipeline as native_turns
from wakfu_server.combat_arena_selection import bounded_arena
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_turn_start,
    prepare_server_spell,
)
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class XelorRuntimePipelineTests(unittest.TestCase):
    def fixture(
        self,
        *,
        level=200,
        passives=(),
        actives=(754, 775, 2839),
        seed=17,
        target_distance=3,
        target_offset=None,
    ):
        origin = (-8, -7, -1)
        offset = target_offset or (target_distance, 0)
        target = (origin[0] + offset[0], origin[1] + offset[1], origin[2])
        terrain = bounded_arena(map_geometry(1134), origin, [target], radius=12)
        character, monster, fight = native_fixture.fixture(
            5,
            level,
            target,
            terrain,
            origin,
            monster_reference=3646,
            monster_level=12,
        )
        deck, rng = encode_deck(actives, passives), random.Random(seed)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        fight, _ = prepare_server_turn_start(
            character,
            {-7: monster},
            fight,
            deck,
            actor_id=fight.current.id,
            action_id=2,
            rng=rng,
            area_callbacks=True,
        )
        data = character, monster, fight, deck, rng
        if fight.current.id != 7:
            data = self.next_owned_turn(data)
        return data

    @staticmethod
    def adopt(data, fight):
        return (*data[:2], fight, *data[3:])

    def cast(self, data, reference, cell=None, *, action_id=3):
        character, monster, fight, deck, rng = data
        before = snapshot(fight)
        uid = (
            granted_spells(fight, 7)
            .get(reference, {})
            .get("uid", (7 << 32) | reference)
        )
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, uid, *(cell or fight.actors[7].position)),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=action_id,
            line_of_sight=lambda source, target, preview: authoritative_visible(
                1134, source, target, preview
            ),
            critical=False,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(tx.outcomes))
        return tx

    def next_owned_turn(self, data):
        fight = data[2]
        for _ in range(16):
            native_turns.AniripsaGrantSummonPipelineTests().end_current_turn(
                fight, data
            )
            if fight.phase != "active" or fight.current.id == 7:
                return self.adopt(data, fight)
        self.fail("Xelor owner did not regain a turn")

    @staticmethod
    def states(actor):
        return {s.reference: s.level for s in actor.state_ledger.entries}

    def test_native_ready_wp12_and_three_owned_grants(self):
        for level in (20, 200):
            with self.subTest(level=level):
                data = self.fixture(level=level)
                actor = data[2].actors[7]
                self.assertEqual(
                    (actor.ap, actor.mp, actor.effect_stats[4]), (6, 3, 12)
                )
                self.assertEqual(actor.effect_maxima[4], 12)
                self.assertTrue({5345, 3909, 7794} <= set(granted_spells(data[2], 7)))
                self.assertTrue({6755, 4464} <= set(self.states(actor)))
                self.assertEqual(
                    (data[2].native_table_turn, data[2].native_timeline_round), (1, 1)
                )
                self.assertEqual(data[2].current.id, 7)

    def test_time_theft_native_usage_rollback_then_next_turn_escalation(self):
        data = self.fixture()
        tx = self.cast(data, 3909)
        actor = tx.fight.actors[7]
        self.assertEqual((actor.ap, actor.effect_stats[4]), (7, 11))
        self.assertEqual(self.states(actor)[6752], 1)
        adopted = self.adopt(data, tx.fight)
        before, random_before = snapshot(tx.fight), data[4].getstate()
        with self.assertRaisesRegex(ValueError, "maximum casts per turn"):
            self.cast(adopted, 3909, action_id=4)
        self.assertEqual(snapshot(tx.fight), before)
        self.assertEqual(data[4].getstate(), random_before)
        # Native limits allow one cast/turn.6752 has a two-end-tick clock;
        # the next lawful owner turn retains level1 and selects cost/gain2.
        adopted = self.next_owned_turn(adopted)
        actor = adopted[2].actors[7]
        self.assertEqual(self.states(actor)[6752], 1)
        ap, wp = actor.ap, actor.effect_stats[4]
        second = self.cast(adopted, 3909, action_id=20)
        after = second.fight.actors[7]
        self.assertEqual((after.ap, after.effect_stats[4]), (ap + 2, wp - 2))
        self.assertEqual(self.states(after)[6752], 2)

    def test_slowdown_and_devotion_have_exact_owned_resource_receipts(self):
        for reference, ap, wp in ((775, 5, 11), (2839, 6, 8)):
            with self.subTest(reference=reference):
                data = self.fixture()
                tx = self.cast(data, reference, data[2].actors[-7].position)
                self.assertEqual(
                    (tx.fight.actors[7].ap, tx.fight.actors[7].effect_stats[4]),
                    (ap, wp),
                )

    def dial(self, data):
        fight = data[2]
        origin = fight.actors[7].position
        candidates = sorted(
            fight.walkable,
            key=lambda c: (abs(c[0] - origin[0]) + abs(c[1] - origin[1]), c),
        )
        accepted = []
        for cell in candidates:
            if not 1 <= abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) <= 3:
                continue
            if cell[0] != origin[0] and cell[1] != origin[1]:
                continue
            try:
                tx = self.cast(data, 5345, cell)
            except ValueError:
                continue
            hours = {
                r["reference"]
                for r in tx.fight.native_effect_areas.values()
                if r.get("owner_id") == 7 and 1546 <= r["reference"] <= 1557
            }
            accepted.append((len(hours), tx))
            if len(hours) == 12:
                return tx
        self.assertTrue(accepted, "No native eligible sphere placement")
        return max(accepted, key=lambda row: row[0])[1]

    def test_actual_dial_installs_native_hours_owner_and_current_hour(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_qi_fight import current_registry

        data = self.fixture()
        tx = self.dial(data)
        actor = tx.fight.actors[7]
        self.assertEqual((actor.ap, actor.effect_stats[4]), (4, 12))
        self.assertEqual(self.states(actor)[6759], 12)
        hours = [
            r
            for r in tx.fight.native_effect_areas.values()
            if r.get("owner_id") == 7 and 1546 <= r["reference"] <= 1557
        ]
        self.assertEqual({r["reference"] for r in hours}, set(range(1546, 1558)))
        self.assertTrue(all(r["native_area_contract"] == "faZ" for r in hours))
        summons = [a for a in tx.fight.actors.values() if a.id not in data[2].actors]
        self.assertEqual(len(summons), 1)
        self.assertEqual(actor_action_book(summons[0])["profile"], 3791)
        self.assertEqual(actor_action_book(summons[0])["actions"], [])
        current_registry(tx.fight)

    def test_dial_private_checkpoint_and_owned_turn_preserve_registered_roster(self):
        import copy
        import json
        from wakfu_server.combat_qi_fight import current_registry

        data = self.fixture()
        tx = self.dial(data)
        owned = tx.fight
        before = snapshot(owned)
        plain = json.loads(json.dumps(before))
        self.assertEqual(plain, before)
        clone = copy.deepcopy(owned)
        self.assertEqual(snapshot(clone), before)
        clone.actors[7].ap -= 1
        self.assertEqual(snapshot(owned), before)
        prior_turn = owned.turn_id
        data = self.next_owned_turn(self.adopt(data, owned))
        after = data[2]
        self.assertEqual(after.phase, "active")
        self.assertEqual(after.current.id, 7)
        self.assertGreater(after.turn_id, prior_turn)
        self.assertEqual(after.actors[7].ap, after.actors[7].max_ap)
        self.assertIn(6759, self.states(after.actors[7]))
        current_registry(after)
        self.assertEqual(set(after.actors), {int(i) for i in before["actors"]})
