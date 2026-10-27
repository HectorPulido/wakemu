"""Actual positive fei payment through the production area-preview boundary.

Published source and constructors are real. This is a movement component, not
another complete Ready/GUI run or a claim about NPC AI destination selection.
"""
from copy import deepcopy
from contextlib import nullcontext
from dataclasses import replace
import json
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_QA_TACKLE_PREVIEW") == "1",
    "Explicit original-source movement component",
)
class NativeTackleAreaPreviewTests(unittest.TestCase):
    def test_player_and_npc_positive_tax_area_preview_rejection_retry_and_foreign_authority(
        self,
    ):
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
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server import combat_area_transaction as areas
        from wakfu_server import combat_voluntary_movement_events as movement_events
        from wakfu_server.combat_equipment_tackle_events import tackle_departure_preview
        from wakfu_server.combat_movement_runtime import apply_client, _with_areas
        from wakfu_server.combat_tackle_movement import movement_tackle_cost
        from wakfu_server.combat_qi_movement import movement_blocked_cells
        from wakfu_server.fight_checkpoint_store import snapshot
        import rift_native_flow_fixture as flow_fixture
        from wakfu_server.combat_geometry import published_geometry

        checkpoint = json.loads(
            Path(".runtime/qi-wave-282-20261024/checkpoint.private.json").read_bytes()
        )["snapshot"]
        source = checkpoint["rift_wave_state"]
        owner = next(row for row in checkpoint["actors"].values() if row["controlled"])
        store = Store(
            os.environ["WAKFU_DATABASE_URL"],
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        self.addCleanup(store.close)
        from wakfu_server.rift_policy import validate
        from wakfu_server.rift_native_gameplay_policy import load as native_policy
        from wakfu_server.rift_company_compensation import (
            company_actor_ids,
            install_company_compensation,
        )

        with store.connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            character = store.character(owner["owner_id"], owner["id"], db)
            policy = validate(
                db.execute(
                    "SELECT value FROM settings WHERE name='rift_policy'"
                ).fetchone()["value"]
            )
            policy["native_gameplay"] = native_policy(db)
        self.assertIn("INFINITE_WAVE", policy["native_gameplay"]["enabled_types"])
        run = dict(
            catalog=deepcopy(source["catalog"]),
            policy=policy,
            seed=source["seed"],
            instance_id=270001315,
            wave=1,
        )
        compiled, registry = (
            CompiledEffects.from_published("npc_imported"),
            characteristic_registry(),
        )

        def formation(map_id, quantity, **kwargs):
            # Choose facing contact before constructors, from real mutual map
            # edges. No initialized actor is relocated or has stats changed.
            self.assertEqual(quantity, 2)
            geometry = published_geometry(map_id)
            for cell in sorted(geometry.cells):
                north = (cell[0], cell[1] - 1, cell[2])
                east = (cell[0] + 1, cell[1], cell[2])
                if (
                    north in geometry.outgoing.get(cell, ())
                    and east in geometry.outgoing.get(cell, ())
                    and cell in geometry.outgoing.get(north, ())
                    and cell in geometry.outgoing.get(east, ())
                    and len(geometry.outgoing.get(cell, ())) >= 2
                    and len(geometry.outgoing.get(north, ())) >= 2
                    and len(geometry.outgoing.get(east, ())) >= 2
                ):
                    return cell, (north, east)
            self.fail("Native arena lacks the facing-contact formation")

        for controlled in (True, False):
            with self.subTest(controlled=controlled):
                with patch.object(
                    flow_fixture, "_native_positions", side_effect=formation
                ):
                    component = flow_fixture.build_flow_fixture(
                        character,
                        run,
                        270001315,
                        (-200, -201),
                        (3, 3),
                        compiled=compiled,
                        registry=registry,
                        minimum_separation=1,
                    )
                fight = component.fight
                dispatcher, _ = component.factory(fight)
                install_company_compensation(
                    dispatcher, actor_ids=company_actor_ids(fight)
                )
                target_actor_id = component.character["id"] if controlled else -201
                for _ in range(6):
                    if fight.current.id == target_actor_id:
                        break
                    current = fight.current
                    if current.controlled:
                        fight.end_turn(current.owner_id, current.id, current.turn_count)
                    else:
                        fight.end_server_turn(current.id, fight.turn_id)
                self.assertEqual(fight.current.id, target_actor_id)
                self.assertIs(fight.current.controlled, controlled)
                component.factory(fight)  # Actual source-backed movement authority.
                actor = fight.current
                blocked = movement_blocked_cells(fight, actor, fight.walkable)
                candidates, evaluated = [], []
                for start, destination in sorted(fight.edges):
                    if start != actor.position or destination in blocked:
                        continue
                    captured = []
                    ap, mp = movement_tackle_cost(
                        fight, actor, [destination], capture=captured
                    )
                    evaluated.append((destination, ap, mp))
                    if ap + mp > 0 and ap <= actor.ap and mp + 1 <= actor.mp:
                        candidates.append((destination, ap, mp))
                self.assertTrue(
                    candidates,
                    dict(
                        actor=actor.id,
                        position=actor.position,
                        ap=actor.ap,
                        mp=actor.mp,
                        dodge=actor.effect_stats[8],
                        evaluated=evaluated,
                        opponents=[
                            (
                                member.id,
                                member.position,
                                member.effect_stats[7],
                                member.direction,
                            )
                            for member in fight.actors.values()
                            if member.team != actor.team
                        ],
                    ),
                )
                destination, tax_ap, tax_mp = candidates[0]
                actor_id, origin = actor.id, actor.position
                before_ap, before_mp = actor.ap, actor.mp

                def serialize(member, current):
                    if member.controlled:
                        return actual_actor_stats(
                            component.characters[member.id],
                            member,
                            current.id,
                            wp_current=member.effect_stats[4],
                            wp_maximum=member.effect_maxima[4],
                            direction=member.direction,
                            fight=current,
                        )
                    return actual_monster_actor_stats(
                        current.rift_monsters[member.id],
                        member,
                        current.id,
                        wp_current=member.effect_stats[4],
                        wp_maximum=member.effect_maxima[4],
                        direction=member.direction,
                        fight=current,
                    )

                runtime = RuntimeMessages(fight, runtime_stats_serializer=serialize)
                calls, transfers = [], []
                original_delivery = movement_events.deliver_voluntary_movement

                def observed_delivery(dispatcher, **kwargs):
                    calls.append((dispatcher.native_retention.fight, dict(kwargs)))
                    return original_delivery(dispatcher, **kwargs)

                def checked_transfer(current, preview, payment):
                    transfers.append((current, preview, payment))
                    with self.assertRaisesRegex(ValueError, "consumed departure"):
                        with tackle_departure_preview(
                            current,
                            preview,
                            replace(payment, source_fight=deepcopy(current)),
                        ):
                            pass
                    # Equal IDs and identical data do not make a foreign
                    # dispatcher the preview bound by the accepted scope.
                    with tackle_departure_preview(current, preview, payment):
                        foreign_dispatcher, _ = component.factory(deepcopy(preview))
                        from wakfu_server.combat_equipment_tackle_events import (
                            deliver_tackle_boundary,
                        )

                        with self.assertRaisesRegex(
                            ValueError, "matching accepted departure"
                        ):
                            deliver_tackle_boundary(
                                foreign_dispatcher,
                                actor_id=actor_id,
                                from_cell=origin,
                                to_cell=destination,
                                action_id=99,
                            )
                    return tackle_departure_preview(current, preview, payment)

                def provider(current, **kwargs):
                    return areas.prepare_area_movement(
                        component.character,
                        current.rift_monsters,
                        current,
                        component.decks[component.character["id"]],
                        rng=component.rng,
                        player_characters=component.characters,
                        deck_blobs=component.decks,
                        **kwargs
                    )

                def execute(selected_provider):
                    if controlled:
                        return apply_client(
                            runtime,
                            actor.owner_id,
                            struct.pack(">q", actor_id)
                            + struct.pack(">iih", *destination),
                            lambda member: serialize(member, runtime.fight),
                            runtime_stats_serializer=serialize,
                            area_provider=selected_provider,
                        )
                    # The same production adapter used by apply_ai, with an
                    # explicit native server_move path instead of a planner.
                    return _with_areas(
                        runtime,
                        selected_provider,
                        lambda candidate, callback: (
                            [],
                            candidate.fight.server_move(
                                actor_id, [destination], step_callback=callback
                            ),
                        ),
                    )

                baseline, rng_before = snapshot(runtime.fight), component.rng.getstate()
                # Exact pre-fix behavior omitted the authority transfer.
                with patch.object(
                    areas, "tackle_departure_preview", lambda *_: nullcontext()
                ):
                    with self.assertRaisesRegex(
                        ValueError, "matching accepted departure"
                    ):
                        execute(provider)
                self.assertEqual(snapshot(runtime.fight), baseline)
                self.assertEqual(component.rng.getstate(), rng_before)

                def rejected(current, **kwargs):
                    provider(current, **kwargs)
                    raise ValueError("unpublished movement rejected")

                with patch.object(
                    areas, "tackle_departure_preview", checked_transfer
                ), patch.object(
                    movement_events, "deliver_voluntary_movement", observed_delivery
                ):
                    with self.assertRaisesRegex(
                        ValueError, "unpublished movement rejected"
                    ):
                        execute(rejected)
                    self.assertEqual(snapshot(runtime.fight), baseline)
                    self.assertEqual(component.rng.getstate(), rng_before)
                    execute(provider)
                moved = runtime.fight.actors[actor_id]
                self.assertEqual(moved.position, destination)
                self.assertEqual(
                    (moved.ap, moved.mp), (before_ap - tax_ap, before_mp - tax_mp - 1)
                )
                self.assertEqual(len(transfers), 2)
                self.assertEqual(len(calls), 2)
                for current, preview, payment in transfers:
                    self.assertIsNot(current, preview)
                    self.assertIs(payment.source_fight, current)
                    self.assertEqual(payment.publication, [True])
                self.assertEqual(calls[-1][1]["from_cell"], origin)
                self.assertEqual(calls[-1][1]["to_cell"], destination)
                # Outside the committed scope, even a previously real preview
                # cannot generate another native tackle notification.
                from wakfu_server.combat_equipment_tackle_events import (
                    deliver_tackle_boundary,
                )

                dispatcher, _ = component.factory(runtime.fight)
                self.assertEqual(
                    deliver_tackle_boundary(
                        dispatcher,
                        actor_id=actor_id,
                        from_cell=origin,
                        to_cell=destination,
                        action_id=99,
                    ),
                    (),
                )
