"""Paid resurrection after native movement and paid captured summon on native floor.

Disposable fresh combat premises only; no runtime overlay, live player writes,
resource refill, HP-zero write or casting/LOS bypass.
"""
import json
import random
import struct
import tempfile
import unittest
from pathlib import Path
from wakfu_server.fight_checkpoint_store import snapshot


class PaidReviveSummonJourneyTests(unittest.TestCase):
    def fixture(self):
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum
        from wakfu_server.spells import encode_deck
        from wakfu_server.monsters import owned_instance

        positions = {
            7: (-8, -7, -1),
            8: (-7, -6, -1),
            9: (-8, -6, -1),
            -7: (-6, -7, -1),
        }
        arena = local_arena(1134, 78, positions[7], positions[-7])
        characters = {
            identity: effective_character(
                dict(
                    id=identity,
                    account_id=identity - 4,
                    map_id=1134,
                    breed=7 if identity == 7 else 8,
                    level=1 if identity == 8 else 60,
                    hp=maximum(7 if identity == 7 else 8, 1 if identity == 8 else 60),
                    builds={},
                    inventory_items=[],
                )
            )
            for identity in (7, 8, 9)
        }
        actors = [
            Actor(
                identity,
                0,
                positions[identity],
                characters[identity]["hp"],
                6,
                3,
                initiative,
                characters[identity]["level"],
                characters[identity]["account_id"],
                True,
                max_hp=characters[identity]["max_hp"],
            )
            for identity, initiative in ((7, 30), (8, 20), (9, 10))
        ]
        monster = owned_instance(5525, 1, -7, map_id=1134, x=-6, y=-7, z=-1)
        actors.append(Actor(-7, 1, positions[-7], monster["hp"], 6, 3, 1, 1))
        fight = Fight(
            78,
            actors,
            arena["validated_cells"],
            {0: {positions[7], positions[8], positions[9]}, 1: {positions[-7]}},
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        initialize_global_pv_collections(fight, (7, 8, 9, -7))
        freeze_terrain(fight)
        fight.native_obstacle_cells = frozenset()
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters={-7: monster},
            wp_resources={7: (6, 6), 8: (6, 6), 9: (6, 6), -7: (0, 0)},
            running_effects={identity: () for identity in positions},
            initial_effect_uid=1,
        )
        for owner in (3, 4, 5):
            fight.ready(owner)
        decks = {7: encode_deck([1535, 779]), 8: encode_deck(), 9: encode_deck()}
        rng = random.Random(0)
        for action_id, identity in enumerate((7, 8, 9), 1):
            fight, _ = prepare_server_initialization(
                characters[identity],
                {-7: monster},
                fight,
                characters[identity]["account_id"],
                decks[identity],
                action_id=action_id,
                rng=rng,
                fight_start=identity == 9,
                player_characters=characters,
                deck_blobs=decks,
            )
        return fight, characters, monster, decks, rng

    def test_moved_full_health_ally_paid_npc_ko_and_anisurreccion(self):
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.combat_npc_attack import ability
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_global_pv_collections import global_fighter_guards
        from wakfu_server.spells import owned_spell_records

        fight, characters, monster, decks, rng = self.fixture()
        monsters = {-7: monster}
        self.assertEqual(characters[7]["breed"], 7)
        self.assertEqual(fight.actors[8].hp, fight.actors[8].max_hp)
        initial_hp = fight.actors[8].hp
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda phase, **kw: prepare_server_turn_end(
                characters[7], monsters, phase, decks[7], **common, **kw
            ),
            turn_start_provider=lambda phase, **kw: prepare_server_turn_start(
                characters[7], monsters, phase, decks[7], **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                monsters,
                decks[7],
                action_id=action_id,
                critical=False,
                **common
            )[0],
        )

        def stats(actor, phase=None):
            phase = runtime.fight if phase is None else phase
            values = dict(
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                fight=phase,
            )
            if actor.id in characters:
                return actual_actor_stats(
                    characters[actor.id], actor, phase.id, **values
                )
            return actual_monster_actor_stats(
                monsters[actor.id], actor, phase.id, **values
            )

        def advance():
            actor = runtime.fight.current
            if actor.controlled:
                runtime.end_turn(
                    actor.owner_id, actor.id, current_wire_turn(runtime.fight)
                )
            else:
                runtime.end_server_turn(actor.id, runtime.fight.turn_id)
            for _ in range(32):
                token = runtime.awaiting_ack
                if token is None:
                    return
                runtime.acknowledge_turn(struct.pack(">i", token))
            self.fail("Native ACK chain exceeded32")

        for _ in range(8):
            if runtime.fight.current.id == 8:
                break
            advance()
        self.assertEqual(runtime.fight.current.id, 8)
        original = runtime.fight.actors[8].position
        before_mp = runtime.fight.actors[8].mp
        # Actual paid movement updates the retained QI tuple through the normal
        # Fight producer. The historical bug concerns movement BEFORE KO.
        runtime.fight.move(4, 8, [(-7, -7, -1)])
        moved = runtime.fight.actors[8].position
        self.assertNotEqual(moved, original)
        self.assertEqual(runtime.fight.actors[8].mp, before_mp - 1)
        slot = runtime.fight.actors[8].native_obstacle_id
        self.assertIs(
            type(current_registry(runtime.fight).slots[slot]["position"]), tuple
        )
        hits = []
        for _ in range(160):
            if runtime.fight.actors[8].hp == 0:
                break
            if runtime.fight.current.id == -7:
                rule = ability(monster)
                before = snapshot(runtime.fight)
                hp = runtime.fight.actors[8].hp
                ap = runtime.fight.current.ap
                tx = prepare_npc_spell(
                    runtime.fight,
                    dict(
                        type="cast",
                        spellId=rule["spell_id"],
                        level=rule["spell_level"],
                        targetId=8,
                        target=list(moved),
                    ),
                    characters[7],
                    monsters,
                    decks[7],
                    action_id=runtime.action_id + 1,
                    **common
                )
                self.assertEqual(snapshot(runtime.fight), before)
                self.assertEqual(tx.fight.actors[-7].ap, ap - tx.plan["costs"]["ap"])
                self.assertLess(tx.fight.actors[8].hp, hp)
                commit_spell_transaction(runtime, tx, stats_serializer=stats)
                hits.append(
                    dict(
                        spell=rule["spell_id"],
                        cost=tx.plan["costs"],
                        hp_before=hp,
                        hp_after=runtime.fight.actors[8].hp,
                    )
                )
            advance()
        self.assertTrue(hits)
        self.assertEqual(runtime.fight.actors[8].hp, 0, (initial_hp, hits))
        self.assertTrue(global_fighter_guards(runtime.fight, 8)["baG"])
        self.assertEqual(
            current_registry(runtime.fight).slots[slot]["identity"], ["actor", 8]
        )
        for _ in range(12):
            if runtime.fight.current.id == 7:
                break
            advance()
        self.assertEqual(runtime.fight.current.id, 7)
        spell_uid = next(
            uid
            for uid, reference, level in owned_spell_records(characters[7])
            if reference == 1535
        )

        def cast(cell):
            return prepare_server_spell(
                struct.pack(">qqiih", 7, spell_uid, *cell),
                characters[7],
                monsters,
                runtime.fight,
                3,
                decks[7],
                action_id=runtime.action_id + 1,
                line_of_sight=lambda a, b, phase: authoritative_visible(
                    1134, a, b, phase
                ),
                critical=False,
                **common
            )

        baseline = snapshot(runtime.fight)
        rng_before = rng.getstate()
        with self.assertRaises(ValueError):
            cast(runtime.fight.actors[9].position)
        self.assertEqual(snapshot(runtime.fight), baseline)
        self.assertEqual(rng.getstate(), rng_before)
        resource = tuple(runtime.fight.actors[7].effect_stats[k] for k in (2, 3, 4))
        tx = cast(moved)
        self.assertEqual(snapshot(runtime.fight), baseline)
        self.assertGreater(tx.fight.actors[8].hp, 0)
        self.assertEqual(
            tuple(tx.fight.actors[7].effect_stats[k] for k in (2, 3, 4)),
            tuple(
                value - tx.plan["costs"][key]
                for value, key in zip(resource, ("ap", "mp", "wp"))
            ),
        )
        self.assertGreater(sum(tx.plan["costs"][key] for key in ("ap", "mp", "wp")), 0)
        commit_spell_transaction(runtime, tx, stats_serializer=stats)
        self.assertEqual(runtime.fight.order.count(8), 1)
        self.assertEqual(
            current_registry(runtime.fight).slots[slot]["identity"], ["actor", 8]
        )
        self.assertIn(
            1144,
            {row.reference for row in runtime.fight.actors[8].state_ledger.entries},
        )
        for _ in range(16):
            if runtime.fight.current.id == 8:
                break
            advance()
        self.assertEqual(runtime.fight.current.id, 8)
        advance()  # Restored owned turn accepts its actual owner/counter.
        self.evidence = dict(
            initial_hp=initial_hp,
            moved_from=original,
            moved_to=moved,
            paid_hits=hits,
            resurrection_cost=tx.plan["costs"],
            restored_hp=runtime.fight.actors[8].hp,
        )

    def test_osamodas_paid_native_floor_capture_and_occupied_rejection(self):
        import audit_ready_start
        from wakfu_server.characters.captured_roster import (
            CapturedCreature,
            OwnedCapturedRoster,
        )
        from wakfu_server.combat_captured_profiles import native_captured_profiles
        from wakfu_server.combat_spell_grant_book import grant_record
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_summon_spellbook import actor_action_book

        observed = []

        def roster(character, breed, level, passive):
            self.assertEqual(breed, 2)  # Native installed Osamodas class.
            profile = native_captured_profiles()["5347"]
            slots = [None] * 10
            slots[3] = CapturedCreature(3, 5347, profile["native_profile_name"])
            available = [False] * 10
            available[3] = True
            character["captured_roster"] = OwnedCapturedRoster(
                character["id"], tuple(slots), tuple(available), 3
            ).to_record()

        def journey(runtime, character, monster, deck, ready_packets, stats):
            self.assertEqual(runtime.fight.current.id, character["id"])
            actor = runtime.fight.current
            self.assertEqual(actor.hp, actor.max_hp)
            grant = grant_record(runtime.fight, actor.id, 7348)
            self.assertIsNotNone(grant)
            monsters = {monster["id"]: monster}
            baseline = snapshot(runtime.fight)
            resources = tuple(actor.effect_stats[k] for k in (2, 3, 4))

            def attempt(cell, rng):
                return prepare_server_spell(
                    struct.pack(">qqiih", actor.id, grant["uid"], *cell),
                    character,
                    monsters,
                    runtime.fight,
                    character["account_id"],
                    deck,
                    action_id=runtime.action_id + 1,
                    critical=False,
                    rng=rng,
                    line_of_sight=lambda a, b, phase: authoritative_visible(
                        character["map_id"], a, b, phase
                    ),
                )

            rng = random.Random(7)
            before_rng = rng.getstate()
            with self.assertRaises(ValueError):
                attempt(runtime.fight.actors[monster["id"]].position, rng)
            self.assertEqual(snapshot(runtime.fight), baseline)
            self.assertEqual(rng.getstate(), before_rng)
            occupied = {row.position for row in runtime.fight.actors.values()}
            candidates = sorted(
                cell
                for cell in runtime.fight.walkable
                if cell not in occupied
                and 1
                <= abs(cell[0] - actor.position[0]) + abs(cell[1] - actor.position[1])
                <= 4
            )
            failures = []
            for cell in candidates:
                try:
                    tx = attempt(cell, rng)
                except ValueError as error:
                    self.assertEqual(snapshot(runtime.fight), baseline)
                    self.assertEqual(rng.getstate(), before_rng)
                    failures.append(str(error))
                    continue
                break
            else:
                self.fail(("No native eligible empty floor", failures))
            self.assertEqual(snapshot(runtime.fight), baseline)
            self.assertEqual(
                tuple(tx.fight.actors[actor.id].effect_stats[k] for k in (2, 3, 4)),
                tuple(
                    value - tx.plan["costs"][key]
                    for value, key in zip(resources, ("ap", "mp", "wp"))
                ),
            )
            self.assertGreater(
                sum(tx.plan["costs"][key] for key in ("ap", "mp", "wp")), 0
            )
            created = set(tx.fight.actors) - set(runtime.fight.actors)
            self.assertEqual(len(created), 1)
            identity = created.pop()
            child = tx.fight.actors[identity]
            self.assertEqual(child.native_summon_source["ref"], 5347)
            self.assertIs(child.native_summoned_from_symbiot, True)
            self.assertEqual(tuple(child.position), tuple(cell))
            self.assertEqual(
                tx.fight.native_captured_rosters[str(actor.id)]["selected_slot"], 3
            )
            self.assertEqual(child.native_controller_id, actor.id)
            self.assertEqual(
                [row["reference"] for row in actor_action_book(child)["actions"]],
                [7356, 7357, 7358],
            )
            self.assertEqual(
                current_registry(tx.fight).slots[child.native_obstacle_id]["identity"],
                ["actor", identity],
            )
            self.assertFalse(
                tx.fight.native_captured_rosters[str(actor.id)]["available"][3]
            )
            delivery = tx.fight.native_summon_creation_deliveries[identity]
            self.assertIn(
                (delivery["opcode"], bytes.fromhex(delivery["payload_hex"])), tx.packets
            )
            commit_spell_transaction(runtime, tx, stats_serializer=stats)
            for _ in range(len(runtime.fight.actors) * 3):
                if runtime.fight.current.id == identity:
                    break
                current = runtime.fight.current
                if current.controlled:
                    runtime.end_turn(current.owner_id, current.id, current.turn_count)
                else:
                    runtime.end_server_turn(current.id, runtime.fight.turn_id)
                for _ in range(32):
                    token = runtime.awaiting_ack
                    if token is None:
                        break
                    runtime.acknowledge_turn(struct.pack(">i", token))
            self.assertEqual(runtime.fight.current.id, identity)
            observed.append(
                dict(
                    cell=cell,
                    costs=tx.plan["costs"],
                    created=identity,
                    slot=child.native_obstacle_id,
                )
            )
            return observed[-1]

        with tempfile.TemporaryDirectory() as directory:
            report = audit_ready_start.run(
                Path(directory) / "ready.json",
                cases_override=[(2, 153, None)],
                preplacement_character_fixture_provider=roster,
                on_runtime=journey,
                turn_cycle=True,
                turn_steps=1,
            )
        self.assertEqual(len(observed), 1, report["rows"])
        self.assertTrue(report["source_stable"])
        self.evidence = observed[0]
