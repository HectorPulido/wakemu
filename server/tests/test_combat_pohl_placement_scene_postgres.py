"""Durable Pohl placement and paid native dive/resurface opportunity.

The ordinary equipped level-245 Iop is an explicit pre-Ready fixture premise.
NPCs retain native levels and stats. Ordinary NPC offense is not simulated;
this is a phase-window regression, not a complete victory or balance claim.
"""
import json
import random
from pathlib import Path
import sys
import unittest

from postgres_case import PostgresCase

_SERVER_ROOT = Path(__file__).resolve().parents[1]
for _path in (_SERVER_ROOT / "tools",):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


class PohlPlacementScenePostgresTests(PostgresCase):
    def test_durable_placement_retry_binds_scene_before_native_consumers(self):
        from wakfu_server.combat_placement_policy import freeze
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.combat_encounter_scene_policy import (
            arena_scene,
            bind_scene,
            prepare_scene,
            scene_state_declarations,
        )
        from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene
        from wakfu_server.combat_encounter_scene_turn_order import (
            declared_turn_end_order,
        )
        from wakfu_server.combat_actor_snapshot import (
            initialize_fight_snapshots,
            native_actor_catalog,
        )
        from wakfu_server.combat_environment_glyphs import prepare_environment_glyphs
        from wakfu_server.combat_npc_spell import owned_spells
        from wakfu_server.combat_ai_callback_spells import (
            deliberate_spells,
            source_closure,
        )
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
        )
        from wakfu_server.combat_tactical_ai import NativeProvider
        from wakfu_server.combat_encounter_turn_end_order import turn_end_event_order
        from wakfu_server.equipment_stats import combat_resources
        from wakfu_server.fight_store import create as create_fight
        from wakfu_server.combat_encounter_roles import roles_from_record
        from wakfu_server.combat_terrain import local_arena, map_geometry
        from wakfu_server.dungeon_encounters import roster_members
        from wakfu_server.dungeon_runtime_config import level_selector

        fixture = json.loads(
            (
                Path(__file__).resolve().parent
                / "fixtures/dungeon_transition_recovery/bad184v5.json"
            ).read_text()
        )
        config = fixture["configuration"]
        room = next(row for row in config["topology"]["rooms"] if row["order"] == 2)
        compiled_room = next(
            row for row in config["compiled_plan"]["rooms"] if row["order"] == 2
        )
        map_id = config["route"]["start_map_id"]
        instance_id = (1 << 57) + map_id
        group_id = 902184
        from native_paid_party_fixture import (
            native_endgame_iop_build,
            persisted_party_character,
        )
        from dataclasses import replace

        build = native_endgame_iop_build()
        character, generation, deck, _resources, _gear = persisted_party_character(
            self.store,
            replace(build, active_spells=(*build.active_spells, 4784)),
            name="pohl-scene-placement",
            map_id=map_id,
            position=tuple(room["anchor"]),
        )
        account_id = character["account_id"]
        character.update(
            map_id=map_id,
            instance_id=instance_id,
            x=room["anchor"][0],
            y=room["anchor"][1],
            z=room["anchor"][2],
        )

        geometry = map_geometry(map_id)
        room_cells = set(map(tuple, room["cells"]))
        descriptor = room["encounter_scene"]
        arena_cells = room_cells - {
            tuple(row["cell"]) for row in descriptor.get("native_initial_glyphs", ())
        }
        source_anchor = tuple(room["anchor"])
        if source_anchor not in arena_cells:
            floor = 0 if room["order"] == 1 else -15
            source_anchor = min(
                (cell for cell in arena_cells if cell[2] == floor),
                key=lambda cell: (
                    abs(cell[0] - room["anchor"][0]) + abs(cell[1] - room["anchor"][1]),
                    cell,
                ),
            )
        section = dict(
            geometry,
            cells=tuple(arena_cells),
            edges=tuple(
                (tuple(start), tuple(end))
                for start, end in geometry["edges"]
                if tuple(start) in arena_cells and tuple(end) in arena_cells
            ),
        )
        roster = [
            dict(
                ref_id=row["ref_id"],
                count=row["count"],
                min_level=row["native_min_level"],
                max_level=row["native_max_level"],
                role=row["role"],
            )
            for row in compiled_room["monsters"]
        ]
        members = list(
            roster_members(
                instance_id,
                roster,
                asset_map_id=map_id,
                anchor=source_anchor,
                geometry=section,
                group_id=group_id,
                select_level=level_selector(config, room_order=2),
                player_slots=6,
                actor_id_base=100000 + group_id,
            )
        )
        catalog = native_actor_catalog()
        radii = [
            catalog["npc_profiles"][str(row["ref"])]["physical_radius"]
            for row in members
        ]
        source = prepare_scene(
            descriptor,
            scope=dict(
                map_id=map_id,
                instance_id=instance_id,
                group_id=group_id,
                room_order=2,
                policy_version=config["version"],
                route_key=config["route"]["key"],
                evidence_hashes=config["evidence_hashes"],
            ),
            room_cells=room_cells,
        )
        blockers = [
            tuple(row["cell"]) for row in descriptor.get("native_initial_glyphs", ())
        ]
        arena = local_arena(
            map_id,
            character["id"],
            source_anchor,
            [tuple(row[key] for key in ("x", "y", "z")) for row in members],
            compact=False,
            relocate_monsters=True,
            variation_seed=group_id,
            allowed_cells=room_cells,
            member_radii=radii,
            player_radius=catalog["default_actor_radius"],
            ordinary_npc_placement=True,
            full_room_scope=True,
            initial_obstacle_cells=blockers,
        )
        npc_positions = []
        for member, (_before, after) in zip(
            members,
            arena.get(
                "participant_positions",
                [
                    (
                        tuple(row[key] for key in ("x", "y", "z")),
                        tuple(row[key] for key in ("x", "y", "z")),
                    )
                    for row in members
                ],
            ),
        ):
            member.update(zip(("x", "y", "z"), after))
            npc_positions.append(tuple(after))
        # Match the normal Pohl factory caller: retain the room anchor as the
        # participant's world origin, then form the final arena from the
        # already relocated NPC seeds.
        player_position = source_anchor
        character.update(
            x=player_position[0], y=player_position[1], z=player_position[2]
        )
        arena = local_arena(
            map_id,
            character["id"],
            player_position,
            npc_positions,
            compact=False,
            relocate_monsters=False,
            member_radii=radii,
            allowed_cells=room_cells,
            full_room_scope=True,
        )
        arena = prepare_encounter_scene(character, members, arena)
        arena = arena_scene(source, arena, character, members)
        roles = roles_from_record(
            arena["native_encounter_roles"],
            map_id=map_id,
            monster_references=[row["ref"] for row in members],
        )

        fight_id = create_fight(
            self.store, account_id, generation, character["id"], team=roles.player_team
        )
        seeds = {
            0: [(character["x"], character["y"], character["z"])],
            1: [tuple(row[key] for key in ("x", "y", "z")) for row in members],
        }
        frozen = freeze(
            self.store,
            account_id=account_id,
            generation=generation,
            character_id=character["id"],
            fight_id=fight_id,
            map_id=map_id,
            instance_id=instance_id,
            selected_arena=arena,
            seeds=seeds,
        )
        # Reproduce the historical writer: its committed placement retained
        # terrain/glyph metadata but lost the phase scene. A normal retry must
        # heal that omission durably before either AI consumer sees the boss.
        with self.store.connection() as db:
            saved_before = db.execute(
                "SELECT layout FROM fight_placement_layouts WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()["layout"]
            db.execute(
                "UPDATE fight_placement_layouts "
                "SET layout=layout-'native_encounter_scene' WHERE fight_id=%s",
                (fight_id,),
            )
        retried = freeze(
            self.reopen(),
            account_id=account_id,
            generation=generation,
            character_id=character["id"],
            fight_id=fight_id,
            map_id=map_id,
            instance_id=instance_id,
            selected_arena=arena,
            seeds=seeds,
        )

        def durable_shape(value):
            if isinstance(value, dict):
                return {key: durable_shape(item) for key, item in value.items()}
            if isinstance(value, (tuple, list)):
                return [durable_shape(item) for item in value]
            if isinstance(value, (set, frozenset)):
                return sorted(durable_shape(item) for item in value)
            return value

        self.assertEqual(durable_shape(retried), durable_shape(frozen))
        # All downstream native consumers use the actual recovered DB arena.
        frozen = retried
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT layout FROM fight_placement_layouts WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()["layout"]
        self.assertEqual(saved["native_encounter_scene"], source)
        self.assertEqual(saved["wire_instance_id"], character["id"])
        self.assertEqual(source["scope"]["instance_id"], instance_id)
        self.assertEqual(saved, saved_before)
        self.assertEqual(frozen["native_encounter_scene"], source)
        # A subsequent retry with no fresh declaration uses the repaired row;
        # it must not depend on an in-memory-only patch in the first caller.
        scene_less_arena = dict(arena)
        scene_less_arena.pop("native_encounter_scene")
        self.assertEqual(
            freeze(
                self.reopen(),
                account_id=account_id,
                generation=generation,
                character_id=character["id"],
                fight_id=fight_id,
                map_id=map_id,
                instance_id=instance_id,
                selected_arena=scene_less_arena,
                seeds=seeds,
            ),
            frozen,
        )

        resources = combat_resources(character)
        monsters = {row["id"]: row for row in members}
        candidate, _placement_packets = create_placement(
            character,
            members,
            frozen,
            fight_id=fight_id,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=frozen["terrain_effect_id"],
            terrain_instance_id=group_id,
        )
        bound = bind_scene(candidate, frozen, monsters)
        self.assertEqual(bound, descriptor)
        boss_id = next(
            identity for identity, row in monsters.items() if row["ref"] == 5376
        )
        scene_bindings = candidate.native_encounter_scene["scope"]["actor_bindings"]
        self.assertIn(
            {
                "actor_id": boss_id,
                "ref": 5376,
                "descriptor_level": candidate.actors[boss_id].effective_level,
            },
            scene_bindings,
        )
        self.assertEqual(
            candidate.native_encounter_scene["descriptor"][
                "external_event_participants"
            ],
            descriptor["external_event_participants"],
        )

        prepare_environment_glyphs(candidate, frozen, group_id)
        wp = {
            character["id"]: (resources["wp"], resources["wp"]),
            **{
                identity: (row["wp"], row.get("max_wp", row["wp"]))
                for identity, row in monsters.items()
            },
        }
        initialize_fight_snapshots(
            candidate,
            characters={character["id"]: character},
            monsters=monsters,
            wp_resources=wp,
            running_effects={identity: () for identity in candidate.actors},
            initial_effect_uid=1,
            scene_state_declarations=scene_state_declarations(candidate, monsters),
        )
        candidate.ready(account_id)
        candidate, _ = prepare_server_initialization(
            character,
            monsters,
            candidate,
            account_id,
            deck,
            action_id=1,
            rng=random.Random(7),
            fight_start=True,
            player_characters={character["id"]: character},
            deck_blobs={character["id"]: deck},
        )
        characters = {character["id"]: character}
        decks = {character["id"]: deck}
        from native_supreme_paid_component_runtime import PaidComponentRuntime

        paid = PaidComponentRuntime(
            candidate, characters, monsters, decks, map_id=map_id, seed=7
        )
        runtime = paid.runtime
        from tools.combat_audit_turns import advance_actual_turn

        for _ in range(2 * len(runtime.fight.order)):
            if runtime.fight.current.id == boss_id:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, boss_id)
        self.assertEqual(
            declared_turn_end_order(runtime.fight, actor_id=boss_id), (1037, 1002)
        )
        order = turn_end_event_order(runtime.fight, actor_id=boss_id)
        self.assertEqual(order, (1037, 1002))

        owned = owned_spells(runtime.fight, monsters, player_characters=characters)
        before = dict(owned)
        self.assertTrue({7604, 7605} <= set(owned))
        # The native source chain proves these abilities are 426-owned callbacks;
        # they remain in the authoritative book while the advisory AI omits them.
        callback_ids = set()
        for row in descriptor["callback_owned_spells"]:
            _, spells = source_closure(row)
            callback_ids.update(spells)
        self.assertTrue({7604, 7605} <= callback_ids)
        advisory = deliberate_spells(runtime.fight, owned, monsters)
        self.assertEqual(owned, before)
        self.assertFalse({7604, 7605} & set(advisory))
        provider = NativeProvider(
            character,
            monsters,
            deck,
            player_characters=characters,
            deck_blobs=decks,
        )
        python_caps = provider.capabilities(runtime.fight)
        self.assertFalse({7604, 7605} & {row["spellId"] for row in python_caps})

        # Build the actual Jondo cap snapshot for the same current, bound actor.
        import uuid

        runtime.tactical_encounter_id = uuid.uuid4().hex
        from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle

        oracle = NativeOracle(
            runtime,
            characters=characters,
            monsters=monsters,
            decks=decks,
            excluded_decks={character["id"]: frozenset()},
            viewer_id=character["id"],
            flags=dict(native_area_callbacks=True, native_start_events=True),
        )
        from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import (
            build_snapshot,
        )

        jondo = build_snapshot(oracle, budget_ms=1000)
        self.assertFalse({7604, 7605} & {row["id"] for row in jondo["spells"]})
        self.assertEqual(oracle.owned_spells(runtime.fight), before)
        self.assert_paid_phase_window(paid, boss_id)

    def assert_paid_phase_window(self, paid, boss_id):
        from collections import Counter, deque
        from native_visible_target_fixture import visible_target_cells
        from wakfu_server.combat_ground_support import fight_supported
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_server_spell import server_runtime

        player_id = paid.first
        own_ends = 0
        born = ()
        rejection_counts = Counter()
        paid_hits = []

        def states():
            return {
                entry.reference
                for entry in paid.fight.actors[boss_id].state_ledger.entries
            }

        def children():
            return tuple(
                sorted(
                    actor.id
                    for actor in paid.fight.actors.values()
                    if (getattr(actor, "native_summon_source", None) or {}).get("ref")
                    in (5403, 5404)
                )
            )

        def hidden():
            props = paid.fight.actors[boss_id].native_fight_property_counts
            return bool(props.get(18) or props.get(75))

        # Automatic callbacks, real turns and real acknowledgments. Neither
        # phase spell is directly cast by this test.
        for _ in range(6 * len(paid.fight.order)):
            self.assertEqual(paid.fight.phase, "active")
            if paid.fight.current.id == boss_id:
                self.assertFalse(hidden())
                own_ends += 1
            prior_hp = paid.fight.actors[player_id].hp
            paid.advance()
            born = children()
            if born:
                self.assertEqual(paid.fight.actors[player_id].hp, prior_hp)
                break
        self.assertEqual(own_ends, 3)
        self.assertEqual(len(born), 4)
        self.assertIn(7583, states())
        self.assertTrue(hidden())
        born_hp = {identity: paid.fight.actors[identity].hp for identity in born}
        self.assertTrue(all(value > 0 for value in born_hp.values()))
        for _ in range(2 * len(paid.fight.order)):
            if paid.fight.current.id == player_id:
                break
            paid.advance()
        self.assertEqual(paid.fight.current.id, player_id)
        self.assertEqual(
            {identity: paid.fight.actors[identity].hp for identity in born}, born_hp
        )
        self.assertIn(7583, states())
        self.assertTrue(hidden())
        self.assertGreater(paid.fight.current.ap, 0)

        def approach(target_id):
            """BFS plans only; actual movement pays native MP/tackle/area costs."""
            actor, target = paid.fight.current, paid.fight.actors[target_id]
            _, adapter = server_runtime(
                paid.characters[player_id],
                paid.monsters,
                paid.decks[player_id],
                action_id=paid.runtime.action_id + 1,
                critical=False,
                **paid.common,
            )
            options = []
            for reference in (4778, 4777, 4780, 4781):
                casting, index = native_casting_table(reference, actor.effective_level)
                minimum, maximum = casting["levels"][index][:2]
                options.append((minimum, maximum, casting))
            blocked = set().union(
                *(
                    footprint(other.position, other.physical_radius)
                    for other in paid.fight.actors.values()
                    if other.hp > 0 and other.id != player_id
                )
            )
            blocked.update(
                tuple(area["cell"][:2])
                for area in paid.fight.native_effect_areas.values()
                if area.get("movement_blocking") is True
            )
            edges = {}
            for start, end in paid.fight.edges:
                edges.setdefault(tuple(start), []).append(tuple(end))
            pending, seen = deque([(tuple(actor.position), ())]), {
                tuple(actor.position)
            }
            while pending:
                cell, path = pending.popleft()
                if path and any(
                    visible_target_cells(
                        paid.fight,
                        adapter.actor_authority,
                        paid.map_id,
                        actor,
                        target,
                        minimum=minimum,
                        maximum=maximum,
                        source_cell=cell,
                        casting_flags=flags,
                        require_los=flags["line_of_sight"],
                    )
                    for minimum, maximum, flags in options
                ):
                    return paid.player_move_prefix(player_id, path) or jump(target_id)
                for end in sorted(edges.get(cell, ())):
                    if (
                        end not in seen
                        and end[:2] not in blocked
                        and fight_supported(paid.fight, end)
                    ):
                        seen.add(end)
                        pending.append((end, (*path, end)))
            return jump(target_id)

        def jump(target_id):
            """Use the owned native Jump; never grant MP or relocate an actor."""
            import struct
            from wakfu_server.combat_los import authoritative_visible
            from wakfu_server.combat_server_spell import prepare_server_spell
            from wakfu_server.combat_spell_commit import commit_spell_transaction

            actor, target = paid.fight.current, paid.fight.actors[target_id]
            casting, index = native_casting_table(4784, actor.effective_level)
            if actor.ap < casting["costs"][index][0]:
                return False
            minimum, maximum = casting["levels"][index][:2]
            distance = lambda cell: abs(cell[0] - target.position[0]) + abs(
                cell[1] - target.position[1]
            )
            destinations = sorted(
                (
                    cell
                    for cell in paid.fight.walkable
                    if minimum
                    <= abs(cell[0] - actor.position[0])
                    + abs(cell[1] - actor.position[1])
                    <= maximum
                    and distance(cell) < distance(actor.position)
                    and fight_supported(paid.fight, cell)
                ),
                key=lambda cell: (distance(cell), cell),
            )
            for cell in destinations:
                before = dict(position=actor.position, ap=actor.ap, mp=actor.mp)
                try:
                    transaction = prepare_server_spell(
                        struct.pack(
                            ">qqiih", player_id, (player_id << 32) | 4784, *cell
                        ),
                        paid.characters[player_id],
                        paid.monsters,
                        paid.fight,
                        actor.owner_id,
                        paid.decks[player_id],
                        action_id=paid.runtime.action_id + 1,
                        critical=False,
                        line_of_sight=lambda origin, destination, candidate: authoritative_visible(
                            paid.map_id,
                            origin,
                            destination,
                            candidate,
                            blocking_footprints={
                                other.id: footprint(
                                    other.position, other.physical_radius
                                )
                                for other in candidate.actors.values()
                                if other.hp > 0
                            },
                        ),
                        **paid.common,
                    )
                except ValueError as error:
                    rejection_counts[str(error)] += 1
                    continue
                commit_spell_transaction(
                    paid.runtime, transaction, stats_serializer=paid.stats
                )
                after = paid.fight.actors[player_id]
                self.assertGreater(transaction.plan["costs"]["ap"], 0)
                self.assertNotEqual(after.position, before["position"])
                paid.payments.append(
                    dict(
                        kind="player_jump",
                        reference=4784,
                        before=before,
                        costs=transaction.plan["costs"],
                        after=dict(position=after.position, ap=after.ap, mp=after.mp),
                    )
                )
                return True
            return False

        def attack(target_id):
            actor, target = paid.fight.current, paid.fight.actors[target_id]
            _, adapter = server_runtime(
                paid.characters[player_id],
                paid.monsters,
                paid.decks[player_id],
                action_id=paid.runtime.action_id + 1,
                critical=False,
                **paid.common,
            )
            for reference in (4778, 4777, 4780, 4781):
                casting, index = native_casting_table(reference, actor.effective_level)
                minimum, maximum = casting["levels"][index][:2]
                aims = visible_target_cells(
                    paid.fight,
                    adapter.actor_authority,
                    paid.map_id,
                    actor,
                    target,
                    minimum=minimum,
                    maximum=maximum,
                    casting_flags=casting,
                    require_los=casting["line_of_sight"],
                )
                for aim in aims:
                    try:
                        row = paid.cast(player_id, reference, target_id, aim_cell=aim)
                    except ValueError as error:
                        rejection_counts[str(error)] += 1
                        continue
                    self.assertGreater(
                        sum(row["costs"][key] for key in ("ap", "mp", "wp")), 0
                    )
                    if row["after"]["hp"] < row["before"]["hp"]:
                        paid_hits.append(row)
                    return True
            return False

        # Killing the original four must be earned with legal owned spells.
        # Keep the last-kill checkpoint before ending that player's turn.
        for _ in range(240):
            self.assertEqual(paid.fight.phase, "active")
            living = [
                identity for identity in born if paid.fight.actors[identity].hp > 0
            ]
            if not living:
                break
            if paid.fight.current.id == player_id:
                for _ in range(8):
                    living = [
                        identity
                        for identity in born
                        if paid.fight.actors[identity].hp > 0
                    ]
                    if not living or paid.fight.current.ap < 2:
                        break
                    actor = paid.fight.current
                    target_id = min(
                        living,
                        key=lambda identity: sum(
                            abs(a - b)
                            for a, b in zip(
                                actor.position, paid.fight.actors[identity].position
                            )
                        ),
                    )
                    if not attack(target_id) and not approach(target_id):
                        break
                if all(paid.fight.actors[identity].hp <= 0 for identity in born):
                    break
            paid.advance()
        self.assertTrue(
            all(paid.fight.actors[identity].hp <= 0 for identity in born),
            dict(rejections=rejection_counts, payments=paid.payments[-8:]),
        )
        self.assertEqual({row["target"] for row in paid_hits}, set(born))
        self.assertIn(7583, states())
        self.assertTrue(hidden())
        for _ in range(2 * len(paid.fight.order)):
            if paid.fight.current.id == boss_id:
                break
            paid.advance()
        self.assertEqual(paid.fight.current.id, boss_id)
        self.assertNotIn(7583, states())
        self.assertIn(7589, states())
        self.assertFalse(hidden())
        self.assertEqual(
            sum(
                area["reference"] == 1753
                for area in paid.fight.native_effect_areas.values()
            ),
            8,
        )

        # Establish an actionable vulnerability window through the same paid
        # player entry point, including native target/LOS validation.
        boss_hit = None
        window = []
        for _ in range(160):
            self.assertEqual(paid.fight.phase, "active")
            if len(window) < 24:
                window.append(
                    dict(
                        table=paid.fight.native_table_turn,
                        current=paid.fight.current.id,
                        phase=paid.fight.phase,
                        hidden=hidden(),
                        boss_states=sorted(states()),
                        boss_position=paid.fight.actors[boss_id].position,
                        player_position=paid.fight.actors[player_id].position,
                        player_ap=paid.fight.actors[player_id].ap,
                        player_mp=paid.fight.actors[player_id].mp,
                    )
                )
            if paid.fight.current.id == player_id and not hidden():
                for _ in range(8):
                    if attack(boss_id):
                        if paid_hits and paid_hits[-1]["target"] == boss_id:
                            boss_hit = paid_hits[-1]
                            break
                    elif not approach(boss_id):
                        break
                if boss_hit:
                    break
            paid.advance()
        self.assertIsNotNone(
            boss_hit,
            dict(
                window=window, rejections=rejection_counts, payments=paid.payments[-8:]
            ),
        )
        self.assertLess(boss_hit["after"]["hp"], boss_hit["before"]["hp"])


if __name__ == "__main__":
    unittest.main()
