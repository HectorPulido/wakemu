"""Real incident-template constructor lifecycle on a fresh, unpublished fight.

Only publication-generation resolution is a test transport seam. Records and
hashes, native constructors, QI, movement, spell preparation and turns are real.
The finished user checkpoint is source metadata, never restored as active state.
"""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch


class RiftConstructorQIBoundaryTests(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("WAKFU_QA_QI_INCIDENT") == "1",
        "Requires explicit private incident checkpoint and read-only published SQL QA",
    )
    def test_detached_property_constructor_precedes_qi_and_registered_batch(self):
        from wakfu_server import native_catalog, native_compiled_catalog as publications

        with native_catalog._database().connection() as db:
            published = db.execute(
                "SELECT generation FROM native_compiled_catalog_releases WHERE generation LIKE %s AND complete",
                ("74b385%",),
            ).fetchall()
        self.assertEqual(len(published), 1)
        generation = published[0]["generation"]
        backend = publications._store()
        manifest = backend.header(generation)
        self.assertEqual(manifest["source_revision"], native_catalog.release())
        header = dict(manifest, generation=generation, manifest_sha256=generation)
        header["descriptors"] = {
            name: publications.descriptor_for(header, name)
            for name in manifest["collections"]
        }

        def pinned_metadata(**kwargs):
            self.assertIn(
                kwargs.get("source_revision"), (None, manifest["source_revision"])
            )
            return header

        pin_context = patch.object(
            publications, "resolve_publication", side_effect=pinned_metadata
        )
        pin_context.start()
        self.addCleanup(pin_context.stop)
        from wakfu_server.store import Store
        from wakfu_server.combat_static_catalogs import (
            CompiledEffects,
            characteristic_registry,
        )
        from wakfu_server import rift_npc_creation
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_start,
            prepare_server_turn_end,
            prepare_server_spell,
        )
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_random_transaction import rollback_external_rng
        from wakfu_server.rift_dispatch_combat import finish_accepted_action
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.spells import validate_deck
        from rift_native_flow_fixture import build_flow_fixture

        checkpoint_path = Path(".runtime/qi-wave-282-20261024/checkpoint.private.json")
        checkpoint = json.loads(checkpoint_path.read_bytes())
        old = checkpoint["snapshot"]
        identities = [
            int(key) for key, actor in old["actors"].items() if actor.get("controlled")
        ]
        self.assertEqual(len(identities), 1)
        identity = identities[0]
        account = old["actors"][str(identity)]["owner_id"]
        store = Store(
            os.environ["WAKFU_DATABASE_URL"],
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        self.addCleanup(store.close)
        with store.connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            character = store.character(account, identity, db)
        # Current progress is legitimate; use its coherent source sheet without
        # resetting the character to the historical incident level.
        self.assertGreaterEqual(
            character["level"], old["actors"][str(identity)]["effective_level"]
        )
        print("QI placement QA current Hupper level:", character["level"])
        self.assertEqual(
            character["breed"], old["actors"][str(identity)]["native_hud_breed"]
        )
        before_path = Path(
            ".runtime/qi-wave-282-20261024/rift_npc_creation-live-before.py"
        )
        before_raw = before_path.read_bytes()
        self.assertEqual(
            hashlib.sha256(before_raw).hexdigest(),
            "b29733bed24f6de9a4f3c00674900f0fa907558dc47d1fb55ba4a658575b0da7",
        )
        node = next(
            n
            for n in ast.parse(before_raw).body
            if isinstance(n, ast.FunctionDef) and n.name == "install_native_wave"
        )
        namespace = dict(vars(rift_npc_creation))
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                str(before_path),
                "exec",
            ),
            namespace,
        )
        legacy_install = namespace["install_native_wave"]
        with patch.object(
            publications, "resolve_publication", side_effect=pinned_metadata
        ):
            compiled = CompiledEffects.from_published()
            state = old["rift_wave_state"]
            run = dict(
                catalog=deepcopy(state["catalog"]),
                policy=deepcopy(state["policy"]),
                seed=state["seed"],
                instance_id=state["instance_id"],
                wave=1,
            )
            component = build_flow_fixture(
                character,
                run,
                270000282,
                (-200,),
                (3,),
                compiled=compiled,
                registry=characteristic_registry(),
            )
            fight = component.fight
            deck = component.decks[identity]
            fight, opening = prepare_server_initialization(
                component.character,
                fight.rift_monsters,
                fight,
                account,
                deck,
                action_id=1,
                rng=component.rng,
                fight_start=True,
                player_characters=component.characters,
                deck_blobs=component.decks,
            )
            component.fight = fight

            def serialize(actor, current):
                if actor.controlled:
                    return actual_actor_stats(
                        component.characters[actor.id],
                        actor,
                        current.id,
                        wp_current=actor.effect_stats[4],
                        wp_maximum=actor.effect_maxima[4],
                        direction=actor.direction,
                        fight=current,
                    )
                return actual_monster_actor_stats(
                    current.rift_monsters[actor.id],
                    actor,
                    current.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                    direction=actor.direction,
                    fight=current,
                )

            def turn(current, *, actor_id, action_id, start):
                fn = prepare_server_turn_start if start else prepare_server_turn_end
                return fn(
                    component.character,
                    current.rift_monsters,
                    current,
                    deck,
                    actor_id=actor_id,
                    action_id=action_id,
                    rng=component.rng,
                    player_characters=component.characters,
                    deck_blobs=component.decks,
                )

            runtime = RuntimeMessages(
                fight,
                clock=lambda: 100.0,
                runtime_stats_serializer=serialize,
                expiration_runtime_factory=lambda *, action_id: component.runtime_factory(
                    runtime.fight, action_id=action_id
                ),
                turn_start_provider=lambda current, **kw: turn(
                    current, **kw, start=True
                ),
                turn_end_provider=lambda current, **kw: turn(
                    current, **kw, start=False
                ),
            )
            runtime.turn_started()

            def end_current():
                actor = runtime.fight.current
                self.assertIsNotNone(actor)
                packets = (
                    runtime.end_turn(
                        account, actor.id, current_wire_turn(runtime.fight)
                    )
                    if actor.controlled
                    else runtime.end_server_turn(actor.id, runtime.fight.turn_id)
                )
                if runtime.awaiting_ack is not None:
                    runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                return packets

            for _ in range(8):
                if runtime.fight.current.id == identity:
                    break
                end_current()
            self.assertEqual(runtime.fight.current.id, identity)
            fight = runtime.fight
            # Source-native constructor metadata for the no-innate seed only;
            # this is the ordinary producer used by dungeon NPC preparation.
            from wakfu_server.dungeon_combat_scaling import _prepare_constructor

            _prepare_constructor(fight.actors[-200], 3)
            fight.rift_wave_state["actor_id_pool"] = list(
                range(-1125900016355456, -1125900016355460, -1)
            )
            self.assertEqual(len(fight.rift_wave_state["actor_id_pool"]), 4)
            with fight.effect_resolution():
                fight.apply_effect_damage(identity, -200, fight.actors[-200].hp)
            self.assertIsNotNone(fight.rift_wave_state.get("pending_wave"))
            before_snapshot = snapshot(fight)
            rng_before = component.rng.getstate()

            # The accepted provider must be deterministic without consuming the
            # combat RNG or mutating its source preview. Only its private pool
            # is consumed, in exactly the frozen select_wave order.
            from wakfu_server.rift_dispatch_lifecycle import next_roster

            roster_previews = [deepcopy(fight), deepcopy(fight)]
            rosters = [
                next_roster(private, private.rift_wave_state["pending_wave"])
                for private in roster_previews
            ]
            self.assertEqual(rosters[0], rosters[1])
            self.assertEqual([row["ref"] for row in rosters[0]], [3, 4, 3215, 3])
            self.assertEqual(
                [row["id"] for row in rosters[0]],
                fight.rift_wave_state["actor_id_pool"],
            )
            positions = [
                tuple(row[key] for key in ("x", "y", "z")) for row in rosters[0]
            ]
            self.assertEqual(len(positions), len(set(positions)))
            self.assertTrue(set(positions) <= fight.walkable)
            self.assertTrue(
                all(
                    not private.rift_wave_state["actor_id_pool"]
                    for private in roster_previews
                )
            )
            from wakfu_server.rift_reinforcement_placement import select_positions
            from wakfu_server.combat_actor_snapshot import native_actor_catalog
            from wakfu_server.combat_obstacle_condition import footprint
            from wakfu_server.combat_pointer_qi_registry import (
                registered_obstacle,
                registered_population,
            )

            references = tuple(row["ref"] for row in rosters[0])
            state = fight.rift_wave_state
            self.assertEqual(
                select_positions(
                    fight, references=references, seed=state["seed"], wave=2
                ),
                tuple(positions),
            )
            alternative = select_positions(
                fight,
                references=references,
                seed=state["seed"] + ":placement-alternative",
                wave=2,
            )
            self.assertNotEqual(alternative, tuple(positions))
            registry = current_registry(fight)
            _, population = registered_population(registry)
            reserved = set()
            profiles = native_actor_catalog()["npc_profiles"]
            for row, position in zip(rosters[0], positions):
                covered = set(
                    footprint(position, profiles[str(row["ref"])]["physical_radius"])
                )
                self.assertFalse(covered & reserved)
                reserved.update(covered)
                for x, y in covered:
                    for slot in population(x, y):
                        obstacle = registered_obstacle(registry, slot)
                        self.assertFalse(
                            obstacle is not None and obstacle["movement_blocking"]
                        )
            self.assertTrue(
                any(
                    abs(position[0] - fight.actors[identity].position[0])
                    + abs(position[1] - fight.actors[identity].position[1])
                    > 1
                    for position in positions
                ),
                "The frozen witness must exercise placement beyond adjacent BFS cells",
            )
            self.assertEqual(snapshot(fight), before_snapshot)
            self.assertEqual(component.rng.getstate(), rng_before)

            def initialize(current, actors, monsters):
                # All births must already be registered when shared producers run.
                current_registry(current)
                self.assertTrue(all(actor.id in current.order for actor in actors))
                return ()

            @rollback_external_rng
            def successor(*, rng, legacy=False, reject=False):
                preview = deepcopy(fight)
                copy_runtime = deepcopy(runtime)
                copy_runtime.fight = preview
                if legacy:
                    with patch.object(
                        rift_npc_creation, "install_native_wave", legacy_install
                    ):
                        result = finish_accepted_action(
                            preview,
                            copy_runtime,
                            (),
                            initialize_actor=lambda *_: (),
                            initialize_wave=initialize,
                        )
                else:
                    result = finish_accepted_action(
                        preview,
                        copy_runtime,
                        (),
                        initialize_actor=lambda *_: (),
                        initialize_wave=initialize,
                    )
                if reject:
                    raise ValueError("Discard fully initialized successor")
                return result

            with self.assertRaisesRegex(ValueError, "physical_registration"):
                successor(rng=component.rng, legacy=True)
            self.assertEqual(snapshot(fight), before_snapshot)
            self.assertEqual(component.rng.getstate(), rng_before)
            with self.assertRaisesRegex(ValueError, "fully initialized successor"):
                successor(rng=component.rng, reject=True)
            self.assertEqual(snapshot(fight), before_snapshot)
            self.assertEqual(component.rng.getstate(), rng_before)
            result = successor(rng=component.rng)
            runtime = result.runtime
            fight = runtime.fight
            births = fight.rift_wave_state["wave_actor_ids"]
            self.assertEqual(
                [fight.rift_monsters[uid]["ref"] for uid in births], [3, 4, 3215, 3]
            )
            self.assertEqual(sum(op == 13091 for op, _ in result.packets), 4)
            for uid in births:
                self.assertEqual(fight.order.count(uid), 1)
            current_registry(fight)
            from wakfu_server.combat_multiplayer_wire import decode_added

            admissions = {
                value["actor_id"]: value
                for opcode, payload in result.packets
                if opcode == 13091
                for value in (decode_added(payload),)
            }
            self.assertEqual(set(admissions), set(births))
            native_birth_descriptors = []
            for uid in births:
                actor = fight.actors[uid]
                added = admissions[uid]
                self.assertEqual(added["fight_id"], fight.id)
                self.assertEqual(added["team"], actor.team)
                self.assertEqual(added["actor_type"], 0)
                self.assertEqual(added["stats"][0], 2)
                self.assertEqual(
                    struct.unpack_from(">iih", added["stats"], 1), actor.position
                )
                self.assertEqual(
                    struct.unpack_from(">b", added["stats"], 29)[0],
                    actor.native_obstacle_id,
                )
                appearance_index = next(
                    index
                    for index, (opcode, payload) in enumerate(result.packets)
                    if opcode == 12608
                    and payload[:3] == b"\x00\x01\x01"
                    and struct.unpack_from(">q", payload, 3)[0] == uid
                )
                admission_index = next(
                    index
                    for index, (opcode, payload) in enumerate(result.packets)
                    if opcode == 13091 and decode_added(payload)["actor_id"] == uid
                )
                self.assertLess(appearance_index, admission_index)
                appearance = result.packets[appearance_index][1]
                length = struct.unpack_from(">H", appearance, 11)[0]
                blob = appearance[13 : 13 + length]
                self.assertEqual(blob[0], 11)
                self.assertEqual(struct.unpack_from(">q", blob, 1)[0], uid)
                name_length = struct.unpack_from(">H", blob, 18)[0]
                world_fight = struct.unpack_from(">iBBBBbB", blob, 48 + name_length)
                self.assertEqual(world_fight[0], fight.id)
                self.assertEqual(world_fight[5], actor.native_obstacle_id)

                native_birth_descriptors.append(
                    blob[48 + name_length : 58 + name_length].hex()
                    + ":"
                    + str(fight.id)
                    + ":"
                    + str(actor.native_obstacle_id)
                )

            # The original installed client pW decoder and QI.i/QI.g execute
            # against the actual four wire descriptors. This is not the server
            # allocator or a Python approximation of the old-corpse alias case.
            import subprocess
            import tempfile

            oracle = Path(
                ".runtime/qi-wave-283-20261024/birth-qi-oracle/ProbeNativeWaveBirthQI.java"
            )
            with tempfile.TemporaryDirectory(
                prefix="wakemu-native-birth-qi-"
            ) as classes:
                subprocess.run(
                    [
                        "javac",
                        "-J-Xmx64m",
                        "-proc:none",
                        "-classpath",
                        "client/lib/*",
                        "-d",
                        classes,
                        "sniffer/java/ProbeNativeQIRegistry.java",
                        str(oracle),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                result_java = subprocess.run(
                    [
                        "java",
                        "-Xmx64m",
                        "-cp",
                        classes + os.pathsep + "client/lib/*",
                        "ProbeNativeWaveBirthQI",
                        *native_birth_descriptors,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertIn("PASS original pW/QI.i/QI.g births=4", result_java.stdout)
                print(result_java.stdout.strip())

            # Ordinary exterior appearance keeps its existing sentinel contract.
            from wakfu_server.combat_monster_world import spawn_monster

            exterior = spawn_monster(fight.rift_monsters[births[0]], group_id=fight.id)
            length = struct.unpack_from(">H", exterior, 11)[0]
            blob = exterior[13 : 13 + length]
            name_length = struct.unpack_from(">H", blob, 18)[0]
            exterior_fight = struct.unpack_from(">iBBBBbB", blob, 48 + name_length)
            self.assertEqual((exterior_fight[0], exterior_fight[5]), (-1, -1))
            original_monster = fight.rift_monsters[births[0]]
            original_actor = fight.actors[births[0]]
            with self.assertRaises(ValueError):
                spawn_monster(
                    original_monster, group_id=fight.id, fighter=original_actor
                )
            with self.assertRaises(ValueError):
                spawn_monster(
                    original_monster,
                    group_id=fight.id,
                    fighter=deepcopy(original_actor),
                    fight=fight,
                )
            malformed = deepcopy(fight)
            for invalid_byte in (-1, 127):
                malformed.actors[births[0]].native_obstacle_id = invalid_byte
                with self.assertRaises(ValueError):
                    spawn_monster(
                        malformed.rift_monsters[births[0]],
                        group_id=malformed.id,
                        fighter=malformed.actors[births[0]],
                        fight=malformed,
                    )
            del malformed
            skeleton = next(
                uid for uid in births if fight.rift_monsters[uid]["ref"] == 3215
            )
            self.assertTrue(
                any(
                    entry.reference == 61
                    for entry in fight.actors[skeleton].state_ledger.entries
                )
            )
            self.assertIn(20, fight.actors[skeleton].native_fight_properties)
            # Existing native ACK fencing completes the accepted birth boundary.
            if runtime.awaiting_ack is not None:
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
            for _ in range(12):
                if (
                    runtime.fight.current is not None
                    and runtime.fight.current.id == identity
                ):
                    break
                end_current()
            self.assertEqual(runtime.fight.current.id, identity)
            fight = runtime.fight
            book = validate_deck(
                deck,
                component.character["breed"],
                component.character["level"],
                character=component.character,
            )["active"]
            cast = None
            failures = []
            from wakfu_server.combat_los import authoritative_visible

            for ref in book:
                targets = (
                    [runtime.fight.actors[uid].position for uid in births]
                    + [runtime.fight.actors[identity].position]
                    + sorted(
                        destination
                        for origin, destination in runtime.fight.edges
                        if origin == runtime.fight.actors[identity].position
                        and destination in runtime.fight.walkable
                    )
                )
                for target in targets:

                    @rollback_external_rng
                    def prepare_opening(*, rng):
                        transaction = prepare_server_spell(
                            struct.pack(
                                ">qqiih", identity, (identity << 32) | ref, *target
                            ),
                            component.character,
                            runtime.fight.rift_monsters,
                            runtime.fight,
                            account,
                            deck,
                            action_id=runtime.action_id + 1,
                            critical=False,
                            rng=rng,
                            player_characters=component.characters,
                            deck_blobs=component.decks,
                            line_of_sight=lambda origin, target, state: authoritative_visible(
                                component.character["map_id"],
                                origin,
                                target,
                                state,
                                blocking_footprints={
                                    member.id: set(
                                        __import__(
                                            "wakfu_server.combat_obstacle_condition",
                                            fromlist=["footprint"],
                                        ).footprint(
                                            member.position[:2], member.physical_radius
                                        )
                                    )
                                    for member in state.actors.values()
                                    if member.hp > 0
                                },
                            ),
                        )
                        candidate = transaction.fight
                        from wakfu_server.combat_qi_movement import (
                            movement_blocked_cells,
                        )

                        native_steps = [
                            destination
                            for origin, destination in candidate.edges
                            if origin == candidate.actors[identity].position
                            and destination in candidate.walkable
                            and abs(destination[0] - origin[0])
                            + abs(destination[1] - origin[1])
                            == 1
                        ]
                        blocked = movement_blocked_cells(
                            candidate, candidate.actors[identity], native_steps
                        )
                        if (
                            candidate.phase != "active"
                            or candidate.current.id != identity
                            or not any(
                                destination not in blocked
                                for destination in native_steps
                            )
                        ):
                            raise ValueError(
                                "Legal spell does not open a native movement route"
                            )
                        return transaction

                    try:
                        transaction = prepare_opening(rng=component.rng)
                    except ValueError as error:
                        failures.append(str(error))
                        continue
                    commit_spell_transaction(
                        runtime, transaction, stats_serializer=serialize
                    )
                    cast = ref
                    break
                if cast is not None:
                    break
            self.assertIsNotNone(cast, repr(failures[-8:]))
            current_registry(runtime.fight)
            fight = runtime.fight
            from wakfu_server.combat_qi_movement import movement_blocked_cells

            candidates = sorted(
                target
                for origin, target in fight.edges
                if origin == fight.current.position
                and target in fight.walkable
                and abs(target[0] - origin[0]) + abs(target[1] - origin[1]) == 1
            )
            blocked = movement_blocked_cells(fight, fight.current, candidates)
            candidates = [target for target in candidates if target not in blocked]
            self.assertTrue(candidates)
            route = [candidates[0]]
            body = struct.pack(">q", identity) + b"".join(
                struct.pack(">iih", *cell) for cell in route
            )
            movement = apply_client(
                runtime,
                account,
                body,
                lambda actor: serialize(actor, runtime.fight),
                runtime_stats_serializer=serialize,
                area_provider=lambda current, **kw: prepare_area_movement(
                    component.character,
                    current.rift_monsters,
                    current,
                    deck,
                    rng=component.rng,
                    player_characters=component.characters,
                    deck_blobs=component.decks,
                    **kw
                ),
            )
            self.assertEqual(runtime.fight.actors[identity].position, route[-1])
            current_registry(runtime.fight)
            before_turn = runtime.fight.turn_id
            end_current()
            self.assertGreater(runtime.fight.turn_id, before_turn)
            self.assertEqual(len(runtime.fight.order), len(set(runtime.fight.order)))
            current_registry(deepcopy(runtime.fight))
            stale = deepcopy(runtime.fight)
            del stale.actors[skeleton]
            with self.assertRaisesRegex(ValueError, "physical_registration"):
                current_registry(stale)
