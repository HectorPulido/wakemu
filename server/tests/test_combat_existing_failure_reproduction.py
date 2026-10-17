"""Replay an observed historical armor assertion divergence, not certify correctness."""
import copy
import os
import random
import struct
import unittest
from unittest.mock import patch

from test_combat_armor_pipeline import native
from wakfu_server.combat_event_replay import NativeEventReplay
from wakfu_server.combat_incident_capture import incident_scope
from wakfu_server.combat_incident_replay import RECIPE, replay_runtime_incident
from wakfu_server.combat_reproduction import controlled_environment, ReproductionClock
from wakfu_server.combat_reproduction_actions import (
    AUTHORITY_RECIPE,
    execute,
    prepare_context,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import prepare_server_initialization
from wakfu_server.spells import encode_deck


HISTORICAL_EXPECTED_CHANNELS = [10, 1, 20, 2, 30, 3, 40, 4]
OBSERVED_CHANNELS = [10, 1, 11, 11, 20, 2, 21, 21, 30, 3, 31, 31, 40, 4, 41, 41]


class ExistingFailureReproductionTests(unittest.TestCase):
    def fixture(self):
        # Preserve the original armor pipeline's native fixture, legal deck,
        # initialization, resources and target. No injected runner/listener.
        origin, enemy = (-8, -7, -1), (-7, -7, -1)
        terrain = native.bounded_arena(
            native.map_geometry(1134), origin, [enemy], radius=12
        )
        character, monster, fight = native.fixture(
            11, 60, enemy, terrain, origin, monster_reference=3646, monster_level=12
        )
        deck = encode_deck([5033], [5053])
        rng = random.Random(0)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        while fight.current.id != 7:
            fight.end_server_turn(fight.current.id, fight.turn_id)
        runtime = RuntimeMessages(fight)
        runtime.action_id = 1
        inputs = dict(
            authority_recipe=AUTHORITY_RECIPE,
            character=character,
            monsters={-7: monster},
            deck_blob=deck,
            player_characters={7: character},
            deck_blobs={7: deck},
            map_id=1134,
            native_events=True,
            area_callbacks=True,
        )
        action = dict(
            type="player_spell",
            owner_id=3,
            critical=False,
            body=struct.pack(">qqiih", 7, (7 << 32) | 5033, *fight.actors[-7].position),
        )
        return runtime, inputs, action, rng

    def test_observed_armor_phase_divergence_captures_and_replays_without_gameplay_patch(
        self,
    ):
        runtime, inputs, action, rng = self.fixture()
        clocks = dict(wall_time_ns=1700000000000000000, monotonic_ns=123000000000)
        policies = {
            "WAKFU_NATIVE_AREA_CALLBACKS": "1",
            "WAKFU_NATIVE_GRANTED_CAST": "0",
        }
        clock = ReproductionClock(clocks)
        channels = []
        original = NativeEventReplay.__call__

        def observe(instance, event, **kwargs):
            # This spy forwards the exact original source and return value;
            # it neither adds events nor mutates damage, armor or listeners.
            if getattr(event, "effect_action_id", None) == 1013:
                channels.append(event.channel)
            return original(instance, event, **kwargs)

        with controlled_environment(clocks, policies), patch.dict(
            os.environ,
            {
                "WAKFU_COMBAT_INCIDENT_DIR": "/private/unused",
                "WAKFU_COMBAT_INCIDENT_MODE": "all",
            },
        ), patch(
            "wakfu_server.combat_incident_capture._enqueue"
        ) as enqueue, patch.object(
            NativeEventReplay, "__call__", observe
        ):
            context = prepare_context(runtime, action, inputs, rng, clock)
            with incident_scope(
                runtime,
                action,
                dict(inputs, authority_recipe="observed-live-server-v1"),
                recipients=(3,),
            ) as capture:
                result = execute(
                    runtime, action, inputs, rng, clock, prepared_context=context
                )
                capture.packets(result["packets"])
        receipt = enqueue.call_args.args[1]
        receipt[
            "origin"
        ] = "historical-armor-assertion-native-fixture-not-live-client-incident"
        self.assertEqual(channels, OBSERVED_CHANNELS)
        # Matching this divergence is evidence of reproduction only. The
        # historical expected channels are not asserted as gameplay truth.
        self.assertNotEqual(channels, HISTORICAL_EXPECTED_CHANNELS)
        self.assertEqual(receipt["status"], "accepted")
        before = copy.deepcopy(receipt)
        channels.clear()
        with patch.object(NativeEventReplay, "__call__", observe):
            replayed = replay_runtime_incident(receipt, provider_recipe=RECIPE)
        self.assertTrue(replayed["operation_matches"], replayed["differences"])
        self.assertTrue(replayed["rng_ownership_known"])
        self.assertEqual(channels, OBSERVED_CHANNELS)
        self.assertFalse(replayed["shared_delivery_qualified"])
        self.assertFalse(replayed.get("bootstrap_qualified", False))
        self.assertEqual(receipt, before)


if __name__ == "__main__":
    unittest.main()
