"""Regional health contributions must change maximum HP without free healing."""
import unittest
from unittest.mock import Mock, patch

from wakfu_server import territory_bonuses, equipment_stats, health, wire


class TerritoryControlHealthTests(unittest.TestCase):
    def character(self):
        return dict(
            id=1,
            account_id=1,
            breed=8,
            level=6,
            hp=41,
            map_id=527,
            x=1,
            y=2,
            z=0,
            inventory_items=[],
            builds={
                0: dict(equipment="", sheet=wire.proto_field(24, (1 << 64) - 1).hex())
            },
        )

    def test_native_control_health_transitions_do_not_stack_or_heal(self):
        original = self.character()
        baseline = equipment_stats.effective_character(original)
        for delta in (1, 2, -1, 0, 1, 0):
            with self.subTest(delta=delta):
                projected = dict(original, territory_stat_bonuses={1: delta})
                actual = equipment_stats.effective_character(projected)
                self.assertEqual(actual["max_hp"], baseline["max_hp"] + delta)
                self.assertEqual(actual["hp"], original["hp"])
                self.assertEqual(
                    equipment_stats.effective_character(actual)["max_hp"],
                    actual["max_hp"],
                )
                packet = wire.owned_public_characteristics(projected)
                import struct

                count = struct.unpack_from(">H", packet)[0]
                rows = [
                    struct.unpack_from(">Biiii", packet, 2 + i * 17)
                    for i in range(count)
                ]
                hp = next(row for row in rows if row[0] == 1)
                self.assertEqual(hp[3], actual["max_hp"])
        self.assertNotIn("territory_stat_bonuses", original)

    def test_policy_has_no_missing_database_fallback(self):
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        with self.assertRaisesRegex(ValueError, "health policy"):
            territory_bonuses.control_health_policy(db)
        db.execute.return_value.fetchone.return_value = {
            "value": {"schema_version": 1, "states": {"1915": 1, "1916": 2, "1917": -1}}
        }
        self.assertEqual(territory_bonuses.control_health_policy(db)["1915"], 1)

    def test_health_follows_each_native_satisfaction_state(self):
        policy = {"1915": 1, "1916": 2, "1917": -1}
        for state, value in policy.items():
            self.assertEqual(
                territory_bonuses.stat_bonuses(
                    {"state_id": int(state), "effects": []}, health_policy=policy
                ),
                {1: value},
            )
        self.assertEqual(territory_bonuses.stat_bonuses(None, health_policy=policy), {})

    def test_attached_actor_enters_combat_with_matching_owned_maximum(self):
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_actor_snapshot import build_player_snapshot

        original = equipment_stats.effective_character(self.character())
        baseline = original["max_hp"]
        policy = {"1915": 1, "1916": 2, "1917": -1}
        for state, delta in ((1915, 1), (1916, 2), (1917, -1), (None, 0)):
            region = None if state is None else {"state_id": state, "effects": []}
            with self.subTest(state=state), patch.object(
                territory_bonuses, "current_region", return_value=region
            ), patch.object(
                territory_bonuses, "control_health_policy", return_value=policy
            ):
                attached = territory_bonuses.attach_character(object(), original)
                self.assertEqual(attached["max_hp"], baseline + delta)
                self.assertEqual(attached["hp"], original["hp"])
                actor = Actor(
                    1,
                    0,
                    (1, 2, 0),
                    attached["hp"],
                    6,
                    3,
                    0,
                    6,
                    owner_id=1,
                    controlled=True,
                    max_hp=attached["max_hp"],
                )
                snapshot = build_player_snapshot(
                    attached, actor, wp_current=6, wp_maximum=6, running_effects=()
                )
                snapshot.install(actor)
                self.assertEqual(actor.max_hp, baseline + delta)
                self.assertEqual(
                    territory_bonuses.attach_character(object(), attached)["max_hp"],
                    baseline + delta,
                )
        self.assertNotIn("territory_stat_bonuses", original)
