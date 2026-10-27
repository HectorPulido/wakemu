"""Replay four historical descriptors without issuing a summon cast.

This isolated SQL/native-engine qualification is not an exact historical input
replay or a legitimate capture acquisition/graphical acceptance scenario.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import struct
import time
from types import SimpleNamespace

from postgres_case import PostgresCase


class RiftOwnedTofuNoInputTests(PostgresCase):
    def test_historical_roster_ready_turn_wave_company_and_recovery_without_summon_cast(
        self,
    ):
        from wakfu_server import heroes
        from wakfu_server.captured_roster import OwnedCapturedRoster
        from wakfu_server.captured_roster_store import save as save_roster
        from wakfu_server.combat_static_catalogs import (
            CompiledEffects,
            characteristic_registry,
        )
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
            actor_effects,
        )
        from wakfu_server.combat_remote_effects import active_actor_effects
        from wakfu_server.combat_ready import prepare_ready
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
        )
        from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_shared import Registry, Session
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope
        from wakfu_server.rift_dispatch_combat import finish_accepted_action
        from wakfu_server.rift_dispatch_lifecycle import (
            actor_reservation_shortfall,
            replenish_actor_ids,
        )
        from wakfu_server.rift_wave_initialization import initialize_registered_wave
        from wakfu_server.spells import encode_deck, available_spells
        from wakfu_server.progression import level_xp
        from rift_native_flow_fixture import build_flow_fixture

        path = Path(os.environ["WAKFU_QA_TOFU_CHECKPOINT"])
        historical = json.loads(path.read_bytes())
        if "snapshot" in historical:
            historical = historical["snapshot"]
        frozen_roster = deepcopy(historical["native_captured_rosters"]["25"])
        descriptor_sha = hashlib.sha256(
            json.dumps(frozen_roster["slots"], sort_keys=True).encode()
        ).hexdigest()
        self.assertEqual(
            [r["profile_id"] for r in frozen_roster["slots"] if r], [41, 4, 87, 4079]
        )
        state = historical["rift_wave_state"]
        account = self.store.register("tofu-no-input", "isolated-replay-password")["id"]
        members = [
            self.store.create_character(account, name, breed=breed)
            for name, breed in [
                ("Replay Osa", 2),
                ("Replay Steam", 16),
                ("Replay Eni", 7),
            ]
        ]
        decks = {}
        for member in members:
            # Natural level42, bare gear and legal native passive slots are
            # explicitly qualified inputs, not asserted historical gear/decks.
            passive = [
                s["id"]
                for s in available_spells(member["breed"], 42)
                if s["kind"] == "passive"
            ][:2]
            active = (
                [7307, 7317]
                if member["breed"] == 2
                else [
                    s["id"]
                    for s in available_spells(member["breed"], 42)
                    if s["kind"] == "active"
                ][:6]
            )
            decks[member["id"]] = encode_deck(active, passive)
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET level=42,hp_damage=0 WHERE id=%s",
                    (member["id"],),
                )
                db.execute(
                    "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                    (level_xp(42), member["id"]),
                )
                db.execute(
                    "UPDATE character_builds SET deck=%s WHERE character_id=%s AND build_index=0",
                    (decks[member["id"]], member["id"]),
                )
        members = [self.store.character(account, r["id"]) for r in members]
        osa, steam, eni = members
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, osa["id"])
        for hero in (steam, eni):
            heroes.add(self.store, account, generation, osa["id"], hero["id"])
        selected = osa["id"]
        for target in (steam["id"], eni["id"], osa["id"]):
            heroes.switch_main(self.store, account, generation, selected, target)
            selected = target
        cases = []
        target = os.environ.get("WAKFU_QA_TOFU_RECEIPT")

        def save_progress():
            if target:
                Path(target).write_text(
                    json.dumps(
                        dict(
                            scope="isolated historical-descriptor replay, not GUI capture acquisition",
                            historical_input_exactness=False,
                            descriptor_sha256=descriptor_sha,
                            variants=cases,
                        ),
                        indent=2,
                    )
                    + "\n"
                )

        for available in (True, False):
            case = {
                "tofu_available_variant": available,
                "historical_preavailability": "UNKNOWN",
                "historical_preselection": "UNKNOWN; qualification fixes selected Tofu slot1",
                "descriptor_sha256": descriptor_sha,
                "requests": [],
                "stages": [],
                "effect_trace": [],
            }
            cases.append(case)
            roster = deepcopy(frozen_roster)
            roster.update(owner_id=osa["id"], selected_slot=1, available=[True] * 10)
            roster["available"][1] = available
            # Explicit replay fixture rows only, in this test's isolated schema.
            with self.store.connection() as db:
                save_roster(
                    db,
                    osa,
                    OwnedCapturedRoster.from_record(
                        roster, expected_owner_id=osa["id"]
                    ),
                )
            characters = {
                r["id"]: self.store.character(account, r["id"]) for r in members
            }
            run = dict(
                catalog=deepcopy(state["catalog"]),
                policy=deepcopy(state["policy"]),
                seed=state["seed"],
                instance_id=270000426,
                wave=1,
            )
            component = build_flow_fixture(
                characters[osa["id"]],
                run,
                270000426,
                (-200,),
                (3,),
                compiled=CompiledEffects.from_published("npc_imported"),
                registry=characteristic_registry(),
                additional_player_ids=(steam["id"], eni["id"]),
                additional_player_sources=characters,
                ready=False,
            )
            characters, decks = component.characters, component.decks
            initial_ids = set(component.fight.actors)
            provider = OwnedExpirationFactory(
                characters=characters,
                monsters=component.fight.rift_monsters,
                decks=decks,
                actor_id=osa["id"],
                area_callbacks=True,
            )

            def check(current, label):
                unexpected = [
                    dict(
                        id=a.id,
                        source=getattr(a, "native_summon_source", None),
                        owner=a.owner_id,
                        controller=getattr(a, "native_controller_id", None),
                    )
                    for a in current.actors.values()
                    if a.id not in initial_ids
                    and a.owner_id == account
                    and getattr(a, "native_summon_source", {}).get("ref") == 4
                ]
                case["stages"].append(
                    dict(
                        label=label,
                        wave=current.rift_wave_state["wave"],
                        turn=current.turn_id,
                        actor_count=len(current.actors),
                        owned_tofu_births=unexpected,
                    )
                )
                if unexpected:
                    case["unexpected_canonical_births"] = {
                        str(row["id"]): deepcopy(
                            getattr(
                                current, "native_summon_creation_deliveries", {}
                            ).get(row["id"])
                        )
                        for row in unexpected
                    }
                save_progress()
                self.assertEqual(unexpected, [], label)
                rec = getattr(current, "native_captured_rosters", {}).get(
                    str(osa["id"])
                )
                if rec is not None:
                    self.assertEqual(rec["slots"], roster["slots"])
                    self.assertEqual(rec["available"], roster["available"])

            def stats(actor, current):
                if actor.controlled:
                    return actual_actor_stats(
                        characters[actor.id],
                        actor,
                        current.id,
                        wp_current=actor.effect_stats[4],
                        wp_maximum=actor.effect_maxima[4],
                        fight=current,
                    )
                return actual_monster_actor_stats(
                    current.rift_monsters[actor.id],
                    actor,
                    current.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                    fight=current,
                )

            def initialize(preview, action):
                packets = []
                for index, member in enumerate(characters.values()):
                    preview, own = prepare_server_initialization(
                        member,
                        preview.rift_monsters,
                        preview,
                        account,
                        decks[member["id"]],
                        action_id=action,
                        rng=component.rng,
                        fight_start=index == len(characters) - 1,
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                    packets.extend(own)
                return preview, packets

            with combat_diagnostic_scope(
                lambda **r: case["effect_trace"].append(r), limit=10000
            ):
                fight, runtime, opening = prepare_ready(
                    component.fight,
                    account,
                    True,
                    initialize=initialize,
                    stats_serializer=lambda a: stats(a, component.fight),
                    effects_serializer=actor_effects,
                    runtime_stats_serializer=stats,
                    turn_start_provider=provider.turn_start,
                    turn_end_provider=provider.turn_end,
                    expiration_runtime_factory=provider,
                )
                check(fight, "native-Ready-and-class-init")

                def initialize_wave(current, actors, monsters):
                    factory = component.runtime_factory(
                        current, action_id=runtime.action_id
                    )
                    dispatcher, outbox = factory(
                        current, {"native_retained_container": {"present": False}}
                    )
                    with current.effect_resolution():
                        initialize_registered_wave(
                            dispatcher,
                            actors=actors,
                            monsters=monsters,
                            player_ids=tuple(characters),
                        )
                    return tuple(outbox)

                def complete(packets):
                    if actor_reservation_shortfall(runtime.fight):
                        with self.store.connection() as db:
                            replenish_actor_ids(db, runtime.fight)
                    transition = finish_accepted_action(
                        runtime.fight,
                        runtime,
                        packets,
                        initialize_actor=lambda *_: (),
                        initialize_wave=initialize_wave,
                    )
                    runtime.fight = transition.fight
                    provider.monsters = deepcopy(runtime.fight.rift_monsters)
                    check(runtime.fight, "accepted-native-action")
                    if runtime.awaiting_ack is not None:
                        case["requests"].append(
                            dict(opcode=13510, counter=runtime.awaiting_ack)
                        )
                        runtime.acknowledge_turn(
                            struct.pack(">i", runtime.awaiting_ack)
                        )
                    return transition.packets

                def end():
                    actor = runtime.fight.current
                    case["requests"].append(
                        dict(
                            opcode=12403 if actor.controlled else "native-server-end",
                            actor=actor.id,
                        )
                    )
                    packets = (
                        runtime.end_turn(
                            account, actor.id, current_wire_turn(runtime.fight)
                        )
                        if actor.controlled
                        else runtime.end_server_turn(actor.id, runtime.fight.turn_id)
                    )
                    complete(packets)

                def to_osa():
                    for _ in range(len(runtime.fight.actors) * 3):
                        if runtime.fight.current.id == osa["id"]:
                            return
                        end()
                    self.fail("Native company turn never returned to Osamodas")

                # Visit every native company controller, then earn the actual
                # first wave boundary with paid non-summoning attacks.
                for _ in range(len(fight.actors) * 2):
                    end()
                paid = 0
                while runtime.fight.rift_wave_state["wave"] == 1 and paid < 20:
                    to_osa()
                    enemy = runtime.fight.actors[-200]
                    errors = []
                    for reference in (7317, 7307):
                        body = struct.pack(
                            ">qqiih",
                            osa["id"],
                            (osa["id"] << 32) | reference,
                            *enemy.position
                        )

                        def los(origin, target, current):
                            return authoritative_visible(
                                run["catalog"]["map_id"],
                                origin,
                                target,
                                current,
                                blocking_footprints={
                                    a.id: footprint(a.position, a.physical_radius)
                                    for a in current.actors.values()
                                    if a.hp > 0
                                },
                            )

                        try:
                            tx = prepare_server_spell(
                                body,
                                characters[osa["id"]],
                                runtime.fight.rift_monsters,
                                runtime.fight,
                                account,
                                decks[osa["id"]],
                                action_id=runtime.action_id + 1,
                                line_of_sight=los,
                                critical=False,
                                rng=component.rng,
                                player_characters=characters,
                                deck_blobs=decks,
                            )
                        except ValueError as error:
                            errors.append(str(error))
                            continue
                        case["requests"].append(
                            dict(
                                opcode=13260,
                                actor=osa["id"],
                                spell=reference,
                                target=list(enemy.position),
                            )
                        )
                        complete(
                            commit_spell_transaction(
                                runtime, tx, stats_serializer=stats
                            )
                        )
                        paid += 1
                        break
                    else:
                        self.fail("No legal non-summoning paid cast: " + repr(errors))
                    if runtime.fight.rift_wave_state["wave"] == 1:
                        end()
                self.assertGreaterEqual(runtime.fight.rift_wave_state["wave"], 2)
                case["paid_non_summoning_casts"] = paid
                check(runtime.fight, "real-next-wave")
                while runtime.awaiting_ack is not None:
                    runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                owner = Session(
                    account,
                    osa["id"],
                    generation,
                    run["catalog"]["map_id"],
                    run["instance_id"],
                )
                registry = Registry(
                    lambda s: self.store.current_character_session(
                        s.account_id, s.generation, s.character_id
                    )
                )
                shared = registry.register(
                    runtime.fight,
                    owner,
                    runtime=runtime,
                    join_context=dict(
                        arena=dict(
                            runtime.fight.native_qi_snapshot,
                            map_id=owner.map_id,
                            instance_id=0,
                            min_z=min(c[2] for c in runtime.fight.walkable),
                            max_z=max(c[2] for c in runtime.fight.walkable),
                        ),
                        terrain_effect_id=46,
                        terrain_instance_id=0,
                        leaders={
                            component.roles.player_team: osa["id"],
                            component.roles.npc_team: -200,
                        },
                    ),
                )
                before = source_snapshot(shared.fight)
                new_generation = self.store.begin_session(account)
                self.store.select_character(account, new_generation, osa["id"])
                replacement = Session(
                    account, osa["id"], new_generation, owner.map_id, owner.instance_id
                )
                # Register uses the original lease; then its real replacement
                # selection enables takeover without invoking any spell action.
                registry.takeover(
                    shared.fight.id,
                    replacement,
                    lambda current, view, session: owned_snapshot(
                        current,
                        view,
                        session,
                        actor_payload=lambda state, actor, recipient: (
                            stats(actor, state),
                            active_actor_effects(
                                state,
                                actor.id,
                                now_milliseconds=int(time.time() * 1000),
                            ),
                        ),
                    ),
                    persist_takeover=lambda previous: self.assertEqual(previous, owner),
                )
                self.assertTrue(registry.drain(shared.fight.id, replacement))
                self.assertEqual(source_snapshot(shared.fight), before)
                check(shared.fight, "selected-new-generation-and-owned-recovery")
                self.assertFalse(
                    any(r.get("spell") in (7348, 7350) for r in case["requests"])
                )
            generation = new_generation
        target = os.environ.get("WAKFU_QA_TOFU_RECEIPT")
        if target:
            Path(target).write_text(
                json.dumps(
                    dict(
                        scope="isolated historical-descriptor replay, not GUI capture acquisition",
                        historical_input_exactness=False,
                        descriptor_sha256=descriptor_sha,
                        variants=cases,
                        conclusion="No unsolicited owned Tofu reproduced; historical unexpected input remains OPEN",
                    ),
                    indent=2,
                )
                + "\n"
            )
