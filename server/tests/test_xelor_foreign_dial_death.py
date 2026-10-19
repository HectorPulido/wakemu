"""Two actual owned dials; repeated paid hostile attacks retire only one dial."""
import json
from copy import deepcopy
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
        lethal = None
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
            clock_states = {
                owner: deepcopy(
                    [
                        entry
                        for entry in runtime.fight.actors[owner].state_ledger.entries
                        if entry.reference in (6758, 6759)
                    ]
                )
                for owner in (7, 8)
            }
            current_hours = {
                owner: {
                    uid: dict(row)
                    for uid, row in runtime.fight.native_effect_areas.items()
                    if row["owner_id"] == owner and 1546 <= row["reference"] <= 1558
                }
                for owner in (7, 8)
            }
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
            if runtime.fight.actors[victim.id].hp == 0:
                lethal = (tuple(tx.packets), clock_states, current_hours)
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
        self.assertIsNotNone(lethal)
        lethal_packets, clock_states, current_hours = lethal
        from wakfu_server.combat_effect_removal import _identity_fields
        from wakfu_server.combat_global_pv_collections import global_area_order
        from wakfu_server.combat_spectator_snapshot import _retained_carrier_packets

        removed_hours = []
        for opcode, body in lethal_packets:
            if opcode != 12613 or len(body) < 19:
                continue
            effect_class, length = struct.unpack_from(">ih", body, 13)
            if effect_class != 843:
                continue
            self.assertEqual(body[12], 1)
            fields = _identity_fields(body[19 : 19 + length])
            self.assertEqual(fields[3], 313314)
            removed_hours.append(fields[7])
        self.assertCountEqual(removed_hours, current_hours[7])
        self.assertTrue(set(removed_hours).isdisjoint(current_hours[8]))
        self.assertTrue(
            set(current_hours[7]).isdisjoint(global_area_order(runtime.fight))
        )
        for owner in (7, 8):
            self.assertEqual(
                [
                    entry
                    for entry in runtime.fight.actors[owner].state_ledger.entries
                    if entry.reference == 6758
                ],
                [entry for entry in clock_states[owner] if entry.reference == 6758],
            )
        own_hour = [entry for entry in clock_states[7] if entry.reference == 6759]
        foreign_hour = [entry for entry in clock_states[8] if entry.reference == 6759]
        self.assertEqual(len(own_hour), 1)
        self.assertEqual(len(foreign_hour), 1)
        self.assertFalse(
            any(
                entry.reference == 6759
                for entry in runtime.fight.actors[7].state_ledger.entries
            )
        )
        self.assertEqual(
            [
                entry
                for entry in runtime.fight.actors[8].state_ledger.entries
                if entry.reference == 6759
            ],
            foreign_hour,
        )
        removals = {
            struct.unpack(">qq", body[-16:])
            for opcode, body in lethal_packets
            if opcode == 13560
        }
        self.assertIn((7, own_hour[0].uid), removals)
        self.assertNotIn((8, foreign_hour[0].uid), removals)

        # Qf may keep retired creators, but reconnect must not execute their
        # visual construction. Current foreign creators remain rehydratable.
        before_projection = snapshot(runtime.fight)
        replayed_creators = set()
        for opcode, body in _retained_carrier_packets(runtime.fight, 999):
            if opcode != 12613 or len(body) < 19:
                continue
            _, length = struct.unpack_from(">ih", body, 13)
            replayed_creators.add(_identity_fields(body[19 : 19 + length])[1])
        creator_ids = {
            owner: {row["effect_uid"] for row in current_hours[owner].values()}
            for owner in (7, 8)
        }
        self.assertTrue(creator_ids[7].isdisjoint(replayed_creators))
        # Ordinary HOUR315 creation can be immediate/nonretained. Only its
        # actual current Qf creators belong in the retained-carrier projection.
        foreign_retained_creators = creator_ids[8] & set(
            runtime.fight.native_retained_records
        )
        self.assertTrue(foreign_retained_creators <= replayed_creators)
        self.assertIn(foreign_hour[0].uid, replayed_creators)
        self.assertTrue(set(current_hours[8]) <= set(global_area_order(runtime.fight)))
        for uid, row in current_hours[8].items():
            self.assertEqual(runtime.fight.native_effect_areas[uid], row)
        self.assertEqual(snapshot(runtime.fight), before_projection)
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
