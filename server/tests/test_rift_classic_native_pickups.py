"""Prospective classic policy on original Tainela geometry and normal mobs.

One isolated Ready fixture supplies independent native artifact/orb consumers.
Only publication-generation selection is a metadata transport seam. No entry,
full-wave composition, NPC AI selection, or forty-round claim is made here.
"""
from collections import deque
from copy import deepcopy
import json
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_QA_RIFT_CLASSIC_PICKUPS") == "1",
    "Explicit private-source classic pickup component",
)
class ClassicNativePickupTests(unittest.TestCase):
    def test_classic_ready_two_choices_native_death_orb_paid_contacts_and_clock(self):
        from wakfu_server import native_catalog, native_compiled_catalog as publications

        with native_catalog._database().connection() as db:
            rows = db.execute(
                "SELECT generation FROM native_compiled_catalog_releases "
                "WHERE generation LIKE %s AND complete",
                ("74b385%",),
            ).fetchall()
        self.assertEqual(len(rows), 1)
        generation = rows[0]["generation"]
        manifest = publications._store().header(generation)
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

        seam = patch.object(
            publications, "resolve_publication", side_effect=pinned_metadata
        )
        seam.start()
        self.addCleanup(seam.stop)
        from wakfu_server.store import Store
        from wakfu_server.combat_static_catalogs import (
            CompiledEffects,
            characteristic_registry,
        )
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_start,
            prepare_server_turn_end,
        )
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_qi_movement import movement_blocked_cells
        from wakfu_server.combat_tackle_movement import movement_tackle_cost
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.combat_death import newly_registered_death_messages
        from wakfu_server.dungeon_combat_scaling import _prepare_constructor
        from rift_native_flow_fixture import build_flow_fixture

        checkpoint = json.loads(
            Path(".runtime/qi-wave-282-20261024/checkpoint.private.json").read_bytes()
        )["snapshot"]
        source = checkpoint["rift_wave_state"]
        owner = next(
            actor for actor in checkpoint["actors"].values() if actor["controlled"]
        )
        store = Store(
            os.environ["WAKFU_DATABASE_URL"],
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        self.addCleanup(store.close)
        with store.connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            character = store.character(owner["owner_id"], owner["id"], db)
        self.assertEqual(character["breed"], 19)
        policy = deepcopy(source["policy"])
        policy["native_gameplay"]["enabled_types"] = [
            "INFINITE_WAVE",
            "ULTIMATE_INFINITE_WAVE",
        ]
        self.assertTrue(policy["native_gameplay"]["enabled"])
        self.assertTrue(policy["native_gameplay"]["artifacts"]["enabled"])
        run = dict(
            catalog=deepcopy(source["catalog"]),
            policy=policy,
            seed=source["seed"],
            instance_id=270001314,
            wave=1,
        )
        self.assertEqual(
            (run["catalog"]["type"], run["catalog"]["map_id"]), ("INFINITE_WAVE", 1314)
        )
        self.assertIn(3, run["catalog"]["species_refs"])
        component = build_flow_fixture(
            character,
            run,
            270001314,
            (-200, -201),
            (3, 3),
            compiled=CompiledEffects.from_published("npc_imported"),
            registry=characteristic_registry(),
        )
        fight = component.fight
        identity, account = component.character["id"], component.character["account_id"]
        deck = component.decks[identity]
        self.assertEqual(
            (component.roles.player_team, component.roles.npc_team), (1, 0)
        )
        for actor_id in (-200, -201):
            _prepare_constructor(fight.actors[actor_id], 3)
            self.assertNotIn(43, fight.actors[actor_id].native_world_properties)
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
        self.assertTrue(opening)
        self.assertTrue(
            all(
                any(
                    entry.reference == 6807
                    for entry in fight.actors[uid].state_ledger.entries
                )
                for uid in (-200, -201)
            )
        )
        group = fight.rift_wave_state["native_artifact_groups"]["1"]
        self.assertEqual((len(group["remaining"]), group["choices_allowed"]), (2, 1))
        original_artifacts = set(group["remaining"])
        self.assertTrue(
            all(
                fight.native_effect_areas[uid]["native_area_contract"] == "faM"
                for uid in original_artifacts
            )
        )
        self.assertEqual(
            fight.rift_wave_state["native_artifact_generation"]["1"][
                "template_effect_reference"
            ],
            147120,
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
            return actual_monster_actor_stats(
                current.rift_monsters[actor.id],
                actor,
                current.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                direction=actor.direction,
                fight=current,
            )

        def make_runtime(current):
            def turn(state, *, actor_id, action_id, start):
                callback = (
                    prepare_server_turn_start if start else prepare_server_turn_end
                )
                return callback(
                    component.character,
                    state.rift_monsters,
                    state,
                    deck,
                    actor_id=actor_id,
                    action_id=action_id,
                    rng=component.rng,
                    player_characters=component.characters,
                    deck_blobs=component.decks,
                )

            runtime = RuntimeMessages(
                current,
                clock=lambda: 100.0,
                runtime_stats_serializer=serialize,
                expiration_runtime_factory=lambda *, action_id: component.runtime_factory(
                    runtime.fight, action_id=action_id
                ),
                turn_start_provider=lambda state, **kw: turn(state, **kw, start=True),
                turn_end_provider=lambda state, **kw: turn(state, **kw, start=False),
            )
            runtime.turn_started()
            return runtime

        def end_current(runtime):
            actor = runtime.fight.current
            self.assertIsNotNone(actor)
            packets = (
                runtime.end_turn(account, actor.id, current_wire_turn(runtime.fight))
                if actor.controlled
                else runtime.end_server_turn(actor.id, runtime.fight.turn_id)
            )
            if runtime.awaiting_ack is not None:
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
            return packets

        def reach_player(runtime):
            for _ in range(12):
                if (
                    runtime.fight.current is not None
                    and runtime.fight.current.id == identity
                ):
                    return
                end_current(runtime)
            self.fail("Native turn sequence did not reach the player")

        def route(runtime, destination, *, avoid=()):
            current, actor = runtime.fight, runtime.fight.actors[identity]
            blocked = set(
                movement_blocked_cells(current, actor, current.walkable)
            ) | set(avoid)
            previous, pending = {actor.position: None}, deque((actor.position,))
            outgoing = {}
            for origin, target in current.edges:
                outgoing.setdefault(origin, []).append(target)
            while pending and destination not in previous:
                origin = pending.popleft()
                for target in sorted(outgoing.get(origin, ())):
                    if target not in blocked and target not in previous:
                        previous[target] = origin
                        pending.append(target)
            if destination not in previous:
                return None
            path, cursor = [], destination
            while cursor != actor.position:
                path.append(cursor)
                cursor = previous[cursor]
            return list(reversed(path))

        def walk(runtime, path):
            actor = runtime.fight.actors[identity]
            before = actor.mp
            packets, accepted = apply_client(
                runtime,
                account,
                struct.pack(">q", identity)
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
                    **kw
                ),
            )
            self.assertTrue(accepted)
            self.assertTrue(packets)
            self.assertLess(runtime.fight.actors[identity].mp, before)
            current_registry(runtime.fight)
            return packets

        baseline = make_runtime(deepcopy(fight))
        reach_player(baseline)
        # A private branch observes the real normal-mob death publisher before
        # any artifact can change its health/damage or end this component fight.
        orb_runtime = deepcopy(baseline)
        before_sequence = orb_runtime.fight.sequence
        action_id = orb_runtime.action_id + 1
        factory = component.runtime_factory(orb_runtime.fight, action_id=action_id)
        dispatcher, kill_packets = factory(
            orb_runtime.fight, {"native_retained_container": {"present": False}}
        )
        self.assertIn("402298", dispatcher.effects)
        self.assertTrue(
            dispatcher.execute(
                EffectInvocation(
                    402298,
                    1,
                    identity,
                    -200,
                    orb_runtime.fight.actors[-200].position,
                    native_explicit_target=True,
                    native_context_hex=constructed_execution_context().payload().hex(),
                    native_retained_container={"present": False},
                )
            )
        )
        self.assertTrue(kill_packets)
        orb_runtime.prepare_fight_delivery(
            kill_packets,
            orb_runtime.fight,
            action_id=action_id,
            operation="classic_native_kill_component",
        )
        deaths = newly_registered_death_messages(
            orb_runtime, after_sequence=before_sequence
        )
        self.assertTrue(any(opcode == 12727 for opcode, _ in deaths))
        orbs = [
            row
            for row in orb_runtime.fight.native_effect_areas.values()
            if row["reference"] in (1574, 1576, 1577, 1578)
        ]
        self.assertEqual(len(orbs), 1)
        orb = orbs[0]
        original_orb = dispatcher.native_area_events._definition(orb)
        self.assertEqual(
            (original_orb["type"], original_orb["native_class"]), ("GLYPH", "bcT")
        )
        expiry_runtime = deepcopy(orb_runtime)
        avoid = {
            tuple(row["cell"])
            for row in orb_runtime.fight.native_effect_areas.values()
            if row["native_area_contract"] == "faM"
        }
        path = route(orb_runtime, tuple(orb["cell"]), avoid=avoid)
        self.assertTrue(path, "Native normal orb lacks a QI-passable contact route")
        ap, mp = movement_tackle_cost(
            orb_runtime.fight, orb_runtime.fight.actors[identity], path
        )
        self.assertLessEqual(len(path) + mp, orb_runtime.fight.actors[identity].mp)
        self.assertLessEqual(ap, orb_runtime.fight.actors[identity].ap)
        walk(orb_runtime, path)
        self.assertNotIn(orb["uid"], orb_runtime.fight.native_effect_areas)
        for _ in range(8):
            end_current(expiry_runtime)
            if expiry_runtime.fight.current.id == identity:
                break
        self.assertNotIn(orb["uid"], expiry_runtime.fight.native_effect_areas)

        # Independent branch: one classic choice, one original opponent grant.
        runtime = deepcopy(baseline)
        for _ in range(32):
            reach_player(runtime)
            group = runtime.fight.rift_wave_state["native_artifact_groups"]["1"]
            if group["choices_made"]:
                break
            options = []
            for uid in group["remaining"]:
                destination = tuple(runtime.fight.native_effect_areas[uid]["cell"])
                avoid = {
                    tuple(row["cell"])
                    for row in runtime.fight.native_effect_areas.values()
                    if row["native_area_contract"] == "faM" and row["uid"] != uid
                }
                path = route(runtime, destination, avoid=avoid)
                if path:
                    options.append(path)
            self.assertTrue(options, "Classic artifact choices lack a native QI route")
            path = min(options, key=lambda value: (len(value), value))
            actor = runtime.fight.actors[identity]
            prefix = path[: actor.mp]
            while prefix:
                ap, mp = movement_tackle_cost(runtime.fight, actor, prefix)
                if len(prefix) + mp <= actor.mp and ap <= actor.ap:
                    break
                prefix.pop()
            if prefix:
                walk(runtime, prefix)
            if not runtime.fight.rift_wave_state["native_artifact_groups"]["1"][
                "choices_made"
            ]:
                end_current(runtime)
        group = runtime.fight.rift_wave_state["native_artifact_groups"]["1"]
        self.assertEqual((group["choices_made"], group["remaining"]), (1, []))
        self.assertEqual(len(group["assignments"]), 1)
        assignment = group["assignments"][0]
        for uid, origin in (
            (assignment["collected"], "contact"),
            (assignment["opponent"], "assignment"),
        ):
            self.assertIn(uid, original_artifacts)
            self.assertNotIn(uid, runtime.fight.native_effect_areas)
            receipt = runtime.fight.native_artifact_activation_receipts[str(uid)]
            self.assertTrue(receipt["complete"])
            self.assertEqual(receipt["origin"], origin)
        print(
            "classic_native_pickups_complete",
            dict(
                map_id=1314,
                breed=character["breed"],
                level=character["level"],
                normal_mob=3,
                orb_reference=orb["reference"],
                artifacts=2,
                choices=group["choices_made"],
            ),
            flush=True,
        )
