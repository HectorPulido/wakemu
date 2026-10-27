"""Three original-pool native wave pipelines on one bounded source backend.

This is a native lifecycle component on published native terrain. Separate
PostgreSQL receipts qualify entry/payment/settlement/exit, and the owned-session
fence component qualifies peer-generation takeover. This method does not claim
client play, NPC spell-selection AI, or all29 boss encounters.
"""
from copy import deepcopy
from contextlib import contextmanager
import json
from collections import deque
import os
from pathlib import Path
import re
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class ThreeNativeRiftFlowsTests(unittest.TestCase):
    def test_three_original_pools_ready_artifacts_death_successor_ack_and_budget(self):
        from tools.sublimation_bounded_census import BoundedDataset

        manifest = os.environ["WAKFU_RIFT_FLOW_MANIFEST"]
        dataset = BoundedDataset(manifest)
        dataset.install_catalog_backend()
        self.assertIn("indexed_records", dataset.manifest)
        from wakfu_server.combat_static_catalogs import CompiledEffects
        from wakfu_server.combat_effect_runtime import _merge_effects
        from wakfu_server.rift_producer_catalog import original_artifact_producer
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_start_events import deliver_fight_start
        from wakfu_server.combat_turn_events import deliver_turn_start, deliver_turn_end
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.combat_random_transaction import rollback_external_rng
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.combat_npc_spell import owned_spells, prepare_npc_spell
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_qi_movement import movement_blocked_cells
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            prepare_server_initialization,
        )
        from wakfu_server.rift_company_compensation import install_company_compensation
        from wakfu_server.rift_native_gameplay import install_wave_state
        from wakfu_server.rift_artifact_generation import spawn_artifacts
        from wakfu_server.rift_dispatch_combat import finish_accepted_action
        from wakfu_server.rift_wave_initialization import initialize_registered_wave
        from wakfu_server.rift_combat_adapter import (
            world_snapshot,
            creation_replay,
            finish_survival,
        )
        from wakfu_server.rift_policy import select_wave
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum
        from wakfu_server.wire import proto_field
        from rift_native_flow_fixture import build_flow_fixture
        import test_rift_native_carrier_component as carrier_fixture
        import test_rift_artifact_generation_component as artifact_fixture

        policy = carrier_fixture.NativeRiftCarrierComponentTests.policy()
        native = artifact_fixture.RiftArtifactGenerationComponentTests.native_policy()
        native["compensation"] = policy["native_gameplay"]["compensation"]
        policy["native_gameplay"] = native
        effects = _merge_effects(
            dataset.closure["effects"],
            dataset.read(dataset.manifest["semantic"]["extra_effects"]),
        )
        states = {
            **dataset.states["states"],
            **dataset.read(dataset.manifest["semantic"]["extra_states"])["states"],
        }
        # Exercise the production indexed importer, rather than satisfying its
        # dependency by leaving a fixture-only315925 in the source overlay.
        producer = original_artifact_producer(native["artifacts"]["producer"])
        for ref in producer["effects"]:
            effects.pop(ref, None)
        effects = _merge_effects(effects, producer)
        compiled = CompiledEffects(effects, dict(states=states, effects=effects))
        registry = {"effects": dataset.closure["registry"]}
        # Metadata seam only: constructors/turns/casts consume the exact same
        # immutable original closure as this component's real factory. No
        # targeting, ownership, eligibility, callback or resolver is replaced.
        from wakfu_server import spell_audit, combat_npc_attack, combat_server_spell

        class_catalog = dataset.read(dataset.manifest["rift_player_class_catalog"])
        from wakfu_server import combat_casting_context

        casting_roots = dataset.read(dataset.manifest["rift_casting_root_catalog"])
        from wakfu_server import combat_health_ordering_authority

        health_authority = dataset.read(
            dataset.manifest["native_health_ordering_authority"]
        )

        class HealthAuthoritySource:
            @contextmanager
            def connection(self):
                yield self

            def execute(self, query, parameters):
                if query == (
                    "SELECT * FROM native_health_ordering_authority_versions WHERE catalog_revision=%s"
                ) and parameters == (health_authority["version"]["catalog_revision"],):
                    return SimpleNamespace(
                        fetchone=lambda: deepcopy(health_authority["version"])
                    )
                if query == (
                    "SELECT * FROM native_health_ordering_authority_rows WHERE authority_key=%s "
                    "ORDER BY effect_reference"
                ) and parameters == (health_authority["version"]["authority_key"],):
                    return SimpleNamespace(
                        fetchall=lambda: deepcopy(health_authority["rows"])
                    )
                raise ValueError("Unlisted immutable health-ordering metadata query")

        combat_health_ordering_authority._for_revision.cache_clear()
        health_reader = patch.object(
            combat_health_ordering_authority,
            "_database",
            return_value=HealthAuthoritySource(),
        )
        health_reader.start()
        self.addCleanup(health_reader.stop)

        for module, name, value in (
            (spell_audit, "states_catalog", compiled.source_states),
            (spell_audit, "catalog", class_catalog),
            (combat_server_spell, "catalog", class_catalog),
            (combat_server_spell, "states_catalog", compiled.source_states),
            (combat_npc_attack, "npc_runtime_catalog", compiled),
            (combat_server_spell, "compiled_runtime_catalog", compiled),
            (combat_casting_context, "casting_root_catalog", casting_roots),
        ):
            reader = patch.object(module, name, return_value=value)
            reader.start()
            self.addCleanup(reader.stop)
        source_sql = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "090_dimensional_rifts.sql"
        )
        if not source_sql.exists():
            source_sql = next(
                (Path(__file__).resolve().parents[1] / "migrations").glob("090_*.sql")
            )
        catalog = next(
            value
            for encoded in re.findall(r"'({.*})'::jsonb", source_sql.read_text())
            for value in [json.loads(encoded)]
            if "5" in value and "37" in value
        )
        aptitudes = proto_field(24, (1 << 64) - 1) + proto_field(
            34, proto_field(8, 20) + proto_field(16, 2)
        )
        if "rift_qa_equipment" in dataset.manifest:
            from wakfu_server import aptitudes as native_aptitudes

            category = native_aptitudes.BONUS_CATEGORY[1]
            self.assertEqual(category, native_aptitudes.BONUS_CATEGORY[16])
            budget = native_aptitudes.budgets(245)[category]
            resistance = min(budget, native_aptitudes.BONUSES[16]["maximum"])
            for bonus, points in ((16, resistance), (1, budget - resistance)):
                aptitudes += proto_field(
                    34, proto_field(8, bonus) + proto_field(16, points)
                )
            native_aptitudes.validate(dict(level=245), aptitudes)
        character = effective_character(
            dict(
                id=7,
                account_id=3,
                breed=1,
                sex=False,
                level=245,
                real_level=245,
                map_id=1134,
                instance_id=0,
                x=0,
                y=0,
                z=0,
                hp=maximum(1, 245),
                inventory_items=[],
                active_build_index=0,
                builds={
                    0: dict(
                        equipment="",
                        sheet=proto_field(24, 0xFFFFFFFF).hex(),
                        aptitudes=aptitudes.hex(),
                    )
                },
            )
        )
        if "rift_qa_equipment" in dataset.manifest:
            from rift_native_gear_fixture import equip_character

            character = effective_character(
                equip_character(
                    character, dataset.read(dataset.manifest["rift_qa_equipment"])
                )
            )
        # Fresh QA creation starts at the canonical native build maximum;
        # this precedes Actor construction and never heals a running fight.
        character["hp"] = character["max_hp"]
        from wakfu_server.spells import default_deck

        deck = default_deck(character)
        character["builds"][0]["deck"] = deck.hex()
        requested = os.environ.get("WAKFU_RIFT_FLOW_WAVES")
        selected_waves = (
            {5, 8, 37}
            if not requested
            else {int(value) for value in requested.split(",")}
        )
        self.assertTrue(selected_waves and selected_waves <= {5, 8, 37})
        for wave_id, witness in ((5, 4520), (8, 3866), (37, 5295)):
            if wave_id not in selected_waves:
                continue
            with self.subTest(wave_id=wave_id, boss=witness):
                entry = catalog[str(wave_id)]
                # A real deterministic seed under the complete original pool;
                # neither the species list nor select_wave/RNG is replaced.
                seed = next(
                    str(number)
                    for number in range(200000)
                    if all(
                        select_wave(entry, policy, str(number), wave)
                        == (witness, witness)
                        for wave in (1, 2)
                    )
                )
                run = dict(
                    catalog=entry,
                    policy=deepcopy(policy),
                    seed=seed,
                    instance_id=wave_id,
                    wave=1,
                )
                component = build_flow_fixture(
                    character,
                    run,
                    500 + wave_id,
                    (-200, -201),
                    (witness, witness),
                    compiled=compiled,
                    registry=registry,
                    minimum_separation=5 if witness == 3866 else 3,
                    additional_player_ids=(),
                )
                fight = component.fight
                self.assertEqual(
                    (component.roles.player_team, component.roles.npc_team), (1, 0)
                )
                self.assertTrue(
                    all(fight.actors[uid].max_hp > 1000 for uid in (-200, -201))
                )
                opening = []
                for index, (identity, member) in enumerate(
                    component.characters.items()
                ):
                    fight, packets = prepare_server_initialization(
                        member,
                        fight.rift_monsters,
                        fight,
                        member["account_id"],
                        component.decks[identity],
                        action_id=1,
                        rng=component.rng,
                        fight_start=index == len(component.characters) - 1,
                        player_characters=component.characters,
                        deck_blobs=component.decks,
                    )
                    opening.extend(packets)
                component.fight = fight
                print(
                    "native_rift_ready_build",
                    dict(
                        wave_id=wave_id,
                        witness=witness,
                        player_hp=fight.actors[7].hp,
                        player_maximum=fight.actors[7].max_hp,
                        fire_resistance={
                            key: fight.actors[7].effect_stats[key] for key in (27, 30)
                        },
                        npc_fire_stats={
                            uid: {
                                key: fight.actors[uid].effect_stats[key]
                                for key in (
                                    20,
                                    23,
                                    48,
                                    101,
                                    102,
                                    103,
                                    104,
                                    105,
                                    106,
                                    107,
                                )
                            }
                            for uid in (-200, -201)
                        },
                    ),
                    flush=True,
                )

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
                    if getattr(actor, "native_summon_source", None) is not None:
                        return registered_summon_stats(actor, current, entry["map_id"])
                    return actual_monster_actor_stats(
                        current.rift_monsters[actor.id],
                        actor,
                        current.id,
                        wp_current=actor.effect_stats[4],
                        wp_maximum=actor.effect_maxima[4],
                        direction=actor.direction,
                        fight=current,
                    )

                def turn_provider(current, *, actor_id, action_id, start):
                    callback = (
                        prepare_server_turn_start if start else prepare_server_turn_end
                    )
                    return callback(
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
                    turn_start_provider=lambda current, **kw: turn_provider(
                        current, **kw, start=True
                    ),
                    turn_end_provider=lambda current, **kw: turn_provider(
                        current, **kw, start=False
                    ),
                )
                runtime.turn_started()
                npc_cast = False

                curse_transfers = []

                def end_current():
                    if "rift_qa_equipment" in dataset.manifest:
                        from rift_native_safety_fixture import move_to_safety

                        move_to_safety(
                            runtime,
                            component,
                            serialize,
                            npc_distance=3 if witness == 3866 else 0,
                        )
                    current = runtime.fight
                    actor = current.current
                    if actor is not None and actor.id == 8:
                        # A real second PC follows the carrier by paid movement
                        # so the original adjacent-human curse can transfer.
                        carrier = current.actors[7]
                        separation = lambda cell: (
                            abs(cell[0] - carrier.position[0])
                            + abs(cell[1] - carrier.position[1])
                        )
                        if separation(actor.position) > 1 and actor.mp > 0:
                            blocked = set(
                                movement_blocked_cells(current, actor, current.walkable)
                                or ()
                            )
                            blocked.update(
                                tuple(row["cell"])
                                for row in current.native_effect_areas.values()
                                if row.get("native_area_contract") == "faM"
                            )
                            previous, queue = {actor.position: None}, deque(
                                [actor.position]
                            )
                            distances = {actor.position: 0}
                            while queue:
                                origin = queue.popleft()
                                if distances[origin] >= actor.mp:
                                    continue
                                for start, end in sorted(current.edges):
                                    if (
                                        start != origin
                                        or end in previous
                                        or end in blocked
                                    ):
                                        continue
                                    previous[end] = origin
                                    distances[end] = distances[origin] + 1
                                    queue.append(end)
                            from wakfu_server.combat_tackle_movement import (
                                movement_tackle_cost,
                            )

                            paths = []
                            for destination in previous:
                                if separation(destination) >= separation(
                                    actor.position
                                ):
                                    continue
                                path, cursor = [], destination
                                while cursor != actor.position:
                                    path.append(cursor)
                                    cursor = previous[cursor]
                                path.reverse()
                                ap, mp = movement_tackle_cost(current, actor, path)
                                if (
                                    path
                                    and len(path) + mp <= actor.mp
                                    and ap <= actor.ap
                                ):
                                    paths.append(path)
                            if paths:
                                path = min(
                                    paths,
                                    key=lambda value: (
                                        separation(value[-1]),
                                        len(value),
                                        value,
                                    ),
                                )
                                packets, result = apply_client(
                                    runtime,
                                    actor.owner_id,
                                    struct.pack(">q", actor.id)
                                    + b"".join(
                                        struct.pack(">iih", *cell) for cell in path
                                    ),
                                    lambda selected: serialize(selected, runtime.fight),
                                    runtime_stats_serializer=serialize,
                                    area_provider=lambda current, **kw: prepare_area_movement(
                                        component.characters[8],
                                        current.rift_monsters,
                                        current,
                                        component.decks[8],
                                        rng=component.rng,
                                        player_characters=component.characters,
                                        deck_blobs=component.decks,
                                        **kw,
                                    ),
                                )
                                self.assertTrue(packets)
                                self.assertTrue(result)
                                current = runtime.fight
                                actor = current.current
                    curse_before = {
                        uid
                        for uid in component.characters
                        if any(
                            entry.reference == 4199
                            for entry in current.actors[uid].state_ledger.entries
                        )
                    }
                    before = dict(
                        actor_id=None if actor is None else actor.id,
                        turn=current.turn_id,
                        round=current.native_timeline_round,
                        hp={uid: member.hp for uid, member in current.actors.items()},
                    )
                    self.assertIsNotNone(actor, repr(before))
                    trace = []
                    with combat_diagnostic_scope(
                        lambda **row: trace.append(row), limit=512
                    ):
                        packets = (
                            runtime.end_turn(
                                actor.owner_id, actor.id, current_wire_turn(current)
                            )
                            if actor.controlled
                            else runtime.end_server_turn(actor.id, current.turn_id)
                        )
                        if runtime.awaiting_ack is not None:
                            runtime.acknowledge_turn(
                                struct.pack(">i", runtime.awaiting_ack)
                            )
                    after = runtime.fight
                    curse_after = {
                        uid
                        for uid in component.characters
                        if any(
                            entry.reference == 4199
                            for entry in after.actors[uid].state_ledger.entries
                        )
                    }
                    if (
                        len(curse_before) == len(curse_after) == 1
                        and curse_before != curse_after
                    ):
                        curse_transfers.append(
                            (tuple(curse_before), tuple(curse_after))
                        )
                    if after.phase == "finished" and after.native_timeline_round <= 40:
                        self.fail(
                            "Actual early terminal boundary: "
                            + repr(
                                dict(
                                    wave_id=wave_id,
                                    witness=witness,
                                    before=before,
                                    phase=after.phase,
                                    winner=after.winner,
                                    outcome=after.rift_wave_state.get("outcome"),
                                    actors={
                                        uid: dict(
                                            hp=member.hp,
                                            maximum=member.max_hp,
                                            position=member.position,
                                            team=member.team,
                                            states=[
                                                (entry.reference, entry.level)
                                                for entry in member.state_ledger.entries
                                            ],
                                        )
                                        for uid, member in after.actors.items()
                                    },
                                    events=after.events[-16:],
                                    trace=trace[-96:],
                                )
                            )
                        )
                    return packets

                def reach_player():
                    nonlocal npc_cast
                    for _ in range(32):
                        current = runtime.fight
                        self.assertEqual(current.phase, "active")
                        if current.current.id == 7:
                            return
                        if current.current.controlled:
                            end_current()
                            continue
                        if not npc_cast:
                            actor = current.current
                            errors = []
                            targets = [current.actors[7].position, actor.position]
                            targets.extend(
                                sorted(
                                    end
                                    for start, end in current.edges
                                    if start == actor.position
                                )
                            )

                            def cast_preference(item):
                                reference, evaluation_level = item
                                table, index = native_casting_table(
                                    reference, evaluation_level
                                )
                                # Explicit survival-scenario action choice, not
                                # the NPC oracle: prefer genuine zero-range
                                # utility before direct offensive casts. Native
                                # legality, costs and outcomes remain unchanged.
                                self_centered = table["levels"][index][:2] == [0, 0]
                                return (not self_centered, reference)

                            for spell, level in sorted(
                                owned_spells(current, current.rift_monsters).items(),
                                key=cast_preference,
                            ):
                                for target in dict.fromkeys(targets):
                                    action = dict(
                                        type="cast",
                                        spellId=spell,
                                        level=level,
                                        target=target,
                                    )

                                    @rollback_external_rng
                                    def attempt_cast(*, rng):
                                        prepared = prepare_npc_spell(
                                            current,
                                            action,
                                            component.character,
                                            current.rift_monsters,
                                            deck,
                                            action_id=runtime.action_id + 1,
                                            rng=rng,
                                            player_characters=component.characters,
                                            deck_blobs=component.decks,
                                        )
                                        if prepared.fight.phase != "active":
                                            # A legal lethal preview is a real
                                            # defeat, not a server failure. This
                                            # controlled survival scenario may
                                            # choose another genuine own action;
                                            # rejection restores its RNG, without
                                            # healing or modifying the preview.
                                            raise ValueError(
                                                "Scenario rejects legal terminal NPC preview: "
                                                + repr(
                                                    dict(
                                                        action=action,
                                                        winner=prepared.fight.winner,
                                                        hp=prepared.fight.actors[7].hp,
                                                        maximum=prepared.fight.actors[
                                                            7
                                                        ].max_hp,
                                                        outcomes=prepared.outcomes,
                                                    )
                                                )
                                            )
                                        return prepared

                                    failure = None
                                    try:
                                        transaction = attempt_cast(rng=component.rng)
                                    except ValueError as error:
                                        failure = error
                                    diagnostic = getattr(
                                        failure, "native_target_diagnostic", None
                                    )
                                    if isinstance(diagnostic, dict):
                                        # Feed back the actual native target chosen by
                                        # validation, never invent an anchor recipient.
                                        action["targetId"] = diagnostic[
                                            "native_target_id"
                                        ]
                                        try:
                                            transaction = attempt_cast(
                                                rng=component.rng
                                            )
                                            failure = None
                                        except ValueError as error:
                                            failure = error
                                    if failure is not None:
                                        if str(failure).startswith(
                                            (
                                                "Metadata requires",
                                                "Unlisted bounded",
                                                "Bounded document",
                                                "Missing native casting root",
                                                "Unsupported native NPC effect roots",
                                            )
                                        ):
                                            raise failure
                                        errors.append(str(failure))
                                        continue
                                    self.assertTrue(transaction.outcomes)
                                    cast_packets = commit_spell_transaction(
                                        runtime,
                                        transaction,
                                        stats_serializer=serialize,
                                    )
                                    self.assertTrue(cast_packets)
                                    self.assertEqual(
                                        runtime.fight.phase,
                                        "active",
                                        repr(
                                            dict(
                                                wave_id=wave_id,
                                                witness=witness,
                                                action=action,
                                                plan=transaction.plan,
                                                outcomes=transaction.outcomes,
                                                winner=runtime.fight.winner,
                                                outcome=runtime.fight.rift_wave_state.get(
                                                    "outcome"
                                                ),
                                                actors={
                                                    uid: dict(
                                                        hp=member.hp,
                                                        maximum=member.max_hp,
                                                        team=member.team,
                                                        controlled=member.controlled,
                                                    )
                                                    for uid, member in runtime.fight.actors.items()
                                                },
                                            )
                                        ),
                                    )
                                    npc_cast = True
                                    break
                                if npc_cast:
                                    break
                            self.assertTrue(
                                npc_cast,
                                "No original legal NPC cast: " + repr(errors[:8]),
                            )
                        end_current()
                    self.fail("Native timeline did not return to the player")

                reach_player()
                if witness == 3866:
                    # Espinanta's authentic4174 START casts5650 in ring1–3.
                    # Leave that telegraphed range by ordinary paid12161
                    # movement before observing the uncollected-choice clock.
                    current = runtime.fight
                    actor = current.actors[7]
                    group = current.rift_wave_state["native_artifact_groups"]["1"]
                    forbidden = {
                        tuple(current.native_effect_areas[uid]["cell"])
                        for uid in group["remaining"]
                    }
                    blocked = set(
                        movement_blocked_cells(current, actor, current.walkable) or ()
                    )
                    previous, queue = {actor.position: None}, deque([actor.position])
                    distances = {actor.position: 0}
                    while queue:
                        origin = queue.popleft()
                        if distances[origin] >= actor.mp:
                            continue
                        for start, end in sorted(current.edges):
                            if (
                                start != origin
                                or end in previous
                                or end in blocked
                                or end in forbidden
                            ):
                                continue
                            previous[end] = origin
                            distances[end] = distances[origin] + 1
                            queue.append(end)
                    enemies = [
                        member
                        for member in current.actors.values()
                        if member.team == component.roles.npc_team
                        and current._in_play(member)
                    ]

                    def enemy_distance(cell):
                        return min(
                            abs(cell[0] - member.position[0])
                            + abs(cell[1] - member.position[1])
                            for member in enemies
                        )

                    from wakfu_server.combat_tackle_movement import movement_tackle_cost

                    safe_paths = []
                    for destination in previous:
                        if enemy_distance(destination) <= 3:
                            continue
                        path, cursor = [], destination
                        while cursor != actor.position:
                            path.append(cursor)
                            cursor = previous[cursor]
                        path.reverse()
                        ap, mp = movement_tackle_cost(current, actor, path)
                        if path and len(path) + mp <= actor.mp and ap <= actor.ap:
                            safe_paths.append(path)
                    self.assertTrue(
                        safe_paths, "No affordable native retreat beyond ring1–3"
                    )
                    path = min(
                        safe_paths,
                        key=lambda path: (-enemy_distance(path[-1]), len(path), path),
                    )
                    retreat_before = dict(
                        hp=actor.hp,
                        position=actor.position,
                        states=[
                            (entry.reference, entry.level)
                            for entry in actor.state_ledger.entries
                        ],
                    )
                    retreat_trace = []
                    with combat_diagnostic_scope(
                        lambda **row: retreat_trace.append(row), limit=512
                    ):
                        movement_packets, result = apply_client(
                            runtime,
                            actor.owner_id,
                            struct.pack(">q", 7)
                            + b"".join(struct.pack(">iih", *cell) for cell in path),
                            lambda selected: serialize(selected, runtime.fight),
                            runtime_stats_serializer=serialize,
                            area_provider=lambda current, **kw: prepare_area_movement(
                                component.character,
                                current.rift_monsters,
                                current,
                                deck,
                                rng=component.rng,
                                player_characters=component.characters,
                                deck_blobs=component.decks,
                                **kw,
                            ),
                        )
                    self.assertEqual(
                        runtime.fight.phase,
                        "active",
                        repr(
                            dict(
                                stage="paid_retreat",
                                path=path,
                                before=retreat_before,
                                actors={
                                    uid: dict(
                                        hp=member.hp,
                                        position=member.position,
                                        states=[
                                            (entry.reference, entry.level)
                                            for entry in member.state_ledger.entries
                                        ],
                                    )
                                    for uid, member in runtime.fight.actors.items()
                                },
                                events=runtime.fight.events[-16:],
                                trace=retreat_trace[-96:],
                            )
                        ),
                    )
                    self.assertTrue(movement_packets)
                    self.assertTrue(result)
                    self.assertGreater(
                        enemy_distance(runtime.fight.actors[7].position), 3
                    )
                # Choice groups survive two complete owner START/END cycles.
                # Original315925's timer1 would destroy these Qq before this
                # point;147120's original indefinite clock remains untouched.
                initial_uids = tuple(
                    runtime.fight.rift_wave_state["native_artifact_groups"]["1"][
                        "remaining"
                    ]
                )
                for _ in range(2):
                    end_current()
                    reach_player()
                    self.assertEqual(
                        tuple(
                            runtime.fight.rift_wave_state["native_artifact_groups"][
                                "1"
                            ]["remaining"]
                        ),
                        initial_uids,
                    )
                    self.assertTrue(
                        all(
                            uid in runtime.fight.native_effect_areas
                            for uid in initial_uids
                        )
                    )
                fight = runtime.fight
                dispatcher, contact_packets = component.factory(fight)
                group = fight.rift_wave_state["native_artifact_groups"]["1"]
                self.assertEqual(len(group["remaining"]), 4)
                early_kill_packets = []
                # Actual12161 resource payment and production step callbacks.
                # Native corridors may need multiple turns; no relocation,
                # resource refill or area position is fabricated by the test.
                for _ in range(12):
                    fight = runtime.fight
                    group = fight.rift_wave_state["native_artifact_groups"]["1"]
                    if group["choices_made"]:
                        break
                    actor = fight.actors[7]
                    blocked = set(
                        movement_blocked_cells(fight, actor, fight.walkable) or ()
                    )
                    # This controlled route avoids visible hostile glyph
                    # footprints, using their actual Qq geometry rather than
                    # treating an unoccupied damage cell as a safe corridor.
                    from wakfu_server.combat_effect_area import native_effect_areas
                    from wakfu_server.combat_effect_area_geometry import (
                        contains_area_actor,
                    )
                    from wakfu_server.combat_area_affiliation import area_affiliation

                    for area in fight.native_effect_areas.values():
                        definition = native_effect_areas()[str(area["reference"])]
                        if (
                            definition["type"] == "GLYPH"
                            and area["reference"] not in range(1574, 1581)
                            and area_affiliation(fight, area)
                            == component.roles.npc_team
                            and "rift_qa_equipment" not in dataset.manifest
                        ):
                            blocked.update(
                                cell
                                for cell in fight.walkable
                                if contains_area_actor(
                                    area, cell, actor.physical_radius
                                )
                            )
                    choice_cells = {
                        tuple(fight.native_effect_areas[uid]["cell"])
                        for uid in group["remaining"]
                    }
                    paths = []
                    for destination in sorted(choice_cells):
                        previous, queue = {actor.position: None}, deque(
                            [actor.position]
                        )
                        while queue and destination not in previous:
                            origin = queue.popleft()
                            for start, end in sorted(fight.edges):
                                if (
                                    start != origin
                                    or end in previous
                                    or end in blocked
                                    or end in choice_cells - {destination}
                                ):
                                    continue
                                previous[end] = origin
                                queue.append(end)
                        if destination not in previous:
                            continue
                        path, cursor = [], destination
                        while cursor != actor.position:
                            path.append(cursor)
                            cursor = previous[cursor]
                        if path:
                            paths.append(tuple(reversed(path)))
                    if not paths:
                        # Remove one actual glyph-producing opponent first,
                        # leaving a real remaining opponent so no successor
                        # starts before the player's artifact decision.
                        alive = sorted(
                            member.id
                            for member in fight.actors.values()
                            if member.team == component.roles.npc_team
                            and fight._in_play(member)
                        )
                        self.assertGreater(
                            len(alive),
                            1,
                            "No safe native corridor while only one opponent remains",
                        )
                        victim = alive[0]
                        # This component's PK.a caller supplies the real victim
                        # PV; the original leaf selector/policies stay intact.
                        death_dispatcher, death_packets = component.factory(fight)
                        self.assertTrue(
                            death_dispatcher.execute(
                                EffectInvocation(
                                    402298,
                                    1,
                                    7,
                                    victim,
                                    fight.actors[victim].position,
                                    native_explicit_target=True,
                                    native_context_hex=constructed_execution_context()
                                    .payload()
                                    .hex(),
                                    native_retained_container={"present": False},
                                )
                            )
                        )
                        self.assertFalse(
                            fight._in_play(fight.actors[victim]),
                            "Protected opponent requires an owned damage phase before KO",
                        )
                        self.assertIsNone(fight.rift_wave_state.get("pending_wave"))
                        early_kill_packets.extend(death_packets)
                        continue
                    path = min(paths, key=lambda value: (len(value), value))
                    prefix = list(path[: actor.mp])
                    from wakfu_server.combat_tackle_movement import movement_tackle_cost

                    while prefix:
                        ap, mp = movement_tackle_cost(fight, actor, prefix)
                        if len(prefix) + mp <= actor.mp and ap <= actor.ap:
                            break
                        prefix.pop()
                    self.assertTrue(prefix, "No affordable native movement step")
                    before_mp = actor.mp
                    body = struct.pack(">q", 7) + b"".join(
                        struct.pack(">iih", *cell) for cell in prefix
                    )
                    choice_before = dict(
                        hp=actor.hp,
                        position=actor.position,
                        states=[
                            (entry.reference, entry.level)
                            for entry in actor.state_ledger.entries
                        ],
                    )
                    choice_trace = []
                    with combat_diagnostic_scope(
                        lambda **row: choice_trace.append(row), limit=512
                    ):
                        movement_packets, result = apply_client(
                            runtime,
                            actor.owner_id,
                            body,
                            lambda selected: serialize(selected, runtime.fight),
                            runtime_stats_serializer=serialize,
                            area_provider=lambda current, **kw: prepare_area_movement(
                                component.character,
                                current.rift_monsters,
                                current,
                                deck,
                                rng=component.rng,
                                player_characters=component.characters,
                                deck_blobs=component.decks,
                                **kw,
                            ),
                        )
                    self.assertEqual(
                        runtime.fight.phase,
                        "active",
                        repr(
                            dict(
                                stage="paid_choice_path",
                                wave=wave_id,
                                path=prefix,
                                before=choice_before,
                                actors={
                                    uid: dict(
                                        hp=member.hp,
                                        position=member.position,
                                        states=[
                                            (entry.reference, entry.level)
                                            for entry in member.state_ledger.entries
                                        ],
                                    )
                                    for uid, member in runtime.fight.actors.items()
                                },
                                events=runtime.fight.events[-24:],
                                trace=choice_trace[-96:],
                            )
                        ),
                    )
                    self.assertTrue(movement_packets)
                    self.assertTrue(result)
                    self.assertLess(runtime.fight.actors[7].mp, before_mp)
                    if not runtime.fight.rift_wave_state["native_artifact_groups"]["1"][
                        "choices_made"
                    ]:
                        end_current()
                        reach_player()
                fight = runtime.fight
                group = fight.rift_wave_state["native_artifact_groups"]["1"]
                self.assertEqual(group["choices_made"], 1)
                self.assertEqual(len(group["remaining"]), 2)
                original_grant = deepcopy(group["assignments"][0])

                dispatcher, kill_packets = component.factory(fight)
                wave_packets = list(early_kill_packets)
                for _ in range(32):
                    alive = sorted(
                        actor.id
                        for actor in fight.actors.values()
                        if actor.team == component.roles.npc_team
                        and fight._in_play(actor)
                    )
                    if not alive:
                        break
                    identity = alive[0]
                    hp_before = fight.actors[identity].hp
                    self.assertTrue(
                        dispatcher.execute(
                            EffectInvocation(
                                402298,
                                1,
                                7,
                                identity,
                                fight.actors[identity].position,
                                native_explicit_target=True,
                                native_context_hex=constructed_execution_context()
                                .payload()
                                .hex(),
                                native_retained_container={"present": False},
                            )
                        )
                    )
                    wave_packets.extend(kill_packets)
                    kill_packets.clear()
                    if (
                        fight._in_play(fight.actors[identity])
                        and fight.actors[identity].hp == hp_before
                    ):
                        # Native instant death respects authentic health floors.
                        # An actual owned player cast must deliver the damage
                        # event which advances a protected boss phase.
                        from rift_native_phase_fixture import (
                            execute_health_floor_transition,
                            NoLegalOwnedPhaseTransition,
                        )

                        try:
                            wave_packets.extend(
                                execute_health_floor_transition(
                                    runtime,
                                    component,
                                    identity,
                                    stats_serializer=serialize,
                                )
                            )
                        except NoLegalOwnedPhaseTransition as failure:
                            accepted, errors, active_book = (
                                False,
                                failure.errors,
                                failure.active_book,
                            )
                        else:
                            fight = runtime.fight
                            group = fight.rift_wave_state["native_artifact_groups"]["1"]
                            dispatcher, kill_packets = component.factory(fight)
                            accepted, errors, active_book = True, (), ()
                        if not accepted and any(
                            marker in error.lower()
                            for error in errors
                            for marker in (
                                "casts per turn",
                                "casts per target",
                                "cooldown",
                                "not enough ap",
                            )
                        ):
                            # Respect actual owned usage/resource limits. The
                            # same END/START path used by gameplay renews them;
                            # no counter, cost, AP or cooldown is rewritten.
                            end_current()
                            reach_player()
                            fight = runtime.fight
                            group = fight.rift_wave_state["native_artifact_groups"]["1"]
                            dispatcher, kill_packets = component.factory(fight)
                            continue
                        if (
                            not accepted
                            and errors
                            and all(
                                "twI" in error or "twG" in error for error in errors
                            )
                        ):
                            # Actual cast range rejected the current position.
                            # Approach along the real map before retrying the
                            # owned action; no range/MP/position override.
                            actor = fight.actors[7]
                            if actor.mp == 0:
                                end_current()
                                reach_player()
                                fight = runtime.fight
                                group = fight.rift_wave_state["native_artifact_groups"][
                                    "1"
                                ]
                                dispatcher, kill_packets = component.factory(fight)
                                continue
                            target = fight.actors[identity].position
                            forbidden = {
                                tuple(fight.native_effect_areas[uid]["cell"])
                                for uid in group["remaining"]
                            }
                            blocked = set(
                                movement_blocked_cells(fight, actor, fight.walkable)
                                or ()
                            )
                            previous, queue = {actor.position: None}, deque(
                                [actor.position]
                            )
                            distances = {actor.position: 0}
                            while queue:
                                origin = queue.popleft()
                                if distances[origin] >= actor.mp:
                                    continue
                                for start, end in sorted(fight.edges):
                                    if (
                                        start != origin
                                        or end in previous
                                        or end in blocked
                                        or end in forbidden
                                    ):
                                        continue
                                    previous[end] = origin
                                    distances[end] = distances[origin] + 1
                                    queue.append(end)
                            paths = []
                            for destination in previous:
                                distance = abs(destination[0] - target[0]) + abs(
                                    destination[1] - target[1]
                                )
                                if not (
                                    distance == 1
                                    if len(component.characters) > 1
                                    else 2 <= distance <= 3
                                ):
                                    continue
                                path, cursor = [], destination
                                while cursor != actor.position:
                                    path.append(cursor)
                                    cursor = previous[cursor]
                                path.reverse()
                                ap, mp = movement_tackle_cost(fight, actor, path)
                                if (
                                    path
                                    and len(path) + mp <= actor.mp
                                    and ap <= actor.ap
                                ):
                                    paths.append(path)
                            if not paths:
                                end_current()
                                reach_player()
                                fight = runtime.fight
                                group = fight.rift_wave_state["native_artifact_groups"][
                                    "1"
                                ]
                                dispatcher, kill_packets = component.factory(fight)
                                continue
                            path = min(paths, key=lambda value: (len(value), value))
                            movement_packets, result = apply_client(
                                runtime,
                                actor.owner_id,
                                struct.pack(">q", 7)
                                + b"".join(struct.pack(">iih", *cell) for cell in path),
                                lambda selected: serialize(selected, runtime.fight),
                                runtime_stats_serializer=serialize,
                                area_provider=lambda current, **kw: prepare_area_movement(
                                    component.character,
                                    current.rift_monsters,
                                    current,
                                    deck,
                                    rng=component.rng,
                                    player_characters=component.characters,
                                    deck_blobs=component.decks,
                                    **kw,
                                ),
                            )
                            self.assertTrue(movement_packets)
                            self.assertTrue(result)
                            wave_packets.extend(movement_packets)
                            fight = runtime.fight
                            group = fight.rift_wave_state["native_artifact_groups"]["1"]
                            dispatcher, kill_packets = component.factory(fight)
                            continue
                        self.assertTrue(
                            accepted,
                            "No legal owned damage phase transition: "
                            + repr(
                                dict(
                                    errors=errors,
                                    player=fight.actors[7].position,
                                    target=fight.actors[identity].position,
                                    ap=fight.actors[7].ap,
                                    mp=fight.actors[7].mp,
                                    phase=fight.phase,
                                    casting={
                                        ref: native_casting_table(
                                            ref, fight.actors[7].effective_level
                                        )[0]["levels"][
                                            native_casting_table(
                                                ref, fight.actors[7].effective_level
                                            )[1]
                                        ]
                                        for ref in active_book
                                    },
                                )
                            ),
                        )
                wave_packets.extend(kill_packets)
                kill_packets = wave_packets
                group = fight.rift_wave_state["native_artifact_groups"]["1"]
                self.assertFalse(
                    [
                        dict(
                            id=actor.id,
                            hp=actor.hp,
                            maximum=actor.max_hp,
                            minimum=actor.effect_minima[1],
                            states=[
                                (entry.reference, entry.level)
                                for entry in actor.state_ledger.entries
                            ],
                        )
                        for actor in fight.actors.values()
                        if actor.team == component.roles.npc_team
                        and fight._in_play(actor)
                    ],
                    repr(fight.events[-24:]),
                )
                self.assertIsNotNone(fight.rift_wave_state["pending_wave"])
                orb_refs = {
                    row["reference"]
                    for row in fight.native_effect_areas.values()
                    if row["reference"] in range(1574, 1581)
                }
                self.assertIn(1575, orb_refs)
                pending_bytes, rng_before = snapshot(fight), component.rng.getstate()

                def initialize(current, actors, monsters):
                    current_dispatcher, packets = component.factory(current)
                    with current.effect_resolution():
                        initialize_registered_wave(
                            current_dispatcher,
                            actors=actors,
                            monsters=monsters,
                            player_ids=tuple(component.characters),
                        )
                    return tuple(packets)

                @rollback_external_rng
                def rejected(*, rng):
                    preview = deepcopy(fight)
                    current_runtime = deepcopy(runtime)
                    current_runtime.fight = preview
                    finish_accepted_action(
                        preview,
                        current_runtime,
                        tuple(kill_packets),
                        initialize_actor=lambda *_: (),
                        initialize_wave=initialize,
                    )
                    raise ValueError("Reject unpublished fully initialized successor")

                with self.assertRaisesRegex(ValueError, "fully initialized successor"):
                    rejected(rng=component.rng)
                self.assertEqual(snapshot(fight), pending_bytes)
                self.assertEqual(component.rng.getstate(), rng_before)
                prepared = finish_accepted_action(
                    fight,
                    runtime,
                    tuple(kill_packets),
                    initialize_actor=lambda *_: (),
                    initialize_wave=initialize,
                )
                self.assertEqual(fight.rift_wave_state["wave"], 2)
                self.assertEqual(sum(op == 13091 for op, _ in prepared.packets), 2)
                self.assertNotIn(12053, [op for op, _ in prepared.packets])
                self.assertEqual(group["remaining"], [])
                self.assertEqual(group["assignments"][0], original_grant)
                self.assertEqual(
                    len(
                        fight.rift_wave_state["native_artifact_groups"]["2"][
                            "remaining"
                        ]
                    ),
                    4,
                )
                self.assertTrue(
                    getattr(fight, "native_rift_artifact_inheritance", None)
                    or fight.rift_wave_state.get("native_artifact_inheritance")
                )
                # Reconnect's ordinary-avatar prefix is pure, idempotent and
                # never re-executes13091 after a complete participant bootstrap.
                reconnect_state = snapshot(fight)
                self.assertTrue(world_snapshot(fight))
                self.assertEqual(
                    [op for op, _ in creation_replay(fight, world_only=True)],
                    [12608, 12608],
                )
                self.assertEqual(snapshot(fight), reconnect_state)
                replay = finish_accepted_action(
                    fight, runtime, (), initialize_actor=lambda *_: ()
                )
                self.assertFalse(replay.packets)
                # Genuine native end/ACK counters release the pending birth
                # fence; no invented end frame is sent during the kill itself.
                if "rift_qa_equipment" in dataset.manifest:
                    from rift_native_safety_fixture import move_to_safety

                    move_to_safety(
                        runtime,
                        component,
                        serialize,
                        npc_distance=3 if witness == 3866 else 0,
                    )
                fight = runtime.fight
                actor = fight.current
                end_before = dict(
                    actor=actor.id,
                    in_play=fight._in_play(actor),
                    phase=fight.phase,
                    turn=fight.turn_id,
                    round=fight.native_timeline_round,
                    fence=getattr(fight, "native_rift_birth_fence", None),
                    actors={
                        uid: dict(
                            hp=member.hp,
                            team=member.team,
                            states=[
                                (entry.reference, entry.level)
                                for entry in member.state_ledger.entries
                            ],
                        )
                        for uid, member in fight.actors.items()
                    },
                )
                end_trace = []
                with combat_diagnostic_scope(
                    lambda **row: end_trace.append(row), limit=512
                ):
                    if actor.controlled:
                        end_packets = runtime.end_turn(
                            actor.owner_id, actor.id, current_wire_turn(fight)
                        )
                    else:
                        end_packets = runtime.end_server_turn(actor.id, fight.turn_id)
                self.assertIn(
                    12502,
                    [op for op, _ in end_packets],
                    repr(
                        dict(
                            before=end_before,
                            phase=runtime.fight.phase,
                            winner=runtime.fight.winner,
                            current=None
                            if runtime.fight.current is None
                            else runtime.fight.current.id,
                            actors={
                                uid: dict(
                                    hp=member.hp,
                                    states=[
                                        (entry.reference, entry.level)
                                        for entry in member.state_ledger.entries
                                    ],
                                )
                                for uid, member in runtime.fight.actors.items()
                            },
                            events=runtime.fight.events[-24:],
                            trace=end_trace[-96:],
                        )
                    ),
                )
                expected = runtime.awaiting_ack
                with self.assertRaises(ValueError):
                    runtime.acknowledge_turn(struct.pack(">i", expected + 1))
                runtime.acknowledge_turn(struct.pack(">i", expected))
                self.assertIsNone(runtime.awaiting_ack)
                # Continue real native START/END/ACK cycles to the terminal
                # survival boundary. No clock setter or forty-round shortcut.
                for _ in range(1024):
                    if runtime.fight.phase == "finished":
                        break
                    self.assertLessEqual(runtime.fight.native_timeline_round, 40)
                    end_current()
                fight = runtime.fight
                self.assertTrue(npc_cast)
                self.assertEqual(fight.phase, "finished")
                self.assertEqual(fight.native_timeline_round, 41)
                self.assertEqual(fight.winner, component.roles.player_team)
                self.assertIsNone(runtime.awaiting_ack)
                self.assertEqual(runtime.pending, [])
                self.assertIsNone(runtime.turn_deadline)
                self.assertIsNone(runtime.deadline_turn)
                if witness == 3866:
                    self.assertFalse(
                        any(
                            entry.reference == 4199
                            for uid in component.characters
                            for entry in runtime.fight.actors[uid].state_ledger.entries
                        )
                    )
                print(
                    "native_rift_flow_complete",
                    dict(
                        wave_id=wave_id,
                        witness=witness,
                        round=fight.native_timeline_round,
                        player_hp=fight.actors[7].hp,
                    ),
                    flush=True,
                )
