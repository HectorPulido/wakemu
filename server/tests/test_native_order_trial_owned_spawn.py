"""The real private 885 owner creates its original native larva and state3127."""

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import socket
import struct
import unittest
from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

from postgres_case import PostgresCase


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".runtime/quest-archetypes/pizza/candidate-native-source"
ADMISSION_SOURCES = (
    Path(__file__).with_name("fixtures") / "native_pizzlarva_admission_sources.json"
)
ENABLED_FIXTURE = SOURCE / "enabled-context-fixture"
ENABLED_CONFIG = (
    ENABLED_FIXTURE
    / "server/wakfu_server/maps/owned_story_profiles/astrub-pizzlarva-885.configuration.json"
)
ENABLED_ADMISSION = (
    ENABLED_FIXTURE
    / "server/wakfu_server/achievements/order_trial_profiles/astrub_pizzlarva_admission.json"
)
ENABLED_RECEIPT = ENABLED_FIXTURE / "receipt.json"


class _Profiler:
    def span(self, _name):
        return nullcontext()


class NativeOrderTrialOwnedSpawnTests(PostgresCase):
    def test_actual3044_produces_native307_with_original3127_initialization(self):
        self._run_owned_fixture()

    def test_diagnostic_original3127_first_larva_turn_invocations(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_timeline_snapshot import current_wire_turn

        def first_turn(ctx):
            invocations = []
            original = EffectDispatcher.execute

            def observed(dispatcher, invocation, *args, **kwargs):
                if invocation.reference in (120672, 120673, 120674, 120675):
                    invocations.append(
                        {
                            "reference": invocation.reference,
                            "caster_id": invocation.caster_id,
                            "target_id": invocation.target_id,
                            "cell": invocation.cell,
                            "native_target_cell_argument": invocation.native_target_cell_argument,
                            "native_preselected_target": invocation.native_preselected_target,
                            "state_uid": invocation.state_uid,
                            "native_running_uid": invocation.native_running_uid,
                            "native_delayed_uid": invocation.native_delayed_uid,
                        }
                    )
                return original(dispatcher, invocation, *args, **kwargs)

            with patch.object(EffectDispatcher, "execute", observed):
                fight = ctx.runtime.fight
                owner = fight.current
                self.assertEqual(owner.id, ctx.owner_id)
                previous_turn = fight.turn_id
                actor_turn = current_wire_turn(fight)
                ctx.runtime.end_turn(ctx.owner_id, owner.id, actor_turn)
                ctx.runtime.acknowledge_turn(struct.pack(">i", previous_turn))
            fight = ctx.runtime.fight
            larvae = [
                fight.actors[identity]
                for identity in ctx.registrations
                if identity in fight.actors
            ]
            self.assertEqual(len(larvae), 1)
            larva = larvae[0]
            self.assertEqual(larva.direction, 3)
            receipts = getattr(fight, "native_order_birth_area_receipts", {})
            receipt = receipts.get(larva.id)
            self.assertIsInstance(receipt, dict)
            self.assertEqual(receipt.get("area_reference"), 787)
            self.assertIs(fight.current, larva)
            before_auto = (larva.position, larva.mp, fight.turn_id)
            order_command = getattr(fight, "native_order_commands", {}).get(
                str(larva.id)
            )
            movement_probe = []
            from wakfu_server import native_order_trial_movement

            original_path_for = native_order_trial_movement.path_for

            def observed_path_for(candidate, actor, command):
                try:
                    path = original_path_for(candidate, actor, command)
                except Exception as error:
                    movement_probe.append(
                        {
                            "turn_id": candidate.turn_id,
                            "actor_id": actor.id,
                            "position": actor.position,
                            "mp": actor.mp,
                            "command": deepcopy(command),
                            "error": f"{type(error).__name__}: {error}",
                        }
                    )
                    raise
                movement_probe.append(
                    {
                        "turn_id": candidate.turn_id,
                        "actor_id": actor.id,
                        "position": actor.position,
                        "mp": actor.mp,
                        "command": deepcopy(command),
                        "path": path,
                    }
                )
                return path

            with patch.object(
                native_order_trial_movement, "path_for", observed_path_for
            ):
                ctx.runtime.end_automatic_npc_turn(larva.id, fight.turn_id)
                awaiting_ack = ctx.runtime.awaiting_ack
                self.assertIsNotNone(awaiting_ack)
                ctx.runtime.acknowledge_turn(struct.pack(">i", awaiting_ack))
            fight = ctx.runtime.fight
            larva = fight.actors[larva.id]
            glyphs = [
                (
                    uid,
                    row.get("reference"),
                    row.get("cell"),
                    row.get("creator_reference"),
                    row.get("effect_reference"),
                    row.get("effect_uid"),
                )
                for uid, row in getattr(fight, "native_effect_areas", {}).items()
                if row.get("reference") in (768, 782)
            ]
            print(
                "NATIVE_3127_FIRST_TURN_TRACE",
                {
                    "current": getattr(fight.current, "id", None),
                    "turn_id": fight.turn_id,
                    "turn_count": getattr(fight.current, "turn_count", None),
                    "actors": [
                        (
                            actor.id,
                            actor.team,
                            getattr(actor, "native_fight_affiliation", None),
                            actor.position,
                            actor.direction,
                            actor.controlled,
                        )
                        for actor in (fight.actors[ctx.owner_id], *larvae)
                    ],
                    "invocations": invocations,
                    "birth_receipt": receipt,
                    "automatic_turn": {
                        "before": before_auto,
                        "after": (larva.position, larva.mp, fight.turn_id),
                        "command_before": order_command,
                        "command_after": getattr(
                            fight, "native_order_commands", {}
                        ).get(str(larva.id)),
                        "path_for": movement_probe,
                    },
                    "glyphs": glyphs,
                    "events": [
                        event
                        for event in fight.events
                        if event.get("reference") in (120672, 120673, 120674, 120675)
                        or event.get("event") == "native_order_command"
                    ],
                },
                flush=True,
            )

        self._run_owned_fixture(probe=first_turn)

    def test_actual_native_larva_reaches_registered_escape_area(self):
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server import native_order_trial_events

        def escape_probe(ctx):
            history = []
            death_seen = False
            area_batches = []

            def fresh_events(candidate, previous_sequence):
                batch = tuple(
                    event
                    for event in candidate.events
                    if type(event.get("sequence")) is int
                    and event["sequence"] > previous_sequence
                )
                native_order_trial_events.observe_pending(candidate, events=batch)
                return batch

            from wakfu_server import native_order_trial_movement

            for owner_turn_index in range(16):
                fight = ctx.runtime.fight
                if fight.phase != "active":
                    break
                self.assertIsNotNone(fight.current)
                owner_batch = ()
                if fight.current.id == ctx.owner_id:
                    previous_sequence = fight.sequence
                    previous_turn = fight.turn_id
                    actor_turn = current_wire_turn(fight)
                    ctx.runtime.end_turn(ctx.owner_id, fight.current.id, actor_turn)
                    ctx.runtime.acknowledge_turn(struct.pack(">i", previous_turn))
                    fight = ctx.runtime.fight
                    owner_batch = fresh_events(fight, previous_sequence)
                if fight.phase != "active":
                    break
                if fight.current is None:
                    break
                larva = fight.current
                if not native_order_trial_movement.eligible(fight, larva):
                    print(
                        "NATIVE_ESCAPE_NON_OWNER_CURRENT",
                        {
                            "current_id": larva.id,
                            "turn_id": fight.turn_id,
                            "actors": [
                                (
                                    actor.id,
                                    actor.team,
                                    actor.controlled,
                                    actor.position,
                                    actor.hp,
                                    getattr(actor, "native_summon_source", None),
                                    [
                                        (entry.reference, entry.level, entry.uid)
                                        for entry in actor.state_ledger.entries
                                    ],
                                )
                                for actor in fight.actors.values()
                            ],
                            "registrations": fight.native_summon_registrations,
                            "order": getattr(fight, "order", None),
                        },
                        flush=True,
                    )
                    self.fail(
                        "Current actor is neither the owner nor a qualified native3127 larva"
                    )
                self.assertFalse(larva.controlled)
                previous_sequence = fight.sequence
                previous_turn = fight.turn_id
                before = (larva.id, larva.position, larva.hp, larva.mp, larva.direction)
                owner = fight.actors[ctx.owner_id]
                owner_failures_before = [
                    entry.level
                    for entry in owner.state_ledger.entries
                    if entry.reference == 3124
                ]
                self.assertLessEqual(len(owner_failures_before), 1)
                failure_before = (
                    owner_failures_before[0] if owner_failures_before else 0
                )
                original_begin = native_order_trial_events.begin_area_batch
                original_finish = native_order_trial_events.finish_area_batch

                def watched_begin(candidate, row, target):
                    token = original_begin(candidate, row, target)
                    if row.get("reference") == 768:
                        area_batches.append(
                            {
                                "stage": "begin",
                                "area_uid": row.get("uid"),
                                "target_id": target.id,
                                "token": deepcopy(token),
                            }
                        )
                    return token

                def watched_finish(dispatcher, row, target, token):
                    result = original_finish(dispatcher, row, target, token)
                    if row.get("reference") == 768:
                        area_batches.append(
                            {
                                "stage": "finish",
                                "area_uid": row.get("uid"),
                                "target_id": target.id,
                                "token": deepcopy(token),
                                "result": None if result is None else dict(result),
                            }
                        )
                    return result

                with patch.object(
                    native_order_trial_events, "begin_area_batch", watched_begin
                ), patch.object(
                    native_order_trial_events, "finish_area_batch", watched_finish
                ):
                    ctx.runtime.end_automatic_npc_turn(larva.id, previous_turn)
                    if ctx.runtime.awaiting_ack is not None:
                        ctx.runtime.acknowledge_turn(
                            struct.pack(">i", ctx.runtime.awaiting_ack)
                        )
                fight = ctx.runtime.fight
                larva_after = fight.actors.get(larva.id)
                npc_batch = fresh_events(fight, previous_sequence)
                escape_kills = [
                    event
                    for event in npc_batch
                    if event.get("kind") == "kill_hp_minimum_update"
                    and event.get("generic_effect") == 118950
                    and event.get("target_id") == larva.id
                    and (event.get("native_container") or {}).get("type") == 3
                    and fight.native_effect_areas.get(
                        (event.get("native_container") or {}).get("id"), {}
                    ).get("reference")
                    == 768
                ]
                if escape_kills:
                    self.assertEqual(len(escape_kills), 1)
                    matching = [
                        event
                        for event in npc_batch
                        if event.get("kind") == "native_order_failure_applied"
                        and event.get("target_id") == ctx.owner_id
                        and event.get("area_uid")
                        == (escape_kills[0].get("native_container") or {}).get("id")
                    ]
                    self.assertEqual(
                        len(matching),
                        1,
                        f"Each causal registered768 larva kill must apply exactly one owner Failure3124; batch={npc_batch!r}; area_batches={area_batches!r}",
                    )
                    self.assertEqual(matching[0].get("before_level"), failure_before)
                    self.assertEqual(matching[0].get("after_level"), failure_before + 1)
                owner_after = fight.actors[ctx.owner_id]
                owner_failures_after = [
                    entry.level
                    for entry in owner_after.state_ledger.entries
                    if entry.reference == 3124
                ]
                escape_witness = next(
                    (
                        row
                        for row in fight.native_order_trial["events"]
                        if row["classification"].get("action") == "escape"
                        and row["native_event"].get("generic_effect") == 118950
                    ),
                    None,
                )
                outcome = (
                    None if escape_witness is None else escape_witness["classification"]
                )
                if escape_witness is not None:
                    death_seen = True
                history.append(
                    {
                        "owner_turn": owner_turn_index + 1,
                        "turn_id": previous_turn,
                        "larva_before": before,
                        "larva_after": None
                        if larva_after is None
                        else (
                            larva_after.position,
                            larva_after.hp,
                            larva_after.mp,
                            larva_after.direction,
                        ),
                        "command": getattr(fight, "native_order_commands", {}).get(
                            str(larva.id)
                        ),
                        "owner_batch": [event.get("kind") for event in owner_batch],
                        "larva_batch": [
                            (
                                event.get("kind"),
                                event.get("generic_effect"),
                                event.get("reference"),
                                event.get("target_id"),
                            )
                            for event in npc_batch
                        ],
                        "escape_outcome": None
                        if outcome is None
                        else outcome.get("source"),
                        "escape_native_event": None
                        if escape_witness is None
                        else escape_witness["native_event"],
                        "failure_before": failure_before,
                        "failure_after": owner_failures_after,
                        "area_batch_events": deepcopy(area_batches),
                    }
                )
                if death_seen or fight.phase != "active":
                    break

            fight = ctx.runtime.fight
            print(
                "NATIVE_OWNED_ESCAPE_TRACE",
                {
                    "turns": history,
                    "ready_observations": ctx.ready_observations,
                    "ready_native_order_spawns": [
                        (
                            event.get("sequence"),
                            event.get("actor_id"),
                            event.get("reference"),
                            event.get("effect_reference"),
                        )
                        for event in ctx.ready_batch
                        if event.get("kind") == "native_order_spawned"
                    ],
                    "phase": fight.phase,
                    "winner": fight.winner,
                    "checkpoint": fight.native_order_trial.get("state"),
                    "native_order_commands": getattr(
                        fight, "native_order_commands", {}
                    ),
                    "escape": death_seen,
                },
                flush=True,
            )
            self.assertTrue(
                death_seen,
                "Real 3127/328 movement did not produce a registered 768 kill and escape classifier",
            )

        self._run_owned_fixture(probe=escape_probe)

    def _run_owned_fixture(self, probe=None):
        from wakfu_server import (
            dungeon_context,
            dungeon_instances,
            dungeon_runtime,
            dungeon_runtime_config,
            native_order_trial_admission as admission,
            native_order_trial_arena as order_arena,
            native_order_trial_context as order_context,
            native_order_trial_encounter as encounter,
            native_order_trial_orders,
            native_transports,
            owned_story_controller,
            owned_story_generic_entry,
        )
        from wakfu_server.application.transport import Connection
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.equipment_stats import combat_resources
        from wakfu_server.position_buffer import Positions
        from wakfu_server.spells import default_deck

        receipt = json.loads(ENABLED_RECEIPT.read_text())
        source_bytes = ENABLED_ADMISSION.read_bytes()
        self.assertEqual(
            sha256(source_bytes).hexdigest(), receipt["enabled_raw_sha256"]
        )
        self.assertEqual(
            admission.SOURCE_SHA256, receipt["canonical_source_unchanged_sha256"]
        )
        capability = admission.validate(json.loads(source_bytes))
        self.assertTrue(capability["enabled"])
        self.assertEqual(
            admission.digest(capability), receipt["enabled_canonical_digest"]
        )
        configuration = json.loads(ENABLED_CONFIG.read_text())
        account = self.store.register("native-spawn-owner", "isolated-test-password")[
            "id"
        ]
        char_id = self.store.create_character(account, "Native Spawn Owner", breed=8)[
            "id"
        ]
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, char_id)
        previous_routes = dungeon_instances._ROUTES
        left = right = None
        source_document = order_context._document

        def fixture_source_document(name, expected_sha256):
            if name == ENABLED_ADMISSION.name:
                self.assertEqual(expected_sha256, receipt["enabled_raw_sha256"])
                self.assertEqual(sha256(source_bytes).hexdigest(), expected_sha256)
                return json.loads(source_bytes)
            return source_document(name, expected_sha256)

        source_pin_patch = patch.object(
            order_context, "_document", side_effect=fixture_source_document
        )
        try:
            source_pin_patch.start()
            with self.store.connection() as db:
                dungeon_runtime_config.install_configuration(db, configuration)
                db.execute(
                    "UPDATE characters SET map_id=546,instance_id=0,x=-4,y=-8,z=3 WHERE id=%s",
                    (char_id,),
                )
            dungeon_instances.load_runtime_routes(self.store)
            live = {(account, generation, char_id)}
            positions = Positions(
                self.store,
                lease_active=lambda owner, lease, identity: (owner, lease, identity)
                in live,
            )
            positions.attach(
                account, generation, self.store.character(account, char_id)
            )
            groups = Mock()

            def initialize_instance(db, admitted):
                dungeon_runtime.initialize_instance(
                    db, admitted, groups=groups, geometry={}, store=self.store
                )

            with positions.account_barrier(account):
                positions.flush(account_id=account)
                entered = owned_story_generic_entry.enter(
                    self.store,
                    account,
                    generation,
                    self.store.character(account, char_id),
                    struct.pack(">qHH", 23626, 0, 0),
                    loaded=True,
                    blocked=False,
                    allowed_position_accounts=frozenset({account}),
                    initialize_instance=initialize_instance,
                )
                positions.rebind_selected(account, generation, char_id)
            instance_id = entered["instance_id"]
            current = self.store.character(account, char_id)
            self.assertEqual(
                tuple(current[key] for key in ("map_id", "instance_id", "x", "y", "z")),
                (885, instance_id, 0, 0, 0),
            )
            with self.store.connection() as db:
                ready = owned_story_controller.on_world_ready(db, self.store, current)
            self.assertEqual(ready["step"], "order-context-ready")

            # Walk one actual map cell to the original hard-mode button pose.
            moved = positions.move(
                account,
                generation,
                char_id,
                current,
                dict(x=1, y=0, z=0),
            )
            self.assertEqual(
                (
                    moved["map_id"],
                    moved["instance_id"],
                    moved["x"],
                    moved["y"],
                    moved["z"],
                ),
                (885, instance_id, 1, 0, 0),
            )
            positions.flush(account_id=account)
            current = self.store.character(account, char_id)

            with self.store.connection() as db:
                context = order_context.scope(db, self.store, current)
            context_packet = native_transports.bootstrap(
                current,
                dungeon_context=dungeon_context.for_instance(
                    self.store, instance_id, fight_in_progress=False
                ),
            )
            body = next(
                payload for opcode, payload in context_packet if opcode == 13974
            )
            publication_scope = (account, generation, char_id, 885, instance_id)
            left, right = socket.socketpair()
            connection = Connection(left, runtime=Mock(PROFILER=_Profiler()))
            connection.native_instance_scope = lambda: publication_scope
            frame = struct.pack(">IH", len(body) + 6, 13974) + body
            connection.sendall(frame)
            self.assertEqual(right.recv(len(frame)), frame)
            self.assertEqual(
                connection.instance_publications.published.instance_id, instance_id
            )

            mode_body = struct.pack(">qHH", 23620, 0, 0)
            sources = {
                row["id"]: row for row in json.loads(ADMISSION_SOURCES.read_text())
            }
            native_source = sources[23620]
            proof = admission.plan(
                capability, current, mode_body, native_source=native_source
            )
            proof = replace(proof, generation=generation)
            geometry_proof = admission.plan(
                capability, current, mode_body, native_source=native_source
            )
            geometry_proof = replace(geometry_proof, generation=generation)
            arena = order_arena.prepare(context, current, geometry_proof)

            resources = combat_resources(current)
            deck = default_deck(current)
            bind_results = []
            runtime_context = {}
            before_ready_resources = {}

            def initialize_runtime(fight):
                bound = connection.instance_publications.bind_encounter(
                    fight,
                    connection.native_instance_scope(),
                    npc_ids=(),
                    player_id=char_id,
                )
                bind_results.append(bound)
                if not bound:
                    raise ValueError("Actual private 885 publication did not bind")
                initialize_fight_snapshots(
                    fight,
                    characters={char_id: current},
                    monsters={},
                    wp_resources={char_id: (resources["wp"], resources["wp"])},
                    running_effects={char_id: ()},
                    initial_effect_uid=1,
                )
                owner_before_ready = fight.actors[char_id]
                before_ready_resources.update(
                    hp=owner_before_ready.hp,
                    max_hp=owner_before_ready.max_hp,
                    ap=owner_before_ready.ap,
                    mp=owner_before_ready.mp,
                    wp=owner_before_ready.effect_stats.get(4),
                )
                factory, _adapter = server_runtime(
                    current, {}, deck, action_id=1, critical=False
                )
                dispatcher, _retained = factory(
                    fight, {"native_retained_container": {"present": False}}
                )
                runtime_context.update(factory=factory, dispatcher=dispatcher)
                from wakfu_server import native_order_trial_placement

                application_authorized = (
                    native_order_trial_placement.application_authorized
                )
                initialization_scope = native_order_trial_placement.initialization_scope
                self.assertFalse(
                    application_authorized(fight, char_id, char_id, 3049, 1)
                )
                with initialization_scope(
                    fight, dispatcher, proof, current, capability=capability
                ):
                    self.assertTrue(
                        application_authorized(fight, char_id, char_id, 3049, 1)
                    )
                    self.assertTrue(
                        application_authorized(fight, char_id, char_id, 3044, 1)
                    )
                    self.assertTrue(
                        application_authorized(fight, char_id, char_id, 3052, 1)
                    )
                    self.assertFalse(
                        application_authorized(fight, char_id, char_id, 3049, 2)
                    )
                    self.assertFalse(
                        application_authorized(fight, char_id, char_id + 1, 3049, 1)
                    )
                    self.assertFalse(
                        application_authorized(
                            deepcopy(fight), char_id, char_id, 3049, 1
                        )
                    )
                with self.assertRaisesRegex(ValueError, "enabled typed native source"):
                    with initialization_scope(
                        fight,
                        dispatcher,
                        proof,
                        current,
                        capability={**capability, "enabled": False},
                    ):
                        pass
                with self.assertRaisesRegex(ValueError, "enabled typed native source"):
                    with initialization_scope(
                        fight,
                        dispatcher,
                        replace(proof, source_sha256="0" * 64),
                        current,
                        capability=capability,
                    ):
                        pass
                return dispatcher

            with self.store.connection() as db:
                context = order_context.scope(db, self.store, current)
                prepared = encounter.create_durable(
                    db,
                    self.store,
                    current,
                    proof,
                    capability=capability,
                    arena=arena,
                    initialize_runtime=initialize_runtime,
                    resources=dict(
                        player_ap=resources["ap"],
                        player_mp=resources["mp"],
                        player_wp=resources["wp"],
                        player_initiative=resources["initiative"],
                        terrain_effect_id=46,
                        terrain_instance_id=90000,
                    ),
                    generate_orders=native_order_trial_orders.initial,
                )
            from wakfu_server import native_order_trial_selection

            initial_native_recipes = native_order_trial_selection.selected(
                prepared["fight"], prepared["fight"].events, initialization=True
            )
            self.assertEqual(len(initial_native_recipes), 3)
            self.assertEqual(len(set(initial_native_recipes)), 3)
            self.assertEqual(tuple(prepared["state"].orders), initial_native_recipes)
            from wakfu_server.combat_session_adapter import CombatSessionAdapter

            combat_adapter = CombatSessionAdapter(self.store)
            session = combat_adapter.session(account, generation, current)
            ready_source_sequence = prepared["fight"].sequence
            ready = combat_adapter.ready_transition(
                session, prepared["fight"], None, True, {}, area_callbacks=True
            )

            fight = ready.fight
            ready_batch = tuple(
                event
                for event in fight.events
                if type(event.get("sequence")) is int
                and event["sequence"] > ready_source_sequence
            )
            from wakfu_server import native_order_trial_events

            ready_observations = native_order_trial_events.observe_pending(
                fight, events=ready_batch
            )
            registrations = fight.native_summon_registrations
            native_larva_refs = {3206, 3239, 3240}
            from wakfu_server.combat_summon_initial_states import native_initial_states

            native_tables = native_initial_states()
            larvae = [
                fight.actors[identity]
                for identity in registrations
                if identity in fight.actors
                and fight.actors[identity].native_summon_source.get("ref")
                in native_larva_refs
            ]
            states3127 = [
                (actor.id, entry.reference, entry.level, entry.uid)
                for actor in larvae
                for entry in actor.state_ledger.entries
                if entry.reference == 3127
            ]
            native_initial_table = {
                str(ref): native_tables[str(ref)]
                for ref in sorted(native_larva_refs)
                if str(ref) in native_tables
            }
            print(
                "OWNED_SPAWN_TRACE",
                dict(
                    fight_id=fight.id,
                    owner=char_id,
                    owner_states=[
                        (entry.reference, entry.level, entry.uid)
                        for entry in fight.actors[char_id].state_ledger.entries
                        if entry.reference in (3049, 3052, 3044)
                    ],
                    owner_resources={
                        "hp": fight.actors[char_id].hp,
                        "max_hp": fight.actors[char_id].max_hp,
                        "ap": fight.actors[char_id].ap,
                        "mp": fight.actors[char_id].mp,
                        "wp": fight.actors[char_id].effect_stats.get(4),
                    },
                    before_ready_resources=before_ready_resources,
                    phase=fight.phase,
                    ready_event_batch=[
                        (
                            event.get("sequence"),
                            event.get("kind"),
                            event.get("reference"),
                            event.get("effect_reference"),
                            event.get("actor_id"),
                        )
                        for event in ready_batch
                    ],
                    ready_observations=ready_observations,
                    ready_checkpoint_larvae=fight.native_order_trial["state"]["larvae"],
                    native_initial_table=native_initial_table,
                    initial_native_recipes=initial_native_recipes,
                    publication_bound=bind_results,
                    registrations=[
                        (
                            identity,
                            row.get("caster_id"),
                            row.get("controller_id"),
                            row.get("reference"),
                        )
                        for identity, row in registrations.items()
                    ],
                    larvae=[(actor.id, actor.native_summon_source) for actor in larvae],
                    affiliations={
                        identity: {
                            "team": actor.team,
                            "native_fight_affiliation": getattr(
                                actor, "native_fight_affiliation", None
                            ),
                            "controlled": actor.controlled,
                        }
                        for identity, actor in fight.actors.items()
                        if identity == char_id
                        or identity in {item.id for item in larvae}
                    },
                    state3127=states3127,
                ),
                flush=True,
            )
            self.assertTrue(bind_results == [True])
            self.assertEqual(fight.phase, "active")
            ready_owner = fight.actors[char_id]
            self.assertEqual(
                (
                    ready_owner.hp,
                    ready_owner.max_hp,
                    ready_owner.ap,
                    ready_owner.mp,
                    ready_owner.effect_stats.get(4),
                ),
                (1, 1, 6, 3, 4),
                "Native Ready must preserve the reviewed hard-mode resource tuple",
            )
            self.assertTrue(
                larvae, "Original3044 did not create a native307 order-trial larva"
            )
            self.assertTrue(
                states3127, "Native initial-state construction omitted original3127"
            )
            self.assertEqual(
                {
                    entry.reference
                    for entry in fight.actors[char_id].state_ledger.entries
                }
                & {3049, 3052, 3044},
                {3049, 3052, 3044},
            )
            for actor in larvae:
                source = actor.native_summon_source
                registration = registrations[actor.id]
                self.assertEqual(
                    source["native_relation_source"],
                    "big.new_bje.fdt_initial_registration",
                )
                self.assertEqual(source["caster_id"], char_id)
                self.assertEqual(source["controller_id"], actor.id)
                self.assertEqual(registration["caster_id"], char_id)
                self.assertEqual(registration["controller_id"], actor.id)
                triples = native_initial_table[str(source["ref"])][
                    "initial_state_triples"
                ]
                self.assertEqual(triples, [3127, 1, 0])
                self.assertEqual(
                    [
                        (entry.reference, entry.level)
                        for entry in actor.state_ledger.entries
                        if entry.reference == 3127
                    ],
                    [(3127, 1)],
                )
            if probe is not None:
                probe(
                    SimpleNamespace(
                        store=self.store,
                        account_id=account,
                        generation=generation,
                        character=current,
                        owner_id=char_id,
                        proof=proof,
                        fight=fight,
                        runtime=ready.runtime,
                        adapter=combat_adapter,
                        session=session,
                        dispatcher=runtime_context["dispatcher"],
                        factory=runtime_context["factory"],
                        deck=deck,
                        connection=connection,
                        initial_native_recipes=initial_native_recipes,
                        registrations=registrations,
                        larvae=tuple(larvae),
                        before_ready_resources=dict(before_ready_resources),
                        ready_batch=ready_batch,
                        ready_observations=ready_observations,
                    )
                )
        finally:
            source_pin_patch.stop()
            dungeon_instances._ROUTES = previous_routes
            if left is not None:
                left.close()
            if right is not None:
                right.close()


if __name__ == "__main__":
    unittest.main()
