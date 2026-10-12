"""Pure differential and authority regressions for private native1100."""
import json
import struct
from pathlib import Path
from types import SimpleNamespace
import unittest
from wakfu_server.combat_instance_level_group import (
    InstanceDifficultySnapshot,
    native_override,
    runtime_child_level,
)
from wakfu_server.combat_effect_dispatch import UnsupportedEffectExecution
from wakfu_server.combat_instance_publication import InstancePublicationTracker
from wakfu_server.maps.proto_dungeon import encode

HERE = Path(__file__).parent / "fixtures/native_monster_recovery"


def snapshot(identity, value):
    return InstanceDifficultySnapshot(
        identity, value, "fBg.drG.Optional.empty" if value is None else "fBg.drG.fBf.GN"
    )


def effect(count=0, base=0, factor=1, source=0):
    raw = [source, 0, base, 0, factor, 0][: count * 2]
    return {"effect_class": 1100, "parameters": raw, "parameter_count": count}


def published_fight(npc_id, difficulty):
    """Representable actual placement: one NPC GN and one empty-Optional PC."""
    player_id = 2 if npc_id == 1 else 1
    scope = (7, "oracle-runtime-session", player_id, 1385, 0)
    context = encode({"difficulty_level": difficulty})
    body = b"".join(
        struct.pack(">H", len(block)) + block
        for block in (b"entity", b"", b"\0\0", context)
    )
    tracker = InstancePublicationTracker()
    tracker.after_write(struct.pack(">IH", 6 + len(body), 13974) + body, scope)
    fight = SimpleNamespace(actors={1: SimpleNamespace(id=1), 2: SimpleNamespace(id=2)})
    if not tracker.bind_encounter(fight, scope, npc_ids=(npc_id,), player_id=player_id):
        raise AssertionError("Actual publication did not bind")
    return fight


class InstanceLevelGroupTests(unittest.TestCase):
    def setUp(self):
        self.invocation = SimpleNamespace(caster_id=1, target_id=2, level=53)
        self.snapshots = {1: snapshot(1, 7), 2: snapshot(2, 3)}

    def test_270_actual_native_rows_match_override_and_signed_short(self):
        rows = [
            json.loads(line)
            for line in (HERE / "native-oracle.jsonl").read_text().splitlines()
        ]
        self.assertEqual(len(rows), 270)
        runtime_rows = 0
        for row in rows:
            with self.subTest(row=row):
                count = row["parameter_count"]
                source = row["source_parameter"]
                e = effect(count, float(row["base"]), float(row["factor"]), source)
                values = {"parameters": ([source] + [0] * (count - 1)) if count else []}
                snapshots = {
                    1: snapshot(1, row["caster_difficulty"]),
                    2: snapshot(2, row["target_difficulty"]),
                }
                # Controlled native oracle actors intentionally cover arbitrary
                # GN pairs; compare the actual merged arithmetic primitive.
                actual = native_override(e, values, self.invocation, snapshots.get)
                self.assertEqual(actual, row["native_override"])
                if actual != -1:
                    self.assertEqual(
                        ((actual + 32768) % 65536) - 32768,
                        row["native_effective_short"],
                    )
                # These90 rows also match a real placement publication domain:
                # one NPC with GN7/3 and one actual empty-Optional player.
                pair = (row["caster_difficulty"], row["target_difficulty"])
                if pair in ((7, None), (None, 3)):
                    fight = (
                        published_fight(1, 7)
                        if pair == (7, None)
                        else published_fight(2, 3)
                    )
                    self.assertEqual(
                        runtime_child_level(
                            e,
                            values,
                            self.invocation,
                            fight,
                            return_native_override=True,
                        ),
                        row["native_override"],
                    )
                    expected = (
                        self.invocation.level
                        if actual == -1
                        else row["native_effective_short"]
                    )
                    self.assertEqual(
                        runtime_child_level(e, values, self.invocation, fight), expected
                    )
                    runtime_rows += 1
                self.assertTrue(row["actor_route"])
                self.assertFalse(row["cell_route"])
        self.assertEqual(runtime_rows, 90)

    def test_unknown_actual_instance_is_not_assumed_empty(self):
        with self.assertRaises(UnsupportedEffectExecution):
            runtime_child_level(
                effect(), {"parameters": []}, self.invocation, SimpleNamespace()
            )

    def test_explicit_native_empty_optional_produces_zero(self):
        self.snapshots[1] = snapshot(1, None)
        self.assertEqual(
            native_override(
                effect(), {"parameters": []}, self.invocation, self.snapshots.get
            ),
            0,
        )

    def test_nonzero_source_parameter_selects_actual_target(self):
        for value in (1, -3):
            self.assertEqual(
                native_override(
                    effect(1, source=value),
                    {"parameters": [value]},
                    self.invocation,
                    self.snapshots.get,
                ),
                3,
            )

    def test_native_null_target_branch_is_zero_without_fake_snapshot(self):
        self.invocation.target_id = None
        self.assertEqual(
            native_override(
                effect(1, source=1), {"parameters": [1]}, self.invocation, None
            ),
            0,
        )

    def test_wrong_actor_binding_is_rejected(self):
        with self.assertRaises(UnsupportedEffectExecution):
            native_override(
                effect(),
                {"parameters": []},
                self.invocation,
                lambda identity: snapshot(2, 7),
            )

    def test_malformed_two_parameter_variant_fails_closed(self):
        with self.assertRaises(UnsupportedEffectExecution):
            native_override(
                effect(2), {"parameters": [0, 1]}, self.invocation, self.snapshots.get
            )

    def test_negative_one_native_override_keeps_parent_level(self):
        fight = published_fight(1, 7)
        e = effect(3, -1, 0)
        self.assertEqual(
            runtime_child_level(
                e,
                {"parameters": [0, -1, 0]},
                self.invocation,
                fight,
                return_native_override=True,
            ),
            -1,
        )
        self.assertEqual(
            runtime_child_level(e, {"parameters": [0, -1, 0]}, self.invocation, fight),
            53,
        )

    def test_snapshot_provenance_and_native_integer_range_required(self):
        for value, source in (
            (True, "fBg.drG.fBf.GN"),
            (2**31, "fBg.drG.fBf.GN"),
            (None, "guessed_absent"),
        ):
            with self.assertRaises(ValueError):
                InstanceDifficultySnapshot(1, value, source)


if __name__ == "__main__":
    unittest.main()
