"""Exercise the real dispatcher settlement callbacks without sockets."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from test_rift_dispatch import helper


class RiftRewardDispatchTests(unittest.TestCase):
    def test_terminal_reward_callback_filters_nonmembers_losers_and_withdrawn(self):
        from wakfu_server import rift_runtime

        rewards = SimpleNamespace(apply=Mock())
        actors = {
            i: SimpleNamespace(id=i, team=team, pve_withdrawn=withdrawn)
            for i, team, withdrawn in (
                (1, 0, False),
                (2, 0, True),
                (3, 1, False),
                (4, 0, False),
            )
        }
        fight = SimpleNamespace(
            id=80,
            winner=0,
            actors=actors,
            native_timeline_round=40,
            rift_wave_state={"instance_id": 90},
        )
        store, db = object(), object()
        settle = helper(
            "settle_rift_rewards",
            {"fight": fight, "owner_characters": {1: {}, 2: {}, 3: {}}, "STORE": store},
        )

        def terminal(connection, instance, fight_id, **options):
            self.assertIs(connection, db)
            self.assertEqual(
                (90, 80, "won", 40),
                (instance, fight_id, options["outcome"], options["turn"]),
            )
            options["apply_rewards"](
                connection, {"members": "frozen"}, {"outcome": "won"}
            )
            return {"receipt": 1}

        with patch.dict(
            sys.modules, {"wakfu_server.maps.rift_rewards": rewards}
        ), patch.object(rift_runtime, "settle", side_effect=terminal):
            self.assertEqual({"receipt": 1}, settle(db))
        rewards.apply.assert_called_once_with(
            db,
            {"members": "frozen"},
            {"outcome": "won"},
            store=store,
            eligible_character_ids=(1,),
        )

    def test_rift_member_loot_settles_before_native_delivery(self):
        calls = []
        rewards = SimpleNamespace(
            delivery=lambda *args: calls.append(("delivery", args))
            or {"loots": [], "packets": []}
        )
        db, store = object(), object()
        loot = helper(
            "shared_loot",
            {
                "fight": SimpleNamespace(rift_wave_state={"instance_id": 90}),
                "STORE": store,
                "settle_rift_rewards": lambda value: calls.append(("settle", value)),
            },
        )
        with patch.dict(sys.modules, {"wakfu_server.maps.rift_rewards": rewards}):
            self.assertEqual(
                {"loots": [], "packets": []}, loot(db, {"character_id": 1}, None)
            )
        self.assertEqual([("settle", db), ("delivery", (db, store, 90, 1))], calls)
