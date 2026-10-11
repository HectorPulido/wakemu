import os
import random
import struct
import unittest
from unittest.mock import patch
import test_combat_spell_transaction as fixture_module
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import server_runtime, prepare_server_spell
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_terrain import local_arena
from wakfu_server.monsters import owned_instance
from wakfu_server.spells import encode_deck
from wakfu_server.fight_checkpoint_store import snapshot


@patch.dict(
    os.environ, {"WAKFU_NATIVE_GRANTED_CAST": "1", "WAKFU_NATIVE_AREA_CALLBACKS": "1"}
)
class NativeSummonEntryTests(unittest.TestCase):
    def test_native_granted_sphere_common_entry_and_registered_roster(self):
        fixture = fixture_module.SpellTransactionTests()
        character, _, _ = fixture.native_server_fixture(5, 20)
        origin, enemy_cell = (-8, -7, -1), (-7, -7, -1)
        character.update(
            account_id=3,
            name="Summon entry",
            map_id=1134,
            instance_id=0,
            x=origin[0],
            y=origin[1],
            z=origin[2],
        )
        monster = owned_instance(
            5525,
            1,
            -7,
            map_id=1134,
            x=enemy_cell[0],
            y=enemy_cell[1],
            z=enemy_cell[2],
        )
        # Reserve sufficient native terrain for all twelve clock offsets;
        # the automatic5–7-cell minimum can legitimately clip some hours.
        terrain = local_arena(
            1134,
            0,
            origin,
            enemy_cell,
            compact=True,
            minimum_dimensions=(15, 15),
            variation_seed=0,
        )
        fight, _ = create_placement(
            character,
            monster,
            terrain,
            fight_id=78,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=0,
            terrain_effect_id=46,
            terrain_instance_id=-300,
        )
        initialize_fight_snapshots(
            fight,
            characters={7: character},
            monsters={-7: monster},
            wp_resources={7: (6, 6), -7: (monster["wp"], monster["wp"])},
            running_effects={7: (), -7: ()},
            initial_effect_uid=200,
        )
        fight.actors[7].direction = 0
        fight.actors[-7].direction = 3
        fight.ready(3)
        while fight.current is not None and fight.current.id != 7:
            fight.end_server_turn(fight.current.id, fight.turn_id)
        caster_cell = fight.actors[7].position
        occupied_cells = {actor.position for actor in fight.actors.values()}
        summon_cell = next(
            cell
            for cell in sorted(fight.walkable)
            if 1 <= abs(cell[0] - caster_cell[0]) + abs(cell[1] - caster_cell[1]) <= 3
            and (cell[0] == caster_cell[0] or cell[1] == caster_cell[1])
            and cell not in occupied_cells
        )
        deck = encode_deck([], [])
        factory, _ = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=1,
            critical=False,
            rng=random.Random(1),
        )
        dispatcher, _ = factory(
            fight,
            dict(
                native_retained_container=dict(
                    present=True,
                    type=3,
                    id=(6755 << 16) + 1,
                    is_spell=False,
                    protected=None,
                )
            ),
        )
        # Actual649 child of native6755 grants5345; no copied/custom ability definition.
        dispatcher.execute(EffectInvocation(313107, 1, 7, 7, origin))
        before = snapshot(fight)
        body = struct.pack(">qqiih", 7, 5345, *summon_cell)

        def native_los(source, target, preview):
            return authoritative_visible(
                1134,
                source,
                target,
                preview,
                blocking_footprints={
                    actor.id: {actor.position[:2]}
                    for actor in preview.actors.values()
                    if actor.hp > 0
                },
            )

        try:
            cast = prepare_server_spell(
                body,
                character,
                {-7: monster},
                fight,
                3,
                deck,
                action_id=2,
                line_of_sight=native_los,
                critical=False,
                rng=random.Random(1),
            )
        except ValueError as error:
            self.fail(
                f"Native spell rejection {error}; "
                f"diagnostic={getattr(error, 'native_casting_diagnostic', None)!r}; "
                f"caster_cell={fight.actors[7].position!r}; target_cell={summon_cell!r}"
            )
        self.assertEqual(snapshot(fight), before)
        # The native current-hour6759 starts at12. Its actual313308 reaction
        # already creates1558 on hour1557 during the same cast.
        self.assertEqual(
            {
                r["reference"]
                for r in cast.fight.native_effect_areas.values()
                if r.get("owner_id") == 7
            },
            set(range(1546, 1559)),
        )
        owned = [
            r for r in cast.fight.native_effect_areas.values() if r.get("owner_id") == 7
        ]
        self.assertEqual(len(owned), 13)
        self.assertTrue(
            all(
                r["native_area_contract"] == "faZ" and r["native_type_id"] == 1
                for r in owned
            )
        )
        center = next(r for r in owned if r["reference"] == 1558)
        hour = next(r for r in owned if r["reference"] == 1557)
        self.assertEqual(center["cell"], hour["cell"])
        self.assertEqual(center["effect_reference"], 313308)
        self.assertEqual(center["effect_class"], 315)
        self.assertFalse(center["keep_after"])
        self.assertFalse(center["native_running_effect_manager"])
        self.assertEqual(
            next(
                s.level
                for s in cast.fight.actors[7].state_ledger.entries
                if s.reference == 6759
            ),
            12,
        )
        # The native battleground has an faP border and a faY environmental
        # glyph alongside the thirteen class-owned areas.
        self.assertEqual(len(cast.fight.native_effect_areas), 15)
        border_rows = [
            row
            for row in cast.fight.native_effect_areas.values()
            if row.get("native_area_contract") == "faP"
        ]
        self.assertEqual(len(border_rows), 1)
        self.assertEqual(border_rows[0]["uid"], -300)
        environment_rows = [
            row
            for row in cast.fight.native_effect_areas.values()
            if row.get("native_area_contract") == "faY"
        ]
        self.assertEqual(len(environment_rows), 1)
        self.assertEqual(environment_rows[0]["reference"], 910)
        self.assertEqual(
            {
                row["reference"]
                for row in cast.fight.native_effect_areas.values()
                if row.get("native_area_contract") not in ("faP", "faY")
            },
            set(range(1546, 1559)),
        )
        self.assertEqual(len(set(cast.fight.actors) - set(fight.actors)), 1)
        classes = [
            struct.unpack_from(">i", data, 13 if opcode == 12613 else 12)[0]
            for opcode, data in cast.packets
            if opcode in (13497, 12613)
        ]
        # Twelve areas use cvY/13497. The native 313308 area definition has
        # no event subscription, so its retained UID is delivered as cvX/12613.
        from wakfu_server.combat_effect_removal import _identity_fields

        area_applications = []
        for opcode, data in cast.packets:
            class_offset, body_offset = {
                13497: (12, 18),
                12613: (13, 19),
            }.get(opcode, (None, None))
            if class_offset is None or len(data) < body_offset:
                continue
            if struct.unpack_from(">i", data, class_offset)[0] != 315:
                continue
            fields = _identity_fields(data[body_offset:], integer_fields=(1, 2, 3, 4))
            area_applications.append((fields[3], fields[4]))
        self.assertEqual(len(area_applications), 13)
        self.assertEqual(
            {area_reference for _, area_reference in area_applications},
            {
                row["reference"]
                for row in cast.fight.native_effect_areas.values()
                if row.get("native_area_contract") not in ("faP", "faY")
            },
        )
        self.assertEqual(
            {area_reference for _, area_reference in area_applications},
            set(range(1546, 1559)),
        )
        self.assertEqual(
            len({area_reference for _, area_reference in area_applications}), 13
        )
        self.assertEqual(classes.count(307), 1)
        self.assertEqual(
            cast.fight.actors[7].ap, fight.actors[7].ap - cast.plan["costs"]["ap"]
        )
        # Actual400 producer352198 emits2251 to a real Qq; Qq routes channel1
        # to its actual running caster. No fabricated turn or effect source.
        import copy

        source_before = snapshot(cast.fight)
        area = next(
            row
            for row in cast.fight.native_effect_areas.values()
            if row["reference"] == 1558
        )
        area_preview = copy.deepcopy(cast.fight)
        area_factory, _ = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=3,
            critical=False,
            rng=random.Random(1),
        )
        area_dispatcher, area_packets = area_factory(
            area_preview, {"native_retained_container": {"present": False}}
        )
        area_dispatcher.execute(
            EffectInvocation(
                352198, 1, 7, area["uid"], area["cell"], native_explicit_target=True
            )
        )
        self.assertEqual(area_preview.actors[7].position, cast.fight.actors[7].position)
        self.assertTrue(area_packets)
        # Original843 definition317642 selects this explicit area, calls Qs.b,
        # and removes no other clock-cell UID. Reconstructing retains ownership.
        area_dispatcher.execute(
            EffectInvocation(
                317642, 1, 7, area["uid"], area["cell"], native_explicit_target=True
            )
        )
        self.assertNotIn(area["uid"], area_preview.native_effect_areas)
        # The area used by this check was removed; twelve class areas plus
        # the compact border and environment glyph remain.
        self.assertEqual(len(area_preview.native_effect_areas), 14)
        self.assertIn(-300, area_preview.native_effect_areas)
        self.assertTrue(
            any(
                row.get("native_area_contract") == "faY" and row["reference"] == 910
                for row in area_preview.native_effect_areas.values()
            )
        )
        self.assertTrue(
            any(
                op == 13497 and struct.unpack_from(">i", payload, 12)[0] == 843
                for op, payload in area_packets
            )
        )
        self.assertTrue(any(op == 13560 for op, _ in area_packets))
        area_factory(area_preview, {"native_retained_container": {"present": False}})
        self.assertEqual(snapshot(cast.fight), source_before)
        # Real307 root from5345 also supports a new runtime after commit.
        factory, _ = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=2,
            critical=False,
            rng=random.Random(1),
        )
        import copy

        preview = copy.deepcopy(fight)
        dispatcher, packets = factory(preview, dict(spell_id=5345, evaluation_level=1))
        dispatcher.execute(EffectInvocation(313167, 1, 7, None, summon_cell))
        from types import SimpleNamespace

        tx = SimpleNamespace(fight=preview, packets=packets)
        added = set(tx.fight.actors) - set(fight.actors)
        self.assertEqual(len(added), 1)
        actor = tx.fight.actors[next(iter(added))]
        self.assertEqual(
            (actor.hp, actor.ap, actor.mp, actor.effective_level), (1, 0, 0, 20)
        )
        self.assertNotIn(actor.id, tx.fight.order)
        self.assertEqual(actor.position, summon_cell)
        self.assertTrue(
            any(
                opcode == 12613
                and len(payload) >= 19
                and struct.unpack_from(">iiiBi", payload) == (fight.id, 2, -1, 1, 307)
                for opcode, payload in tx.packets
            ),
            "native eWv class307 summon creation is immediate cvX/eIK=true",
        )
        # A reconnect snapshot replays the recorded constructor delivery for
        # each registered summon, then overlays current actor stats and retained
        # effects. It does not run the original summon effect a second time.
        from types import SimpleNamespace
        from wakfu_server.combat.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat.combat_shared import Session
        from wakfu_server.combat.combat_wire import decode_actor_state

        reconnect_runtime = SimpleNamespace(
            turn_deadline=None,
            native_action_id=cast.action_id,
            awaiting_ack=None,
        )
        reconnect_shared = SimpleNamespace(
            fight=cast.fight,
            map_id=1134,
            runtime=reconnect_runtime,
            join_context={
                "arena": terrain,
                "terrain_effect_id": 46,
                "terrain_instance_id": -300,
                "leaders": {0: 7, 1: -7},
            },
            ack=None,
        )
        serialized_actor_stats = {}

        def current_actor_payload(current_fight, current_actor, session):
            stats = struct.pack(
                ">iii", current_actor.hp, current_actor.ap, current_actor.mp
            )
            serialized_actor_stats[current_actor.id] = stats
            return stats, b"current-effects"

        before_reconnect_snapshot = snapshot(cast.fight)
        reconnect_packets = owned_snapshot(
            cast.fight,
            reconnect_shared,
            Session(3, 7, "reconnect", 1134, 0),
            actor_payload=current_actor_payload,
        )
        self.assertEqual(snapshot(cast.fight), before_reconnect_snapshot)
        for actor_uid, delivery in cast.fight.native_summon_creation_deliveries.items():
            creation = (delivery["opcode"], bytes.fromhex(delivery["payload_hex"]))
            self.assertEqual(reconnect_packets.count(creation), 1)
            self.assertEqual(
                struct.unpack_from(">iiiBi", creation[1]), (fight.id, 2, -1, 1, 307)
            )
        stat_overlays = {
            row["actor_id"]: row["state"]
            for opcode, payload in reconnect_packets
            if opcode == 12873
            for row in (decode_actor_state(opcode, payload),)
        }
        self.assertEqual(stat_overlays, serialized_actor_stats)
        for actor_id, raw_stats in serialized_actor_stats.items():
            self.assertEqual(
                struct.unpack(">iii", raw_stats),
                (
                    cast.fight.actors[actor_id].hp,
                    cast.fight.actors[actor_id].ap,
                    cast.fight.actors[actor_id].mp,
                ),
            )
        self.assertEqual(snapshot(fight), before)
        # A newly constructed runtime must recognize the persisted registration,
        # while an actor added without that registration remains rejected.
        _, adapter = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=3,
            critical=False,
            rng=random.Random(1),
        )
        self.assertTrue(adapter.actor_authority(tx.fight, actor).is_summon)
