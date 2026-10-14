"""Two real Sram owners: personal refunds and exact trap runner retirement."""
import json
import os
import random
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SramMultiOwnerTrapTests(unittest.TestCase):
    def test_actual_refund_and_retirement_preserve_other_owners_trap(self):
        from xelor_multiowner_fixture import TwoXelorFixture
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_effect_area_geometry import registered_area_cells
        from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot
        from tools.class_spell_eligible_targets import eligible_cast_targets
        from tools.combat_audit_turns import advance_actual_turn
        from tools.audit_feca_glyph_manual import path_to

        fight, characters, monster, decks = TwoXelorFixture().fixture(
            level=200,
            caster_breed=4,
            second_player_breed=4,
            compact_arena=False,
            second_player_position=(-12, -7, -1),
            third_player_position=(-9, -8, -1),
        )
        rng = random.Random(7)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                **common,
            )[0],
        )
        trap_ids = {}
        foreign_cells = set()
        entry_path = None
        for owner in (7, 8):
            for _ in range(24):
                if runtime.fight.current.id == owner:
                    break
                advance_actual_turn(runtime)
            self.assertEqual(runtime.fight.current.id, owner)
            uid = granted_spells(runtime.fight, owner)[5182]["uid"]
            _, adapter = server_runtime(
                characters[owner],
                {-7: monster},
                decks[owner],
                action_id=20 + owner,
                critical=False,
                **common,
            )
            selection = eligible_cast_targets(
                runtime.fight,
                characters[owner],
                decks[owner],
                uid,
                adapter=adapter,
                actor_id=owner,
                limit=512,
                maximum_eligible=16,
                line_of_sight=lambda *args: True,
            )
            choices = selection["eligible"]
            if owner == 7:
                choices = sorted(
                    choices,
                    reverse=True,
                    key=lambda row: sum(
                        abs(row["target"][i] - runtime.fight.actors[8].position[i])
                        for i in (0, 1)
                    ),
                )
            selected = None
            for choice in choices:
                tx = prepare_server_spell(
                    struct.pack(">qqiih", owner, uid, *choice["target"]),
                    characters[owner],
                    {-7: monster},
                    runtime.fight,
                    characters[owner]["account_id"],
                    decks[owner],
                    action_id=20 + owner,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    **common,
                )
                born = [
                    row
                    for key, row in tx.fight.native_effect_areas.items()
                    if key not in runtime.fight.native_effect_areas
                    and row.get("owner_id") == owner
                    and row.get("reference") == 778
                ]
                self.assertEqual(len(born), 1)
                trap = born[0]
                cells = set(
                    registered_area_cells(
                        native_effect_areas()["778"], trap["cell"], trap["direction"]
                    )
                )
                if any(
                    actor.position[:2] in cells for actor in tx.fight.actors.values()
                ):
                    continue
                if owner == 8:
                    destinations = {
                        cell for cell in tx.fight.walkable if cell[:2] in cells
                    }
                    try:
                        path = path_to(tx.fight, tx.fight.actors[8], destinations)
                    except ValueError:
                        continue
                    if not path or any(cell[:2] in foreign_cells for cell in path):
                        continue
                    if len(path) > tx.fight.actors[8].mp:
                        continue
                    entry_path = path
                else:
                    foreign_cells = cells
                selected = tx
                trap_ids[owner] = trap["uid"]
                break
            self.assertIsNotNone(selected, selection)
            runtime.fight = selected.fight

        self.assertEqual(len(trap_ids), 2)
        self.assertNotEqual(trap_ids[7], trap_ids[8])
        saved = snapshot(runtime.fight)
        restored = Checkpoints._read_snapshot(json.loads(json.dumps(saved)))
        self.assertEqual(restored["native_effect_areas"], saved["native_effect_areas"])
        self.assertEqual(
            len(
                [
                    row
                    for row in restored["native_effect_areas"].values()
                    if row["reference"] == 778
                ]
            ),
            2,
        )
        parent = runtime.fight.native_effect_areas[trap_ids[8]]["effect_uid"]
        owner7_ap = runtime.fight.actors[7].ap
        owner8_ap = runtime.fight.actors[8].ap
        source = snapshot(runtime.fight)

        def area_provider(preview, **kwargs):
            return prepare_area_movement(
                characters[8],
                {-7: monster},
                preview,
                decks[8],
                **common,
                **kwargs,
            )

        packets, _ = apply_client(
            runtime,
            characters[8]["account_id"],
            struct.pack(">q", 8)
            + b"".join(struct.pack(">iih", *cell) for cell in entry_path),
            lambda actor: b"",
            area_provider=area_provider,
        )
        self.assertNotEqual(runtime.fight.actors[8].position, tuple(entry_path[-1]))
        self.assertEqual(runtime.fight.actors[8].ap, owner8_ap + 2)
        self.assertEqual(runtime.fight.actors[7].ap, owner7_ap)
        self.assertNotIn(trap_ids[8], runtime.fight.native_effect_areas)
        self.assertNotIn(parent, runtime.fight.native_owned_area_effects)
        self.assertNotIn(parent, runtime.fight.native_retained_records)
        after = snapshot(runtime.fight)
        self.assertEqual(
            after["native_effect_areas"][str(trap_ids[7])],
            source["native_effect_areas"][str(trap_ids[7])],
        )
        self.assertEqual(
            sum(
                opcode == 13560
                and len(body) >= 16
                and struct.unpack(">qq", body[-16:]) == (8, parent)
                for opcode, body in packets
            ),
            1,
        )
        repeat_path = path_to(
            runtime.fight,
            runtime.fight.actors[8],
            {cell for cell in runtime.fight.walkable if cell[:2] in cells},
        )
        self.assertFalse(any(cell[:2] in foreign_cells for cell in repeat_path))
        repeated, _ = apply_client(
            runtime,
            characters[8]["account_id"],
            struct.pack(">q", 8)
            + b"".join(struct.pack(">iih", *cell) for cell in repeat_path),
            lambda actor: b"",
            area_provider=area_provider,
        )
        self.assertEqual(runtime.fight.actors[8].position, tuple(repeat_path[-1]))
        self.assertEqual(runtime.fight.actors[8].ap, owner8_ap + 2)
        self.assertFalse(
            any(
                opcode == 13560
                and len(body) >= 16
                and struct.unpack(">qq", body[-16:]) == (8, parent)
                for opcode, body in repeated
            )
        )
        after = snapshot(runtime.fight)
        reloaded = Checkpoints._read_snapshot(json.loads(json.dumps(after)))
        self.assertEqual(reloaded["native_effect_areas"], after["native_effect_areas"])
        self.assertEqual(
            len(
                [
                    row
                    for row in reloaded["native_effect_areas"].values()
                    if row["reference"] == 778
                ]
            ),
            1,
        )
        self.assertEqual(
            reloaded["native_effect_areas"][str(trap_ids[7])]["owner_id"], 7
        )
