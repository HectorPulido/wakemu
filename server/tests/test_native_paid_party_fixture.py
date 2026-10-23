"""Bounded native endgame inventory admission and real paid damage previews."""
import json
from pathlib import Path
from random import Random
import struct

from postgres_case import PostgresCase


class NativePaidPartyFixtureTests(PostgresCase):
    def test_six_owned_geared_players_preview_native_nox_without_state_grants(self):
        from native_paid_party_fixture import (
            native_endgame_iop_build,
            native_paid_party_fixture,
        )
        from test_ultimate_encounter_scene_recipes import (
            UltimateEncounterSceneRecipeTests,
        )
        from wakfu_server.combat_actor_snapshot import native_actor_catalog
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.dungeon_encounters import enemy_formation
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_spell_grant import granted_spells

        scene = UltimateEncounterSceneRecipeTests().scene(5664)
        boss_cell = tuple(
            enemy_formation(
                {
                    "map_id": scene["map_id"],
                    "cells": scene["cells"],
                    "edges": scene["edges"],
                },
                scene["anchor"],
                1,
                player_slots=6,
            )[0]
        )
        radius = native_actor_catalog()["npc_profiles"]["5664"]["physical_radius"]
        forbidden = footprint(boss_cell, radius)
        available = [
            tuple(cell) for cell in scene["cells"] if tuple(cell[:2]) not in forbidden
        ]
        available.sort(
            key=lambda cell: (
                abs(cell[0] - boss_cell[0]) + abs(cell[1] - boss_cell[1]),
                cell,
            )
        )
        # Existing native cells are declared placement inputs, not terrain edits.
        cells = tuple(available[:6])
        build = native_endgame_iop_build()
        (
            fight,
            characters,
            monsters,
            decks,
            resources,
            _,
            receipt,
        ) = native_paid_party_fixture(
            self.store, scene, (build,) * 6, cells, name_prefix="paid-party"
        )
        self.assertEqual(len(characters), 6)
        self.assertEqual(len({row["account_id"] for row in characters.values()}), 6)
        self.assertEqual(set(fight.actors), {*characters, -200})
        boss = fight.actors[-200]
        self.assertEqual(
            (boss.hp, boss.max_hp), (monsters[-200]["hp"], monsters[-200]["max_hp"])
        )
        for identity, character in characters.items():
            actor = fight.actors[identity]
            values = resources[identity]
            self.assertEqual(actor.hp, character["max_hp"])
            self.assertEqual(
                (actor.ap, actor.mp, actor.effect_stats[4]),
                (values["ap"], values["mp"], values["wp"]),
            )
            self.assertEqual(len(receipt["equipment"][identity]), len(build.gear))
        # Preserve native initiative. A boss opening uses the real ACK/end/start
        # path before an owned player can request a preview; never change order.
        rng = Random(7)
        first = next(iter(characters))
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda phase, **kwargs: prepare_server_turn_end(
                characters[first], monsters, phase, decks[first], **common, **kwargs
            ),
            turn_start_provider=lambda phase, **kwargs: prepare_server_turn_start(
                characters[first], monsters, phase, decks[first], **common, **kwargs
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[first],
                monsters,
                decks[first],
                action_id=action_id,
                critical=False,
                **common
            )[0],
        )
        boundaries = 0
        acknowledgements = 0
        while runtime.fight.current.id not in characters and boundaries < 3:
            advance_actual_turn(runtime)
            boundaries += 1
            # Native skip/additional-turn delivery can enqueue another real
            # acknowledgment while consuming the preceding one. Use every
            # actual token; never clear synchronization fields by hand.
            for _ in range(32):
                pending = runtime.awaiting_ack
                if pending is None:
                    break
                runtime.acknowledge_turn(struct.pack(">i", pending))
                acknowledgements += 1
            else:
                self.fail("Native opening acknowledgment chain exceeded32")
        fight = runtime.fight
        boss = fight.actors[-200]
        self.assertTrue(
            fight.current.id in characters,
            (
                "No owned player after three native boundaries",
                fight.current.id,
                tuple(characters),
            ),
        )
        receipt["actual_opening_boundaries"] = boundaries
        receipt["actual_chained_acknowledgements"] = acknowledgements
        identity = fight.current.id
        rng_state = rng.getstate()
        baseline = snapshot(fight)
        rows = []
        grants = granted_spells(fight, identity)
        for reference in (*build.active_spells, 8402, 8403):
            rng.setstate(rng_state)
            try:
                transaction = prepare_server_spell(
                    struct.pack(
                        ">qqiih",
                        identity,
                        grants[reference]["uid"]
                        if reference in grants
                        else (identity << 32) | reference,
                        *boss.position
                    ),
                    characters[identity],
                    monsters,
                    fight,
                    characters[identity]["account_id"],
                    decks[identity],
                    action_id=runtime.action_id + 1,
                    rng=rng,
                    critical=None,
                    player_characters=characters,
                    deck_blobs=decks,
                    line_of_sight=lambda origin, target, current: authoritative_visible(
                        scene["map_id"],
                        origin,
                        target,
                        current,
                        blocking_footprints={
                            actor.id: footprint(actor.position, actor.physical_radius)
                            for actor in current.actors.values()
                            if actor.hp > 0
                        },
                    ),
                )
                if reference in (8402, 8403):
                    self.assertIn(reference, grants)
                    self.assertEqual(transaction.plan["costs"]["ap"], 0)
                    self.assertEqual(
                        transaction.fight.actors[identity].ap, fight.actors[identity].ap
                    )
                    resource = "mp" if reference == 8402 else "wp"
                    self.assertEqual(transaction.plan["costs"][resource], 1)
                    if resource == "mp":
                        self.assertEqual(
                            transaction.fight.actors[identity].mp,
                            fight.actors[identity].mp - 1,
                        )
                    else:
                        self.assertEqual(
                            transaction.fight.actors[identity].effect_stats[4],
                            fight.actors[identity].effect_stats[4] - 1,
                        )
                rows.append(
                    dict(
                        reference=reference,
                        costs=transaction.plan["costs"],
                        damage=boss.hp - transaction.fight.actors[-200].hp,
                        critical=transaction.plan.get("critical_decision"),
                    )
                )
            except ValueError as error:
                rows.append(dict(reference=reference, rejected=str(error)))
            self.assertEqual(snapshot(fight), baseline)
        receipt.update(
            previews=rows,
            source_actor=identity,
            source_stats=dict(fight.actors[identity].effect_stats),
            target_stats=dict(boss.effect_stats),
            source_position=fight.actors[identity].position,
            target_position=boss.position,
            scope="Uncommitted real paid admission/effect previews; no victory or score claim",
        )
        output = Path(
            ".runtime/parallel-readiness-20261021/native-party-nox-damage-previews.json"
        )
        output.write_text(json.dumps(receipt, indent=2))
        self.assertTrue(any(row.get("damage", 0) > 0 for row in rows), rows)
        self.assertTrue(
            all(
                any(
                    row["reference"] == reference and row.get("damage", 0) > 0
                    for row in rows
                )
                for reference in (8402, 8403)
            ),
            rows,
        )
