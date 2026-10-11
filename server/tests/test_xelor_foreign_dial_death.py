"""Two actual owned dials; repeated paid hostile attacks retire only one dial."""
import json
import random
import struct
import unittest
import xelor_multiowner_fixture as fixtures
from tools.combat_audit_turns import advance_actual_turn
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import (
    prepare_server_spell,
    server_runtime,
    prepare_server_turn_start,
    prepare_server_turn_end,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_npc_spell import prepare_npc_spell
from wakfu_server.combat_death import newly_registered_death_messages
from wakfu_server.combat_qi_fight import current_registry
from wakfu_server.fight_checkpoint_store import snapshot, Checkpoints


class XelorForeignDialDeathTests(unittest.TestCase):
    def test_real_paid_enemy_strikes_retire_one_owned_dial_and_preserve_foreign_hours(
        self,
    ):
        fight, characters, monster, decks = fixtures.TwoXelorFixture().fixture(
            caster_breed=5,
            level=1,
            injury=0,
            caster_aptitudes=(),
            compact_arena=False,
            second_player_position=(-8, -5, -1),
            third_player_position=(-9, -7, -1),
            enemy_position=(-5, -7, -1),
        )
        rng = random.Random(0)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                **common
            )[0],
        )
        born = {}
        for owner in (7, 8):
            for _ in range(16):
                if runtime.fight.current.id == owner:
                    break
                advance_actual_turn(runtime)
            self.assertEqual(runtime.fight.current.id, owner)
            from tools.class_spell_eligible_targets import eligible_cast_targets

            _, adapter = server_runtime(
                characters[owner],
                {-7: monster},
                decks[owner],
                action_id=10 + owner,
                critical=False,
                **common
            )
            uid = granted_spells(runtime.fight, owner)[5345]["uid"]
            selected = eligible_cast_targets(
                runtime.fight,
                characters[owner],
                decks[owner],
                uid,
                adapter=adapter,
                actor_id=owner,
                limit=512,
                maximum_eligible=16,
                line_of_sight=lambda a, b, p: authoritative_visible(1134, a, b, p),
            )
            cells = [tuple(row["target"]) for row in selected["eligible"]]
            if owner == 7:
                enemy = runtime.fight.actors[-7].position
                cells = [
                    cell
                    for cell in cells
                    if abs(cell[0] - enemy[0]) + abs(cell[1] - enemy[1]) == 1
                ]
            self.assertTrue(cells, selected)
            cell = cells[0]
            source = snapshot(runtime.fight)
            old_ids = set(runtime.fight.actors)
            uid = granted_spells(runtime.fight, owner)[5345]["uid"]
            tx = prepare_server_spell(
                struct.pack(">qqiih", owner, uid, *cell),
                characters[owner],
                {-7: monster},
                runtime.fight,
                characters[owner]["account_id"],
                decks[owner],
                action_id=10 + owner,
                line_of_sight=lambda a, b, p: authoritative_visible(1134, a, b, p),
                critical=False,
                **common
            )
            self.assertEqual(snapshot(runtime.fight), source)
            self.assertTrue(any(tx.outcomes))
            ids = set(tx.fight.actors) - old_ids
            self.assertEqual(len(ids), 1)
            born[owner] = ids.pop()
            runtime.fight = tx.fight
        hours = {
            owner: {
                uid: dict(row)
                for uid, row in runtime.fight.native_effect_areas.items()
                if row["owner_id"] == owner and 1546 <= row["reference"] <= 1558
            }
            for owner in (7, 8)
        }
        self.assertTrue(hours[7])
        self.assertTrue(hours[8])
        saved = snapshot(runtime.fight)
        restored = Checkpoints._read_snapshot(json.loads(json.dumps(saved)))
        for owner in (7, 8):
            for uid, row in hours[owner].items():
                self.assertEqual(
                    restored["native_effect_areas"][str(uid)],
                    json.loads(json.dumps(row)),
                )
        deaths = []
        for action in range(256):
            if runtime.fight.actors[born[7]].hp == 0:
                break
            for _ in range(32):
                if runtime.fight.current.id == -7:
                    break
                advance_actual_turn(runtime)
            self.assertEqual(runtime.fight.current.id, -7)
            victim = runtime.fight.actors[born[7]]
            source = snapshot(runtime.fight)
            hp = victim.hp
            sequence = runtime.fight.sequence
            tx = prepare_npc_spell(
                runtime.fight,
                dict(
                    type="cast",
                    spellId=7962,
                    level=1,
                    targetId=victim.id,
                    target=list(victim.position),
                ),
                characters[7],
                {-7: monster},
                decks[7],
                action_id=50 + action,
                **common
            )
            self.assertEqual(snapshot(runtime.fight), source)
            runtime.fight = tx.fight
            self.assertLess(runtime.fight.actors[victim.id].hp, hp)
            deaths.extend(
                struct.unpack(">iiiqB", body)[3:]
                for op, body in newly_registered_death_messages(
                    runtime, after_sequence=sequence
                )
                if op == 12727
            )
            if runtime.fight.actors[victim.id].hp > 0:
                advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.actors[born[7]].hp, 0)
        self.assertIn((born[7], 2), deaths)
        self.assertFalse(any(identity in (7, 8, born[8]) for identity, _ in deaths))
        self.assertEqual(runtime.fight.actors[born[7]].native_obstacle_id, -1)
        current_registry(runtime.fight)
        self.assertTrue(set(hours[7]).isdisjoint(runtime.fight.native_effect_areas))
        self.assertGreater(runtime.fight.actors[born[8]].hp, 0)
        for uid in hours[8]:
            self.assertIn(uid, runtime.fight.native_effect_areas)
            self.assertEqual(runtime.fight.native_effect_areas[uid]["owner_id"], 8)
        saved = snapshot(runtime.fight)
        restored = Checkpoints._read_snapshot(json.loads(json.dumps(saved)))
        self.assertEqual(
            restored["native_effect_areas"],
            json.loads(json.dumps(saved["native_effect_areas"])),
        )
