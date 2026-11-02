"""Two paid Pohl cycles with actual Jondo and native rooted-tentacle attacks.

Six persisted equipped level-245 Iops are a pre-Ready fixture premise. NPCs
retain native levels/stats/books. The bounded method does not claim victory;
the separate terminal method continues that same fight to its real outcome.
"""
import json
import os
import random
from pathlib import Path
import sys
import unittest

from postgres_case import PostgresCase

_SERVER_ROOT = Path(__file__).resolve().parents[1]
for _path in (_SERVER_ROOT / "tools", _SERVER_ROOT / "ai-service"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def native_effect_packet_identity(opcode, body):
    # prepare_native_delivery rewrites only the cvB action ID (bytes4:8).
    # Retain fight/special IDs and the complete native effect payload/UID.
    return opcode, bytes(body[:4]) + bytes(body[8:])


class NativeDamageProvenancePacketTests(unittest.TestCase):
    def test_native_delivery_renumber_preserves_effect_provenance_identity(self):
        import struct
        from wakfu_server.combat_native_action_ids import prepare_native_delivery

        original = (12613, struct.pack(">iii", 7, 11, -1) + b"native-effect-uid-621")
        delivered, _ = prepare_native_delivery((original,), fight_id=7, previous_id=90)
        self.assertNotEqual(original, delivered[0])
        self.assertEqual(
            native_effect_packet_identity(*original),
            native_effect_packet_identity(*delivered[0]),
        )
        changed = (12613, delivered[0][1][:-3] + b"622")
        self.assertNotEqual(
            native_effect_packet_identity(*original),
            native_effect_packet_identity(*changed),
        )


class PohlActualCycleTests(PostgresCase):
    def test_two_actual_ai_cycles_preserve_full_player_opportunity(self):
        self.run_actual_scene(terminal=False)

    def test_actual_ai_phase_cycle_and_paid_terminal_victory(self):
        self.run_actual_scene(terminal=True)

    def run_actual_scene(self, *, terminal):
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
            Path(
                os.environ.get(
                    "WAKFU_POHL_FIXTURE",
                    str(
                        Path(__file__).resolve().parent
                        / "fixtures/dungeon_transition_recovery/bad184v5.json"
                    ),
                )
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
        from wakfu_server.combat_join_registration import register_joined_fighter
        from wakfu_server.combat_heroes import player_actor
        from wakfu_server.combat_cosmetic_conditions import (
            initialize_fresh_player_cosmetics,
        )
        from wakfu_server.fight_store import join_participant

        characters, decks = {character["id"]: character}, {character["id"]: deck}
        occupied = {actor.position for actor in candidate.actors.values()}
        party_cells = sorted(set(candidate.placement[roles.player_team]) - occupied)
        self.assertGreaterEqual(len(party_cells), 5)
        for index, cell in enumerate(party_cells[:5]):
            joined, lease, joined_deck, _, _ = persisted_party_character(
                self.store,
                replace(build, active_spells=(*build.active_spells, 4784)),
                name="pohl-cycle-" + chr(97 + index),
                map_id=map_id,
                position=cell,
            )
            joined.update(instance_id=instance_id)
            with self.store.connection() as db:
                join_participant(
                    self.store,
                    db,
                    joined["account_id"],
                    lease,
                    joined["id"],
                    fight_id,
                    target_character_id=character["id"],
                    team=roles.player_team,
                )
            actor = player_actor(joined, roles.player_team)
            register_joined_fighter(candidate, actor, cell)
            characters[joined["id"]], decks[joined["id"]] = joined, joined_deck
        for member in characters.values():
            candidate.ready(member["account_id"])
        for index, (identity, member) in enumerate(characters.items(), 1):
            candidate, _ = prepare_server_initialization(
                member,
                monsters,
                candidate,
                member["account_id"],
                decks[identity],
                action_id=index,
                rng=random.Random(7),
                fight_start=index == len(characters),
                player_characters=characters,
                deck_blobs=decks,
            )
        from native_supreme_paid_component_runtime import PaidComponentRuntime

        paid = PaidComponentRuntime(
            candidate, characters, monsters, decks, map_id=map_id, seed=7
        )
        runtime = paid.runtime
        self.assert_two_actual_cycles(paid, boss_id, terminal=terminal)

    def assert_two_actual_cycles(self, paid, boss_id, *, terminal=False):
        from collections import Counter, deque
        from datetime import datetime, timezone
        from unittest.mock import patch
        import struct
        import time
        import uuid
        from native_visible_target_fixture import visible_target_cells
        from wakfu_server.combat_ground_support import fight_supported
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_protocol_reconstruction import decode_packet
        from wakfu_ai.native.native_oracle import NativeOracle
        from wakfu_ai.native.native_stats import NativeStats
        from wakfu_ai.transport.framed import FramedClient
        from wakfu_ai.transport.endpoint import tcp_address
        from wakfu_ai.bridge.jondo_entry import run_prepared_turn
        from tools.combat_audit_turns import advance_actual_turn

        player_id = paid.first
        rejection_counts = Counter()
        paid_hits = []
        receipt = dict(
            status="pending",
            cycles=[],
            actual_ai_turns=[],
            tentacle_attacks=[],
            native_effect_packets=[],
            boundaries=[],
            payments=paid.payments,
            scope="Actual configured durable Pohl final room; six normal persisted equipped245 Iops; all turn-capable NPCs use real Jondo. Original5403/5404 are ROOTED/STABILIZED/no-turn114 with empty books: their native7585 controller-end attacks are observed from committed packets, never fabricated movement or AI turns.",
        )
        output = Path(os.environ.get("WAKFU_POHL_RECEIPTS", "/tmp")) / (
            ("pohl-actual-terminal-" if terminal else "pohl-actual-cycles-")
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            + ".json"
        )
        paid.runtime.tactical_encounter_id = uuid.uuid4().hex

        def states():
            return {
                entry.reference
                for entry in paid.fight.actors[boss_id].state_ledger.entries
            }

        def hidden():
            counts = paid.fight.actors[boss_id].native_fight_property_counts
            return bool(counts.get(18) or counts.get(75))

        def living_tentacles():
            return tuple(
                sorted(
                    actor.id
                    for actor in paid.fight.actors.values()
                    if actor.hp > 0
                    and (getattr(actor, "native_summon_source", None) or {}).get("ref")
                    in (5403, 5404)
                )
            )

        def actor_facts(actor):
            source = getattr(actor, "native_summon_source", None)
            reference = (source or paid.monsters.get(actor.id, {})).get("ref")
            # Fight properties are dynamic, installed by snapshot/property
            # handlers. Ordinary actors can legitimately lack these fields;
            # absence is unknown here, never an empty set or world properties.
            properties = getattr(actor, "native_fight_properties", None)
            counts = getattr(actor, "native_fight_property_counts", None)
            return dict(
                id=actor.id,
                reference=reference,
                hp=actor.hp,
                position=actor.position,
                team=actor.team,
                properties=None if properties is None else sorted(properties),
                property_counts=None if counts is None else dict(counts),
                property_diagnostic_source="live_actor_dynamic_attributes",
                states=[entry.reference for entry in actor.state_ledger.entries],
            )

        def phase_facts():
            return dict(
                turn=paid.fight.turn_id,
                table=paid.fight.native_table_turn,
                actors=[actor_facts(actor) for actor in paid.fight.actors.values()],
                areas=[
                    dict(area_id=identity, record=area)
                    for identity, area in paid.fight.native_effect_areas.items()
                ],
                children=[
                    dict(
                        id=actor.id,
                        hp=actor.hp,
                        position=actor.position,
                        source=actor.native_summon_source,
                    )
                    for actor in paid.fight.actors.values()
                    if getattr(actor, "native_summon_source", None) is not None
                ],
            )

        receipt["initial_native_scene"] = phase_facts()
        # Native7585 retains Pohl as its original wire caster. Attribute
        # damage to the actual state carrier, then credit only emitted packets
        # returned by the committed runtime, never an oracle forecast.
        from wakfu_server.combat_damage_handler import NativeDamageHandler
        from wakfu_server.combat_native_container import resolve_state_container

        original_damage = NativeDamageHandler.__call__
        damage_origins = {}
        receipt["observed_damage_origins"] = []

        def observe_damage(handler, effect, values, invocation):
            if invocation.reference not in (341737, 341743):
                return original_damage(handler, effect, values, invocation)
            state = (
                resolve_state_container(handler.fight, invocation.state_uid)
                if invocation.state_uid is not None
                else None
            )
            origin = dict(
                state_uid=invocation.state_uid,
                state_reference=None if state is None else state.reference,
                carrier_id=None if state is None else state.target_id,
                source_cell=invocation.cell,
            )
            receipt["observed_damage_origins"].append(
                dict(
                    origin, definition=invocation.reference, target=invocation.target_id
                )
            )
            first_packet = len(handler.packets)
            result = original_damage(handler, effect, values, invocation)
            for opcode, body in handler.packets[first_packet:]:
                if opcode == 12613:
                    damage_origins[native_effect_packet_identity(opcode, body)] = origin
            return result

        self.enterContext(patch.object(NativeDamageHandler, "__call__", observe_damage))

        def consume(packets):
            for opcode, body in packets:
                if opcode not in (12613, 12614):
                    continue
                effect = decode_packet(opcode, body).get("effect", {})
                if (
                    341600 <= effect.get("definition", 0) < 341800
                    or effect.get("definition") == 409622
                ):
                    receipt["native_effect_packets"].append(
                        dict(
                            effect,
                            table=paid.fight.native_table_turn,
                            turn=paid.fight.turn_id,
                        )
                    )
                if (
                    effect.get("definition") in (341737, 341743)
                    and effect.get("target") in paid.characters
                ):
                    origin = damage_origins.get(
                        native_effect_packet_identity(opcode, body)
                    )
                    receipt["tentacle_attacks"].append(
                        dict(
                            effect,
                            origin=origin,
                            table=paid.fight.native_table_turn,
                            turn=paid.fight.turn_id,
                        )
                    )
                    self.assertIsNotNone(
                        origin,
                        "Committed tentacle damage lacks its native retained origin",
                    )
                    self.assertEqual(origin["state_reference"], 7585)
                    self.assertIn(origin["carrier_id"], paid.fight.actors)

        def advance():
            runtime = paid.runtime
            actor = paid.fight.current
            if actor.controlled:
                consume(advance_actual_turn(runtime))
                return
            source = getattr(actor, "native_summon_source", None)
            reference = source["ref"] if source else paid.monsters[actor.id]["ref"]
            row = dict(
                actor=actor.id,
                reference=reference,
                turn=paid.fight.turn_id,
                table=paid.fight.native_table_turn,
                before=actor.position,
                actions=[],
            )
            receipt["actual_ai_turns"].append(row)
            oracle = NativeOracle(
                runtime,
                characters=paid.characters,
                monsters=paid.monsters,
                decks=paid.decks,
                excluded_decks={identity: frozenset() for identity in paid.characters},
                viewer_id=paid.first,
                flags=dict(native_area_callbacks=True, native_start_events=True),
            )
            serializer = NativeStats(
                characters=paid.characters,
                monsters=paid.monsters,
                fight_id=paid.fight.id,
                map_id=paid.map_id,
            )
            channel = FramedClient(*tcp_address("tcp://ai-jondo:8091"), timeout=20)
            try:
                for packets, diagnostic in run_prepared_turn(
                    runtime,
                    oracle,
                    serializer,
                    channel,
                    deadline=time.monotonic() + 20,
                    max_actions=12,
                ):
                    row["actions"].append(diagnostic["action"])
                    consume(packets)
            except Exception as error:
                row["error"] = dict(type=type(error).__name__, message=str(error))
                raise
            finally:
                channel.close()
            for _ in range(32):
                if runtime.awaiting_ack is None:
                    break
                consume(
                    runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                )
            self.assertIsNone(runtime.awaiting_ack)
            self.assertFalse(runtime.pending)
            row["after"] = paid.fight.actors[actor.id].position
            self.assertTrue(
                paid.fight.phase == "finished" or paid.fight.turn_id != row["turn"]
            )

        def approach(target_id, ring=False):
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
            if (
                ring
                and 1
                <= abs(actor.position[0] - target.position[0])
                + abs(actor.position[1] - target.position[1])
                <= 2
            ):
                return False
            options = []
            for reference in (4778, 4777, 4780, 4781):
                casting, index = native_casting_table(reference, actor.effective_level)
                minimum, maximum = casting["levels"][index][:2]
                options.append((minimum, maximum, casting))
            if not ring and any(
                visible_target_cells(
                    paid.fight,
                    adapter.actor_authority,
                    paid.map_id,
                    actor,
                    target,
                    minimum=minimum,
                    maximum=maximum,
                    casting_flags=flags,
                    require_los=flags["line_of_sight"],
                )
                for minimum, maximum, flags in options
            ):
                return False
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
                if path and (
                    (
                        ring
                        and 1
                        <= abs(cell[0] - target.position[0])
                        + abs(cell[1] - target.position[1])
                        <= 2
                    )
                    or (
                        not ring
                        and any(
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
                        )
                    )
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
                rng_before = paid.rng.getstate()
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
                if transaction.fight.actors[player_id].position == before["position"]:
                    # A legal spell can have no eligible native movement
                    # recipient (for example an occupied landing). Discard
                    # that private preview and try another real destination.
                    rejection_counts["Native Jump preview has no relocation"] += 1
                    paid.rng.setstate(rng_before)
                    continue
                # Jump includes real native earth damage around SELF. Select
                # a safe movement opportunity; do not accidentally kill the
                # phase subject or a teammate while approaching the socket.
                if any(
                    transaction.fight.actors[identity].hp < prior.hp
                    for identity, prior in paid.fight.actors.items()
                ):
                    rejection_counts["Jump would cause collateral damage"] += 1
                    paid.rng.setstate(rng_before)
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

        def finish_terminal():
            nonlocal player_id
            player_team = paid.fight.actors[paid.first].team
            receipt["terminal_boundaries"] = []
            receipt["terminal_attempts"] = []
            last_table = None
            last_progress = None
            stagnant_tables = 0
            for _ in range(240):
                for _ack in range(32):
                    if paid.runtime.awaiting_ack is None:
                        break
                    consume(
                        paid.runtime.acknowledge_turn(
                            struct.pack(">i", paid.runtime.awaiting_ack)
                        )
                    )
                self.assertIsNone(paid.runtime.awaiting_ack)
                enemies = [
                    actor
                    for actor in paid.fight.actors.values()
                    if actor.team != player_team and actor.hp > 0
                ]
                receipt["terminal_boundaries"].append(
                    dict(
                        turn=paid.fight.turn_id,
                        table=paid.fight.native_table_turn,
                        phase=paid.fight.phase,
                        boss_hp=paid.fight.actors[boss_id].hp,
                        enemies=[actor_facts(actor) for actor in enemies],
                        players=[
                            actor_facts(paid.fight.actors[identity])
                            for identity in paid.characters
                        ],
                    )
                )
                if paid.fight.native_table_turn != last_table:
                    progress = (
                        len(paid.payments),
                        tuple(
                            (actor.id, actor.hp, actor.position) for actor in enemies
                        ),
                    )
                    stagnant_tables = (
                        stagnant_tables + 1 if progress == last_progress else 0
                    )
                    last_progress, last_table = progress, paid.fight.native_table_turn
                    self.assertLess(
                        stagnant_tables,
                        4,
                        "No paid player or enemy-state progress for four full terminal tables",
                    )
                if paid.fight.phase == "finished":
                    self.assertEqual(paid.fight.winner, player_team)
                    self.assertEqual(paid.fight.actors[boss_id].hp, 0)
                    self.assertFalse(enemies)
                    self.assertTrue(
                        any(
                            row["target"] == boss_id and row["after"]["hp"] == 0
                            for row in paid_hits
                        ),
                        "Pohl must receive a genuine paid lethal hit",
                    )
                    receipt["terminal"] = dict(
                        phase=paid.fight.phase,
                        winner=paid.fight.winner,
                        fully_closed_cycles=completed,
                        players={
                            identity: paid.fight.actors[identity].hp
                            for identity in paid.characters
                        },
                    )
                    receipt[
                        "status"
                    ] = "actual_ai_pohl_phase_and_paid_terminal_qualified"
                    return
                self.assertEqual(paid.fight.phase, "active")
                self.assertTrue(
                    all(
                        paid.fight.actors[identity].hp > 0
                        for identity in paid.characters
                    )
                )
                self.assertLessEqual(paid.fight.native_table_turn, 50)
                if paid.fight.current.controlled:
                    player_id = paid.fight.current.id
                    for _action in range(12):
                        if paid.fight.phase != "active" or paid.fight.current.ap < 2:
                            break
                        tentacles = living_tentacles()
                        if tentacles:
                            choices = tentacles
                        elif paid.fight.actors[boss_id].hp > 0 and not hidden():
                            choices = (boss_id,)
                        else:
                            choices = tuple(
                                actor.id
                                for actor in paid.fight.actors.values()
                                if actor.team != player_team
                                and actor.hp > 0
                                and actor.id != boss_id
                            )
                        if not choices:
                            break
                        choices = sorted(
                            choices,
                            key=lambda identity: (
                                abs(
                                    paid.fight.current.position[0]
                                    - paid.fight.actors[identity].position[0]
                                )
                                + abs(
                                    paid.fight.current.position[1]
                                    - paid.fight.actors[identity].position[1]
                                ),
                                identity,
                            ),
                        )
                        acted = False
                        for target in choices:
                            prior_rejections = dict(rejection_counts)
                            acted = attack(target) or approach(target)
                            receipt["terminal_attempts"].append(
                                dict(
                                    turn=paid.fight.turn_id,
                                    actor=player_id,
                                    target=target,
                                    acted=acted,
                                    player=actor_facts(paid.fight.actors[player_id]),
                                    enemy=actor_facts(paid.fight.actors[target]),
                                    rejections={
                                        key: value - prior_rejections.get(key, 0)
                                        for key, value in rejection_counts.items()
                                        if value > prior_rejections.get(key, 0)
                                    },
                                )
                            )
                            if acted:
                                break
                        if not acted:
                            break
                if paid.fight.phase == "active":
                    advance()
                if len(receipt["terminal_boundaries"]) == 1 or (
                    receipt["terminal_boundaries"][-1]["table"]
                    != paid.fight.native_table_turn
                ):
                    output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
            self.fail("Paid terminal continuation exceeded bounded native progress")

        cycle = None
        completed = 0
        seen_tentacles = set()
        try:
            for boundary in range(480):
                if terminal and paid.fight.actors[boss_id].hp <= 0:
                    self.assertIsNotNone(cycle)
                    self.assertTrue(
                        any(
                            row["target"] == boss_id and row["after"]["hp"] == 0
                            for row in paid_hits
                        )
                    )
                    self.assertTrue(cycle["boss_hits"])
                    self.assertIn("all_native_attacks_turn", cycle)
                    self.assertIn("last_kill_turn", cycle)
                    self.assertIn("reveal_turn", cycle)
                    receipt["natural_boss_death"] = dict(
                        turn=paid.fight.turn_id,
                        table=paid.fight.native_table_turn,
                        fully_closed_cycles=completed,
                        cycle_number=cycle["number"],
                        note="Paid lethal hit ends this phase naturally; no third birth is required after death.",
                    )
                    finish_terminal()
                    return
                self.assertEqual(paid.fight.phase, "active")
                self.assertLessEqual(paid.fight.native_table_turn, 36)
                self.assertTrue(
                    all(
                        paid.fight.actors[identity].hp > 0
                        for identity in paid.characters
                    ),
                    "Party must remain alive for full opportunity assertions",
                )
                born = living_tentacles()
                if hidden() and not born and cycle is None:
                    receipt["missing_first_birth"] = phase_facts()
                    self.fail(
                        "First native dive has no living tentacles; inspect actual scene/area and child evidence"
                    )
                if (
                    not receipt["boundaries"]
                    or receipt["boundaries"][-1]["table"]
                    != paid.fight.native_table_turn
                ):
                    receipt["progress"] = phase_facts()
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
                new_birth = bool(born) and not set(born) <= seen_tentacles
                if new_birth:
                    self.assertEqual(len(born), 4)
                    self.assertTrue(hidden())
                    self.assertIn(7583, states())
                    if cycle is not None:
                        self.assertEqual(cycle["stage"], "visible")
                        self.assertTrue(
                            cycle["boss_hits"],
                            "No paid hit in the real visible interval",
                        )
                        self.assertEqual(
                            set(cycle["completed_player_turns"]),
                            set(paid.characters),
                            "Rehide preceded a full opportunity turn for every player",
                        )
                        cycle["rehide_turn"] = paid.fight.turn_id
                        cycle["rehide_table"] = paid.fight.native_table_turn
                        completed += 1
                        if completed == 2:
                            receipt.update(
                                status="two_actual_ai_pohl_cycles_qualified",
                                completed_cycles=completed,
                            )
                            if terminal:
                                receipt[
                                    "two_cycle_qualification"
                                ] = "Passed before terminal continuation"
                                finish_terminal()
                            return
                    available = set(paid.characters)
                    assignments = {}
                    for child_id in born:
                        child = paid.fight.actors[child_id]
                        self.assertTrue(
                            {3, 11, 114} <= set(child.native_fight_properties)
                        )
                        self.assertNotIn(child_id, paid.fight.order)
                        chosen = min(
                            available,
                            key=lambda identity: sum(
                                abs(a - b)
                                for a, b in zip(
                                    paid.fight.actors[identity].position, child.position
                                )
                            ),
                        )
                        assignments[chosen] = child_id
                        available.remove(chosen)
                    cycle = dict(
                        number=len(receipt["cycles"]) + 1,
                        stage="attacks",
                        children=list(born),
                        birth_turn=paid.fight.turn_id,
                        birth_table=paid.fight.native_table_turn,
                        birth_positions={
                            identity: paid.fight.actors[identity].position
                            for identity in born
                        },
                        assignments=assignments,
                        boss_hits=[],
                        completed_player_turns=[],
                    )
                    receipt["cycles"].append(cycle)
                    seen_tentacles.update(born)
                if cycle is not None:
                    attackers = {
                        row["origin"]["carrier_id"]
                        for row in receipt["tentacle_attacks"]
                        if row["origin"]["carrier_id"] in cycle["children"]
                        and row["value"] > 0
                    }
                    if cycle["stage"] == "attacks" and attackers == set(
                        cycle["children"]
                    ):
                        cycle["stage"] = "kills"
                        cycle["all_native_attacks_turn"] = paid.fight.turn_id
                    living = [
                        identity
                        for identity in cycle["children"]
                        if paid.fight.actors[identity].hp > 0
                    ]
                    if cycle["stage"] == "kills" and not living:
                        cycle["stage"] = "await_reveal"
                        cycle["last_kill_turn"] = paid.fight.turn_id
                        self.assertTrue(
                            hidden(),
                            "Tentacle KO must not prematurely bypass the native own-start gate",
                        )
                    if cycle["stage"] == "await_reveal" and not hidden():
                        self.assertIn(7589, states())
                        cycle["stage"] = "visible"
                        cycle["reveal_turn"] = paid.fight.turn_id
                        cycle["reveal_table"] = paid.fight.native_table_turn
                        self.assertEqual(
                            sum(
                                area["reference"] == 1753
                                for area in paid.fight.native_effect_areas.values()
                            ),
                            8,
                        )
                actor = paid.fight.current
                receipt["boundaries"].append(
                    dict(
                        turn=paid.fight.turn_id,
                        table=paid.fight.native_table_turn,
                        actor=actor.id,
                        hidden=hidden(),
                        boss_states=sorted(states()),
                        stage=None if cycle is None else cycle["stage"],
                        boss_hp=paid.fight.actors[boss_id].hp,
                        players={
                            identity: dict(
                                hp=paid.fight.actors[identity].hp,
                                position=paid.fight.actors[identity].position,
                            )
                            for identity in paid.characters
                        },
                    )
                )
                visible_player = False
                if actor.controlled:
                    player_id = actor.id
                    visible_player = cycle is not None and cycle["stage"] == "visible"
                    if visible_player:
                        self.assertFalse(hidden())
                    for _ in range(8):
                        if paid.fight.current.ap < 2:
                            break
                        if cycle is None:
                            # Wait the native three-own-END dive. Jump also
                            # deals earth damage; premature approach is unsafe.
                            break
                        elif cycle["stage"] == "attacks":
                            target = cycle["assignments"].get(player_id)
                            if target is None:
                                if not approach(boss_id):
                                    break
                            elif not approach(target, ring=True):
                                break
                        elif cycle["stage"] == "kills":
                            living = [
                                identity
                                for identity in cycle["children"]
                                if paid.fight.actors[identity].hp > 0
                            ]
                            if not living:
                                break
                            target = min(
                                living,
                                key=lambda identity: sum(
                                    abs(a - b)
                                    for a, b in zip(
                                        paid.fight.current.position,
                                        paid.fight.actors[identity].position,
                                    )
                                ),
                            )
                            if not attack(target) and not approach(target):
                                break
                        elif visible_player and not cycle["boss_hits"]:
                            prior = len(paid_hits)
                            if attack(boss_id):
                                if (
                                    len(paid_hits) > prior
                                    and paid_hits[-1]["target"] == boss_id
                                ):
                                    cycle["boss_hits"].append(paid_hits[-1])
                                    break
                            elif not approach(boss_id):
                                break
                        else:
                            break
                    if (
                        cycle is not None
                        and cycle["stage"] == "kills"
                        and all(
                            paid.fight.actors[identity].hp <= 0
                            for identity in cycle["children"]
                        )
                    ):
                        self.assertTrue(hidden())
                        cycle["stage"] = "await_reveal"
                        cycle["last_kill_turn"] = paid.fight.turn_id
                    if visible_player:
                        self.assertFalse(
                            hidden(), "Boss hid during a player-owned opportunity"
                        )
                advance()
                if visible_player:
                    self.assertFalse(
                        hidden(), "Boss hid before the player's real END/ACK completed"
                    )
                    if player_id not in cycle["completed_player_turns"]:
                        cycle["completed_player_turns"].append(player_id)
            self.fail(
                (
                    "Two actual Pohl cycles exceeded bounded native progress",
                    receipt["boundaries"][-6:],
                    receipt["cycles"],
                )
            )
        except Exception as error:
            receipt.update(
                status="failed", error_type=type(error).__name__, error=str(error)
            )
            raise
        finally:
            receipt["rejections"] = dict(rejection_counts)
            receipt["paid_hits"] = paid_hits
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")


if __name__ == "__main__":
    unittest.main()
