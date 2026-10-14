"""Actual Feca team spacing and distinct owner expiry clocks."""
import os
import random
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class MultiOwnerClassAreasTests(unittest.TestCase):
    def test_feca_team_glyph_spacing_and_independent_owner_expiry(self):
        from xelor_multiowner_fixture import TwoXelorFixture
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_timed_expiration import prepare_timed_expiration
        from wakfu_server.fight_checkpoint_store import snapshot
        from tools.combat_audit_turns import advance_actual_turn
        from tools.class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_effect_area_geometry import registered_area_cells

        fight, characters, monster, decks = TwoXelorFixture().fixture(
            level=200,
            caster_breed=1,
            active_spells=(6967,),
            second_player_breed=1,
            second_player_spells=(6967,),
            compact_arena=False,
            second_player_position=(-8, -6, -1),
            third_player_position=(-9, -7, -1),
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
        first_cells = None
        first_center = None
        for owner in (7, 8):
            for _ in range(16):
                if runtime.fight.current.id == owner:
                    break
                advance_actual_turn(runtime)
            self.assertEqual(runtime.fight.current.id, owner)
            before = snapshot(runtime.fight)
            if owner == 8:
                with self.assertRaises(ValueError) as rejected:
                    prepare_server_spell(
                        struct.pack(
                            ">qqiih", owner, (owner << 32) | 6967, *first_center
                        ),
                        characters[owner],
                        {-7: monster},
                        runtime.fight,
                        characters[owner]["account_id"],
                        decks[owner],
                        action_id=10 + owner,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        **common,
                    )
                self.assertEqual(rejected.exception.native_casting_result, "twV")
                self.assertEqual(snapshot(runtime.fight), before)
            _, adapter = server_runtime(
                characters[owner],
                {-7: monster},
                decks[owner],
                action_id=10 + owner,
                critical=False,
                **common,
            )
            selection = eligible_cast_targets(
                runtime.fight,
                characters[owner],
                decks[owner],
                (owner << 32) | 6967,
                adapter=adapter,
                actor_id=owner,
                limit=512,
                maximum_eligible=16,
                line_of_sight=lambda *args: True,
            )
            candidates = sorted(
                selection["eligible"],
                key=lambda row: (
                    abs(row["target"][0] - runtime.fight.actors[8].position[0])
                    + abs(row["target"][1] - runtime.fight.actors[8].position[1]),
                    tuple(row["target"]),
                ),
            )
            self.assertTrue(candidates, selection)
            tx = None
            for candidate in candidates:
                distance = sum(
                    abs(candidate["target"][i] - runtime.fight.actors[8].position[i])
                    for i in (0, 1)
                )
                if owner == 7 and not 2 <= distance <= 3:
                    continue
                possible = prepare_server_spell(
                    struct.pack(
                        ">qqiih", owner, (owner << 32) | 6967, *candidate["target"]
                    ),
                    characters[owner],
                    {-7: monster},
                    runtime.fight,
                    characters[owner]["account_id"],
                    decks[owner],
                    action_id=10 + owner,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    **common,
                )
                cells = set()
                for row in possible.fight.native_effect_areas.values():
                    if row.get("owner_id") == owner and row["reference"] in (
                        1474,
                        1477,
                    ):
                        cells.update(
                            registered_area_cells(
                                native_effect_areas()[str(row["reference"])],
                                row["cell"],
                                row["direction"],
                            )
                        )
                if cells:
                    first_cells = cells if first_cells is None else first_cells
                    if owner == 7:
                        first_center = tuple(candidate["target"])
                    tx = possible
                    break
            self.assertIsNotNone(tx, "No lawful Feca team-spaced glyph context found")
            self.assertEqual(snapshot(runtime.fight), before)
            runtime.fight = tx.fight

        owned = {
            owner: {
                uid
                for uid, row in runtime.fight.native_effect_areas.items()
                if row.get("owner_id") == owner and row["reference"] in (1474, 1477)
            }
            for owner in (7, 8)
        }
        self.assertTrue(owned[7])
        self.assertTrue(owned[8])
        self.assertTrue(owned[7].isdisjoint(owned[8]))
        footprints = {}
        for owner in (7, 8):
            footprints[owner] = set()
            for uid in owned[owner]:
                row = runtime.fight.native_effect_areas[uid]
                footprints[owner].update(
                    registered_area_cells(
                        native_effect_areas()[str(row["reference"])],
                        row["cell"],
                        row["direction"],
                    )
                )
        self.assertTrue(footprints[7].isdisjoint(footprints[8]))
        before = snapshot(runtime.fight)
        foreign = {uid: runtime.fight.native_effect_areas[uid] for uid in owned[8]}
        expired, packets = prepare_timed_expiration(
            runtime.fight,
            actor_id=7,
            round_number=2,
            phase="start",
            action_id=40,
        )
        self.assertTrue(owned[7].isdisjoint(expired.native_effect_areas))
        self.assertTrue(owned[8] <= set(expired.native_effect_areas))
        for uid, row in foreign.items():
            self.assertEqual(expired.native_effect_areas[uid]["owner_id"], 8)
            self.assertEqual(
                expired.native_effect_areas[uid]["reference"], row["reference"]
            )
            self.assertEqual(expired.native_effect_areas[uid]["cell"], row["cell"])
            self.assertEqual(
                expired.native_effect_areas[uid].get("remaining_activations"),
                row.get("remaining_activations"),
            )
        self.assertTrue(any(opcode == 13560 for opcode, _ in packets))
        self.assertEqual(snapshot(runtime.fight), before)
