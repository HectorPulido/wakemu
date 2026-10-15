"""Owned Drheller death and reinvocation through actual native spell dispatch."""
from copy import deepcopy
import random
import struct
import unittest

import test_enutrof_runtime as enutrof_fixture
import test_combat_spell_transaction as native_fixture
import test_aniripsa_grant_summon_pipeline as lifecycle_fixture
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class EnutrofCompanionLifecycleTests(unittest.TestCase):
    cast = enutrof_fixture.EnutrofRuntimeTests.cast
    fixture = enutrof_fixture.EnutrofRuntimeTests.fixture

    def test_actual_ready_innate_companion_projects_before_native_birth(self):
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_global_pv_collections import register_global_fighter
        from wakfu_server.combat_qi_registry import NativeQIRegistry
        from wakfu_server.combat_state import Actor

        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            3,
            200,
            native_qi=True,
            full_health=True,
            target_hp=20000,
            target_distance=3,
            variation_seed=17,
        )
        # Reopen the untouched post-construction fight as the placement input
        # expected by Ready. Native actor snapshots and its actual map/QI source
        # remain intact; no Enutrof initialization has run yet.
        fight.phase = "placement"
        fight.ready_owners.clear()
        fight.order = []
        fight.turn_index = 0
        fight.turn_id = 0
        fight.native_base_turn_order = None
        fight.native_timeline_round = 0
        fight.native_table_turn = 0
        fight.events.clear()
        fight.sequence = 0
        for actor in fight.actors.values():
            actor.turn_count = 0

        from wakfu_server.combat_qi_snapshot import NativeQISnapshot

        occupied_positions = [actor.position for actor in fight.actors.values()]
        terrain = NativeQISnapshot(fight.native_qi_snapshot)
        hero_position = max(
            (
                cell
                for cell in fight.walkable
                if terrain.aK(*cell[:2]) and cell not in occupied_positions
            ),
            key=lambda cell: min(
                abs(cell[0] - other[0]) + abs(cell[1] - other[1])
                for other in occupied_positions
            ),
        )
        fight.placement[0].add(hero_position)
        from wakfu_server.equipment_stats import combat_resources, effective_character
        from wakfu_server.health import maximum

        hero_character = effective_character(
            dict(
                id=101,
                account_id=3,
                map_id=1134,
                breed=7,
                level=200,
                hp=maximum(7, 200),
                max_hp=maximum(7, 200),
                builds={},
                inventory_items=[],
            )
        )
        source = fight.actors[7]
        hero_resources = combat_resources(
            hero_character,
            base_ap=source.ap,
            base_mp=source.mp,
            base_initiative=source.initiative - 100,
        )
        hero = Actor(
            101,
            0,
            hero_position,
            hero_character["hp"],
            hero_resources["ap"],
            hero_resources["mp"],
            hero_resources["initiative"],
            source.effective_level,
            3,
            True,
            max_hp=hero_character["max_hp"],
        )
        hero.native_obstacle_id = next(
            index for index, row in enumerate(fight.native_qi_slots) if row is None
        )
        snapshot = build_player_snapshot(
            hero_character,
            hero,
            wp_current=6,
            wp_maximum=6,
            running_effects=(),
        )
        snapshot.install(hero)
        fight.actors[hero.id] = hero
        registry = NativeQIRegistry(
            fight.native_qi_snapshot,
            fight.native_qi_slots,
            touched_cells=fight.native_qi_touched_cells,
            byte_topology=fight.native_qi_byte_topology,
        )
        registered_slot = registry.register(
            dict(
                identity=["actor", hero.id],
                position=list(hero.position[:2]),
                radius=hero.physical_radius,
                indexed=True,
                movement_blocking=True,
            )
        )
        self.assertEqual(registered_slot, hero.native_obstacle_id)
        fight.native_qi_slots = registry.serialized_slots()
        fight.native_qi_touched_cells = registry.serialized_cells()
        fight.native_qi_byte_topology = registry.serialized_byte_topology()
        register_global_fighter(fight, hero.id, controller_id=source.id)

        deck = encode_deck((2008, 2014, 2018), ())
        hero_deck = encode_deck((630, 779, 645), ())
        player_characters = {7: character, hero.id: hero_character}
        deck_blobs = {7: deck, hero.id: hero_deck}
        rng = random.Random(7)
        baseline_current = []
        baseline_order = []

        def initialize(preview, action_id):
            baseline_current.append(preview.current.id)
            baseline_order.append(tuple(preview.order))
            preview, hero_packets = prepare_server_initialization(
                hero_character,
                {-7: monster},
                preview,
                3,
                hero_deck,
                action_id=action_id,
                rng=rng,
                fight_start=False,
                player_characters=player_characters,
                deck_blobs=deck_blobs,
            )
            preview, owner_packets = prepare_server_initialization(
                character,
                {-7: monster},
                preview,
                3,
                deck,
                action_id=action_id,
                rng=rng,
                fight_start=True,
                player_characters=player_characters,
                deck_blobs=deck_blobs,
            )
            return preview, tuple(hero_packets) + tuple(owner_packets)

        started, runtime, packets = prepare_ready(
            fight,
            3,
            True,
            initialize=initialize,
            stats_serializer=lambda _actor: b"ready baseline stats",
            effects_serializer=lambda: b"\0\0",
        )
        self.assertIsNotNone(runtime)
        self.assertEqual(len(baseline_current), 1)
        self.assertEqual(started.current.id, baseline_current[0])
        self.assertEqual(
            {actor.owner_id for actor in started.actors.values() if actor.controlled},
            {3},
        )

        companions = [
            actor
            for actor in started.actors.values()
            if getattr(actor, "native_summon_source", None)
        ]
        self.assertEqual(len(companions), 1)
        companion = companions[0]
        registration = started.native_summon_registrations[companion.id]
        birth = started.native_summon_creation_deliveries[companion.id]
        birth_packet = (birth["opcode"], bytes.fromhex(birth["payload_hex"]))
        self.assertEqual(birth_packet[0], 12613)
        birth_signature = birth_packet[1][:4] + birth_packet[1][8:]
        self.assertEqual(
            sum(
                opcode == birth_packet[0]
                and payload[:4] + payload[8:] == birth_signature
                for opcode, payload in packets
            ),
            1,
        )
        self.assertEqual(registration["actor_id"], companion.id)

        recovery = next(payload for opcode, payload in packets if opcode == 12053)
        envelope_size = struct.unpack_from(">h", recovery, 4)[0]
        state = recovery[6 : 6 + envelope_size][9:]
        cursor = struct.calcsize(">hiBq")
        order_count = struct.unpack_from(">b", state, cursor)[0]
        cursor += 1
        order = tuple(
            struct.unpack_from(">q", state, cursor + offset * 8)[0]
            for offset in range(order_count)
        )
        self.assertNotIn(companion.id, order)
        self.assertEqual(len(order), len(set(order)))
        self.assertEqual(order, baseline_order[0])
        self.assertIn(started.current.id, order)
        cursor += order_count * 8
        next_count = struct.unpack_from(">b", state, cursor)[0]
        cursor += 1
        next_order = tuple(
            struct.unpack_from(">q", state, cursor + offset * 8)[0]
            for offset in range(next_count)
        )
        self.assertNotIn(companion.id, next_order)
        self.assertEqual(next_order, baseline_order[0])
        cursor += next_count * 8
        progress_count = struct.unpack_from(">b", state, cursor)[0]
        progress_rows = tuple(
            struct.unpack_from(">qh", state, cursor + 1 + offset * 10)
            for offset in range(progress_count)
        )
        self.assertEqual({actor_id for actor_id, _ in progress_rows}, set(order))
        self.assertEqual(len(progress_rows), len(order))
        self.assertNotIn(companion.id, {actor_id for actor_id, _ in progress_rows})
        self.assertEqual(
            dict(progress_rows),
            {
                int(identity): value
                for identity, value in started.native_timeline_member_counters.items()
                if int(identity) != companion.id
            },
        )
        cursor += 1 + progress_count * struct.calcsize(">qh")
        self.assertEqual(state[cursor], order.index(started.current.id))
        cursor += 1
        removed_count = struct.unpack_from(">b", state, cursor)[0]
        cursor += 1 + removed_count * struct.calcsize(">qhih")
        roster_count = struct.unpack_from(">b", state, cursor)[0]
        cursor += 1
        roster = tuple(
            struct.unpack_from(">q", state, cursor + offset * 12)[0]
            for offset in range(roster_count)
        )
        expected_roster = tuple(
            identity for identity in started.actors if identity != companion.id
        )
        self.assertEqual(roster, expected_roster)
        self.assertEqual(len(roster), len(set(roster)))
        self.assertNotIn(companion.id, roster)

    def test_tunnel_passive_reduces_companion_mp_and_teleports_on_real_ore_action(self):
        from pathlib import Path
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from class_spell_eligible_targets import eligible_cast_targets

        baseline = self.fixture()
        original = next(
            actor
            for actor in baseline[2].actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        fixture = self.fixture(passives=(8279,), actives=(8240,))
        companion = next(
            actor
            for actor in fixture[2].actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        self.assertEqual(companion.max_mp, original.max_mp - 3)
        deposit = next(
            row
            for row in fixture[2].native_effect_areas.values()
            if row["reference"] == 203 and row["owner_id"] == 7
        )
        consumed = self.cast(fixture, 8240, tuple(deposit["cell"]))
        fixture = (*fixture[:2], consumed.fight, *fixture[3:])
        character, monster, fight, deck, rng = fixture
        helper = lifecycle_fixture.AniripsaGrantSummonPipelineTests()
        for _ in range(20):
            if fight.current.id == companion.id:
                break
            helper.end_current_turn(fight, fixture)
        self.assertEqual(fight.current.id, companion.id)
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=20, critical=False, rng=rng
        )
        candidates = eligible_cast_targets(
            fight,
            character,
            deck,
            3541,
            actor_id=companion.id,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            limit=128,
            maximum_eligible=3,
        )
        self.assertTrue(candidates["eligible"], candidates)
        cell = candidates["eligible"][0]["target"]
        from wakfu_server.combat_server_spell import prepare_server_spell

        tx = prepare_server_spell(
            struct.pack(">qqiih", companion.id, 3541, *cell),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=20,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertTrue(any(tx.outcomes))
        self.assertEqual(tx.fight.actors[companion.id].position, tuple(cell))
        self.assertTrue(
            any(
                row["reference"] == 203
                and row["owner_id"] == 7
                and tuple(row["cell"]) == tuple(cell)
                for row in tx.fight.native_effect_areas.values()
            )
        )

    def test_actual_enemy_spell_death_allows_new_owned_companion(self):
        from pathlib import Path
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_npc_attack import (
            ability,
            npc_runtime_catalog,
            npc_spell_catalog,
        )
        from wakfu_server.monsters import reference

        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            3,
            6,
            native_qi=True,
            full_health=True,
            target_level=reference(5525)["max_level"],
            target_distance=1,
            variation_seed=17,
        )
        # The simplified transaction fixture's monster source omits level;
        # preserve the level of its actual native NPC constructor, not a boost.
        monster["level"] = fight.actors[-7].effective_level
        deck, rng = encode_deck((2008,), ()), random.Random(7)
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
        companion = next(
            actor
            for actor in fight.actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        old_id = companion.id
        rule = ability(monster)
        helper = lifecycle_fixture.AniripsaGrantSummonPipelineTests()
        for attempt in range(32):
            fixture = character, monster, fight, deck, rng
            for _ in range(20):
                if fight.current.id == -7:
                    break
                helper.end_current_turn(fight, fixture)
            self.assertEqual(fight.current.id, -7)
            companion = fight.actors[old_id]
            self.assertEqual(
                sum(
                    abs(fight.current.position[i] - companion.position[i])
                    for i in (0, 1)
                ),
                1,
            )
            before = snapshot(fight)
            preview = deepcopy(fight)
            factory, _ = server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=20 + attempt,
                critical=False,
                rng=rng,
                compiled=npc_runtime_catalog(),
            )
            dispatcher, _ = factory(
                preview,
                dict(
                    actor_id=-7,
                    spell_id=rule["spell_id"],
                    evaluation_level=rule["spell_level"],
                    target_id=old_id,
                    target=companion.position,
                    costs={key: rule[key] for key in ("ap", "mp", "wp")},
                ),
            )
            with preview.effect_resolution():
                for reference in npc_spell_catalog()["spells"][str(rule["spell_id"])][
                    "levels"
                ][rule["spell_level"] - 1][2]:
                    dispatcher.execute(
                        EffectInvocation(
                            reference,
                            rule["spell_level"],
                            -7,
                            old_id,
                            companion.position,
                            native_explicit_target=True,
                        )
                    )
            self.assertEqual(snapshot(fight), before)
            self.assertLess(preview.actors[old_id].hp, companion.hp)
            fight = preview
            if fight.actors[old_id].hp == 0:
                break
            helper.end_current_turn(fight, (character, monster, fight, deck, rng))
        else:
            self.fail(
                "Actual owned enemy attacks did not kill the native companion within32 turns"
            )
        self.assertTrue(getattr(fight, "native_death_event_deliveries", {}))
        fixture = character, monster, fight, deck, rng
        for _ in range(20):
            if fight.current.id == 7:
                break
            helper.end_current_turn(fight, fixture)
        self.assertEqual(fight.current.id, 7)
        uid = granted_spells(fight, 7)[2027]["uid"]
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=40, critical=False, rng=rng
        )
        candidates = eligible_cast_targets(
            fight,
            character,
            deck,
            uid,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            limit=128,
            maximum_eligible=3,
        )
        self.assertTrue(candidates["eligible"], candidates)
        tx = self.cast(fixture, 2027, candidates["eligible"][0]["target"], action_id=40)
        replacements = [
            actor
            for actor in tx.fight.actors.values()
            if getattr(actor, "native_summon_source", None)
            and actor.id != old_id
            and actor.hp > 0
        ]
        self.assertEqual(len(replacements), 1)
        self.assertEqual(replacements[0].owner_id, 3)
        self.assertEqual(replacements[0].native_summon_source["controller_id"], 7)
        snapshot(tx.fight)
