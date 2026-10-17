"""Private proposed persisted representative full-combat regressions.

Luna executes only after source review/install approval. Native paid actions,
normal turn ACKs, real lethal damage and owned return; never HP/state/AP gifts.
"""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
from random import Random
import struct

from postgres_case import PostgresCase
from native_recorded_instance_fixture import original_bootstrap_publication
from wakfu_server import health_store, wire, fight_store, combat_health
from wakfu_server.progression import level_xp
from wakfu_server.equipment_stats import combat_resources
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_terrain import local_arena
from wakfu_server import combat_actor_snapshot
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_start,
    prepare_server_turn_end,
    server_runtime,
)
from wakfu_server.combat_npc_spell import prepare_npc_spell, owned_spells
from wakfu_server.combat_npc_initialization import initial_plans
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_timeline_snapshot import current_wire_turn
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_results import (
    finish_messages,
    continuation,
    outside_fight_updates,
)
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.monsters import owned_instance, native_abilities
from wakfu_server.spells import encode_deck, available_spells

EXPECTED_REVISION = "35328aee9ef15ee616a0a31a5994be00bae2ac533b096b0c5b156ab495d860fa"


class MonsterRepresentativeFullCombatTests(PostgresCase):
    def test_common_jalato_native_paid_exchange_normal_victory_and_owned_return(self):
        self._case(1, 8)

    def test_royal_bouftou_native_paid_exchange_normal_victory_and_owned_return(self):
        self._case(44, 23)

    def test_arch_bouftou_native_paid_exchange_normal_victory_and_owned_return(self):
        self._case(4086, 23)

    def _case(self, reference, level):
        # Keep mutable Store schemas in PostgresCase's dedicated test database.
        # Runtime/catalog reads remain on a separate explicitly readonly DSN.
        import psycopg
        from psycopg.conninfo import conninfo_to_dict

        reader_url = os.environ["WAKFU_DATABASE_URL"]
        self.assertIn("default_transaction_read_only=on", reader_url)
        self.assertNotEqual(
            conninfo_to_dict(reader_url)["dbname"],
            conninfo_to_dict(self.database_url)["dbname"],
        )
        with psycopg.connect(
            reader_url,
            password=Path(os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
            .read_text()
            .strip(),
        ) as db:
            self.assertEqual(
                db.execute("SHOW transaction_read_only").fetchone()[0], "on"
            )
            self.assertEqual(
                db.execute(
                    "SELECT revision FROM native_catalog_active WHERE id=1"
                ).fetchone()[0],
                EXPECTED_REVISION,
            )
        evidence = {
            "reference": reference,
            "level": level,
            "catalog_revision": EXPECTED_REVISION,
            "status": "pending",
            "actions": [],
            "boundaries": [],
            "scope": "Three selected offline persisted combat callers; not whole species/boss encounter or AI strategy qualification",
        }

        def emit():
            directory = os.environ.get("WAKFU_MONSTER_REPRESENTATIVE_EVIDENCE_DIR")
            if directory:
                folder = Path(directory).resolve()
                self.assertIn(".runtime", folder.parts)
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / (str(reference) + ".json")
                self.assertFalse(
                    path.exists(), "Representative evidence path must be fresh"
                )
                path.write_text(json.dumps(evidence, indent=2, default=str) + "\n")

        self.addCleanup(emit)
        account = self.store.register(
            "representative-" + str(reference), "local-test-password"
        )["id"]
        char = self.store.create_character(account, "Native Representative", breed=8)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, char["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=200,map_id=1134,instance_id=0,x=-9,y=-7,z=-1 WHERE id=%s",
                (char["id"],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(200), char["id"]),
            )
        char = health_store.initialize(self.store, account, generation, char["id"])
        self.assertIn(4780, {s["id"] for s in available_spells(8, 200)})
        deck = encode_deck([4780])
        sheet = b"".join(
            wire.proto_field(t, v)
            for t, v in ((8, 0), (18, b"Representative"), (24, 200), (56, 0))
        )
        char = self.store.save_build(
            account,
            generation,
            char["id"],
            0,
            dict(sheet=sheet, equipment=b"", deck=deck, aptitudes=b""),
        )
        char = self.store.character(account, char["id"])
        self.assertEqual((char["breed"], char["level"]), (8, 200))
        self.assertEqual(char["hp"], char["max_hp"])
        resources = combat_resources(char)
        terrain = local_arena(
            1134,
            0,
            (-9, -7, -1),
            (-8, -7, -1),
            relocate_monsters=False,
            compact=True,
            variation_seed=1,
            minimum_dimensions=(9, 9),
        )
        for cell in ((-9, -7, -1), (-8, -7, -1)):
            self.assertIn(cell, terrain["validated_cells"])
        monster = owned_instance(reference, level, -200, map_id=1134, x=-8, y=-7, z=-1)
        expected_book = {
            r["spell_id"]: r["spell_level"] for r in native_abilities(reference, level)
        }
        self.assertTrue(expected_book)
        evidence["native_owned_book"] = expected_book
        fight_id = fight_store.create(self.store, account, generation, char["id"])
        terrain_id = 900000 + char["id"]
        fight, _ = create_placement(
            char,
            monster,
            terrain,
            fight_id=fight_id,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=46,
            terrain_instance_id=terrain_id,
        )
        self.assertNotIn(terrain_id, fight.actors)
        # Original bje.cle is empty for Jalato and nonempty for these two
        # selected relatives. Check the actual activation-derived constructor
        # plan; absence of a receipt is legitimate only for the empty plan.
        native_triples = {1: (), 44: (4404, 30, 0, 5597, 1, 1), 4086: (4404, 30, 0)}[
            reference
        ]
        expected_initialization = initial_plans(fight, {-200: monster})
        self.assertEqual(
            set(expected_initialization), {-200} if native_triples else set()
        )
        if native_triples:
            planned_reference, planned_raw, planned_states = expected_initialization[
                -200
            ]
            self.assertEqual(
                (planned_reference, planned_raw), (reference, native_triples)
            )
        # Bind the real native publication adapter BEFORE snapshot construction.
        with original_bootstrap_publication() as publication:
            combat_actor_snapshot.initialize_fight_snapshots(
                fight,
                characters={char["id"]: char},
                monsters={-200: monster},
                wp_resources={
                    char["id"]: (resources["wp"], resources["wp"]),
                    -200: (monster["wp"], monster["wp"]),
                },
                running_effects={char["id"]: (), -200: ()},
                initial_effect_uid=1,
            )
        evidence["recorded_context2_replay"] = publication
        for actor in fight.actors.values():
            actor.direction = 0 if actor.controlled else 3
        self.assertEqual(
            (fight.actors[char["id"]].hp, fight.actors[char["id"]].max_hp),
            (char["hp"], char["max_hp"]),
        )
        session = Session(account, char["id"], generation, 1134, 0)
        registry = Registry(lambda current: current == session)
        shared = registry.register(fight, session)
        rng = Random(7)

        def stats(actor, preview):
            self.assertIs(preview.actors[actor.id], actor)
            values = dict(
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                fight=preview,
            )
            return (
                actual_actor_stats(char, actor, preview.id, **values)
                if actor.controlled
                else actual_monster_actor_stats(monster, actor, preview.id, **values)
            )

        def unbound_stats(*_):
            raise ValueError("Native statistics require actual matching Fight")

        def initialize(preview, action_id):
            return prepare_server_initialization(
                char,
                {-200: monster},
                preview,
                account,
                deck,
                action_id=action_id,
                rng=rng,
                fight_start=True,
            )

        def ready(candidate, runtime):
            started, new_runtime, packets = prepare_ready(
                candidate,
                account,
                True,
                initialize=initialize,
                stats_serializer=unbound_stats,
                runtime_stats_serializer=stats,
                effects_serializer=actor_effects,
                turn_end_provider=lambda p, **b: prepare_server_turn_end(
                    char, {-200: monster}, p, deck, rng=rng, **b
                ),
                turn_start_provider=lambda p, **b: prepare_server_turn_start(
                    char,
                    {-200: monster},
                    p,
                    deck,
                    rng=rng,
                    native_events=True,
                    area_callbacks=True,
                    **b
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    char,
                    {-200: monster},
                    deck,
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                )[0],
            )
            return Transition(started, new_runtime, tuple(packets))

        registry.execute(fight_id, session, char["id"], ready, require_turn=False)
        fight_store.activate(self.store, account, generation, char["id"], fight_id)
        self.assertTrue(shared.fight.native_start_event_delivered)
        initialization_receipts = getattr(
            shared.fight, "native_npc_initialization_receipts", {}
        )
        self.assertEqual(set(initialization_receipts), set(expected_initialization))
        for identity, (
            planned_reference,
            planned_raw,
            planned_states,
        ) in expected_initialization.items():
            receipt = initialization_receipts[identity]
            self.assertIs(receipt["initialized"], True)
            self.assertEqual(
                (receipt["ref"], receipt["descriptor_level"]),
                (planned_reference, level),
            )
            self.assertEqual(receipt["raw_triples"], list(planned_raw))
            self.assertEqual(
                receipt["resolved_states"], [asdict(item) for item in planned_states]
            )
            self.assertEqual(
                receipt["applications"],
                [
                    dict(state_id=item.state_id, level=item.level, applied=True)
                    for item in planned_states
                ],
            )
        evidence["initialization"] = deepcopy(initialization_receipts)
        evidence["native_constructor_required"] = bool(expected_initialization)
        evidence["native_initial_state_triples"] = list(native_triples)
        received = []

        def drain():
            for batch in registry.drain(fight_id, session):
                received.extend(batch.packets)

        drain()

        def submit(operation):
            current = shared.fight.current
            self.assertIsNotNone(current)
            if current.controlled:
                registry.execute(
                    fight_id,
                    session,
                    current.id,
                    operation,
                    expected_sequence=shared.sequence,
                )
            else:
                registry.execute_server(
                    fight_id, current.id, operation, expected_sequence=shared.sequence
                )
            self.assertIs(shared.runtime.fight, shared.fight)
            drain()

        def end_ack():
            previous = shared.fight.turn_id
            identity = shared.fight.current.id

            def end(candidate, runtime):
                current = candidate.current
                packets = (
                    runtime.end_turn(
                        current.owner_id, current.id, current_wire_turn(candidate)
                    )
                    if current.controlled
                    else runtime.end_server_turn(current.id, candidate.turn_id)
                )
                return Transition(runtime.fight, runtime, tuple(packets))

            submit(end)
            pending = shared.runtime.awaiting_ack
            if shared.fight.phase == "active":
                self.assertIsNotNone(pending)
            if pending is not None:
                body = struct.pack(">i", pending)

                def release(candidate, runtime, wire_body):
                    packets = runtime.acknowledge_turn(wire_body)
                    return Transition(runtime.fight, runtime, tuple(packets))

                self.assertTrue(registry.acknowledge(fight_id, session, body, release))
                drain()
                self.assertIsNone(shared.runtime.awaiting_ack)
            evidence["boundaries"].append(
                {
                    "actor": identity,
                    "from_turn": previous,
                    "to_turn": shared.fight.turn_id,
                    "ack": pending,
                }
            )

        def los(origin, destination, current):
            return authoritative_visible(
                1134,
                origin,
                destination,
                current,
                blocking_footprints={
                    a.id: footprint(a.position, a.physical_radius)
                    for a in current.actors.values()
                    if a.hp > 0
                },
            )

        npc_hits = player_hits = 0
        for boundary in range(40):
            if shared.fight.phase == "finished":
                break
            self.assertEqual(shared.fight.phase, "active")
            current = shared.fight.current
            target_id = -200 if current.controlled else char["id"]
            # First player turn deliberately yields, so the native NPC must
            # make a real paid damaging hit before this high-level PC attacks.
            if current.controlled and npc_hits == 0:
                end_ack()
                continue
            before_hp = shared.fight.actors[target_id].hp
            before = snapshot(shared.fight, runtime=shared.runtime)
            if current.controlled:
                chosen = 4780
            else:
                self.assertEqual(
                    owned_spells(shared.fight, {-200: monster}), expected_book
                )
                chosen = None
                rejections = []
                for spell, spell_level in sorted(expected_book.items()):
                    action = dict(
                        type="cast",
                        spellId=spell,
                        level=spell_level,
                        target=list(shared.fight.actors[target_id].position),
                        targetId=target_id,
                    )
                    try:
                        preview = prepare_npc_spell(
                            shared.fight,
                            action,
                            char,
                            {-200: monster},
                            deck,
                            action_id=shared.runtime.action_id + 1,
                            rng=Random(7),
                        )
                        self.assertEqual(
                            snapshot(shared.fight, runtime=shared.runtime), before
                        )
                        if (
                            preview.plan["costs"]["ap"] > 0
                            and preview.fight.actors[target_id].hp < before_hp
                        ):
                            chosen = spell
                            break
                        rejections.append(
                            {"spell": spell, "reason": "No paid actual target damage"}
                        )
                    except Exception as error:
                        rejections.append(
                            {
                                "spell": spell,
                                "type": type(error).__name__,
                                "reason": str(error),
                            }
                        )
                evidence.setdefault("npc_native_preflights", []).append(rejections)
                self.assertIsNotNone(
                    chosen,
                    "No legal native paid damaging action; preserve pending scene/guard facts",
                )
            cast_record = {}

            def cast(candidate, runtime):
                actor = candidate.current
                target = candidate.actors[target_id]
                resource_before = {str(k): actor.effect_stats[k] for k in (2, 3, 4)}
                if actor.controlled:
                    transaction = prepare_server_spell(
                        struct.pack(
                            ">qqiih",
                            actor.id,
                            (actor.id << 32) | chosen,
                            *target.position
                        ),
                        char,
                        {-200: monster},
                        candidate,
                        account,
                        deck,
                        action_id=runtime.action_id + 1,
                        line_of_sight=los,
                        critical=None,
                        rng=rng,
                    )
                else:
                    action = dict(
                        type="cast",
                        spellId=chosen,
                        level=expected_book[chosen],
                        target=list(target.position),
                        targetId=target_id,
                    )
                    transaction = prepare_npc_spell(
                        candidate,
                        action,
                        char,
                        {-200: monster},
                        deck,
                        action_id=runtime.action_id + 1,
                        rng=rng,
                    )
                costs = transaction.plan["costs"]
                self.assertGreater(costs["ap"], 0)
                stable = snapshot(candidate, runtime=runtime)
                pending_before = deepcopy(runtime.pending)
                if not evidence["actions"]:

                    def failed(*_):
                        raise ValueError("Representative native serializer rollback")

                    with self.assertRaisesRegex(
                        ValueError, "Representative native serializer rollback"
                    ):
                        commit_spell_transaction(
                            runtime, transaction, stats_serializer=failed
                        )
                    self.assertEqual(snapshot(candidate, runtime=runtime), stable)
                    self.assertEqual(runtime.pending, pending_before)
                packets = commit_spell_transaction(
                    runtime, transaction, stats_serializer=stats
                )
                self.assertIs(runtime.fight, transaction.fight)
                live = runtime.fight.actors[actor.id]
                for key, cost in ((2, "ap"), (3, "mp"), (4, "wp")):
                    self.assertEqual(
                        live.effect_stats[key], resource_before[str(key)] - costs[cost]
                    )
                cast_record.update(
                    actor_id=actor.id,
                    spell=chosen,
                    costs=deepcopy(costs),
                    resources_before=resource_before,
                    resources_after={str(k): live.effect_stats[k] for k in (2, 3, 4)},
                    target_id=target_id,
                    target_hp_before=before_hp,
                    target_hp_after=runtime.fight.actors[target_id].hp,
                    packets=[
                        {"opcode": op, "sha256": sha256(body).hexdigest()}
                        for op, body in packets
                    ],
                )
                return Transition(runtime.fight, runtime, tuple(packets))

            submit(cast)
            self.assertLess(shared.fight.actors[target_id].hp, before_hp)
            evidence["actions"].append(cast_record)
            if current.controlled:
                player_hits += 1
            else:
                npc_hits += 1
            if shared.fight.phase != "finished":
                end_ack()
        self.assertGreaterEqual(npc_hits, 1)
        self.assertGreaterEqual(player_hits, 1)
        self.assertEqual(
            (shared.fight.phase, shared.fight.winner),
            ("finished", 0),
            "Real native lethal combat did not resolve within finite40boundaries; no phase/HP override permitted",
        )
        self.assertEqual(shared.fight.actors[-200].hp, 0)
        self.assertNotIn(-200, shared.fight.order)
        self.assertGreater(shared.fight.actors[char["id"]].hp, 0)
        self.assertTrue(
            any(
                e.get("kind") == "death" and e.get("actor_id") == -200
                for e in shared.fight.events
            )
        )
        metadata = {
            char["id"]: dict(
                kind="player",
                account_id=account,
                name=char["name"],
                breed=8,
                is_male=char.get("sex", 0) == 0,
            ),
            -200: dict(kind="monster", ref=reference),
        }

        def settle_packets(live):
            # Encode on a private runtime so a failed DB settlement cannot
            # publish or mutate the authoritative action queue.
            private_runtime = deepcopy(live.runtime)
            terminal = finish_messages(
                private_runtime,
                metadata,
                duration_ms=1000,
                fight_instance_id=terrain_id,
                initiator_id=char["id"],
            )
            self.assertEqual([op for op, _ in terminal], [12755, 12238])
            with self.store.connection() as db:
                fight_store.finish(
                    self.store, db, account, generation, char["id"], fight_id
                )
            return {account: terminal}

        self.assertTrue(registry.settle_finished(fight_id, session, settle_packets))
        self.assertFalse(registry.settle_finished(fight_id, session, settle_packets))
        drain()
        self.assertEqual(
            [op for op, _ in received if op in (12755, 12238)], [12755, 12238]
        )
        self.assertIsNotNone(registry.lookup_character(char["id"]))
        with self.assertRaises(ValueError):
            continuation(fight_id, struct.pack(">iB", fight_id + 1, 1))
        self.assertIsNotNone(registry.lookup_character(char["id"]))
        self.assertTrue(continuation(fight_id, struct.pack(">iB", fight_id, 1)))
        returned = combat_health.persist(
            self.store, account, generation, char, shared.fight, reason="return"
        )
        self.assertTrue(returned["applied"])
        final_actor = shared.fight.actors[char["id"]]
        expected_damage = max(
            0,
            char["hp_damage"]
            + (final_actor.max_hp - final_actor.hp)
            - (char["max_hp"] - char["hp"]),
        )
        self.assertEqual(
            (
                returned["character"]["hp"],
                returned["character"]["hp_damage"],
                returned["character"]["health_dead"],
            ),
            (max(1, char["max_hp"] - expected_damage), expected_damage, False),
        )
        self.assertGreater(returned["character"]["hp"], 0)
        self.assertTrue(outside_fight_updates(shared.fight))
        duplicate = combat_health.persist(
            self.store,
            account,
            generation,
            returned["character"],
            shared.fight,
            reason="return",
        )
        self.assertFalse(duplicate["applied"])
        self.assertEqual(duplicate["character"]["hp"], returned["character"]["hp"])
        self.assertTrue(registry.mark_returned(fight_id, session))
        self.assertNotIn(fight_id, registry.fights)
        self.assertNotIn(char["id"], registry.by_character)
        self.assertNotIn(char["id"], registry.by_actor)
        self.assertNotIn(-200, registry.by_actor)
        self.assertFalse(registry.mark_returned(fight_id, session))
        restored = self.reopen().character(account, char["id"])
        self.assertEqual(
            (restored["hp"], restored["hp_damage"], restored["health_dead"]),
            (
                returned["character"]["hp"],
                returned["character"]["hp_damage"],
                returned["character"]["health_dead"],
            ),
        )
        with self.store.connection() as db:
            receipts = db.execute(
                "SELECT reason,return_acknowledged_at FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                (fight_id, char["id"]),
            ).fetchall()
            self.assertEqual(len(receipts), 1)
            self.assertEqual(receipts[0]["reason"], "return")
            self.assertIsNotNone(receipts[0]["return_acknowledged_at"])
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
                ).fetchone()["status"],
                "finished",
            )
        evidence.update(
            status="actual_paid_exchange_lethal_victory_native_terminal_owned_return",
            npc_hits=npc_hits,
            player_hits=player_hits,
            final_winner=shared.fight.winner,
            final_checkpoint_sha256=sha256(
                json.dumps(snapshot(shared.fight), sort_keys=True).encode()
            ).hexdigest(),
            cleanup=dict(
                registry_fight_absent=True,
                owned_health_return_once=True,
                reopen_health_preserved=True,
            ),
            terminal_order=[12755, 12238],
            packet_count=len(received),
        )
