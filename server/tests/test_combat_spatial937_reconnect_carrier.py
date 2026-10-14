"""Real family937 retained runner participates in read-only reconnect replay."""
import inspect
import struct
import unittest
from unittest.mock import patch

import test_combat_native_spatial937 as scenario
import test_combat_behind_target_condition as fixtures


class Spatial937ReconnectCarrierTests(unittest.TestCase):
    def test_actual_surviving_spatial_runner_replays_without_gameplay(self):
        from wakfu_server import combat_spectator_snapshot as presentation
        from wakfu_server.fight_checkpoint_store import snapshot

        original = fixtures.BehindTargetConditionTests.fixture
        captured = {}

        def fixture(instance, *args, **kwargs):
            result = original(instance, *args, **kwargs)
            captured["fight"] = result[0]
            return result

        with patch.object(fixtures.BehindTargetConditionTests, "fixture", fixture):
            scenario.CurrentActor937IntegrationTests(
                "test_actual_package_uid_preparation_dispatch_wrapper_and_removal"
            ).test_actual_package_uid_preparation_dispatch_wrapper_and_removal()
        fight = captured["fight"]
        self.assertEqual(set(fight.native_owned_spatial_effects), {778})
        before = snapshot(fight)
        resources = {
            key: (actor.hp, actor.ap, actor.mp) for key, actor in fight.actors.items()
        }

        # Execute the previous helper policy in memory to preserve red proof
        # without reverting a concurrently edited production file.
        prior = inspect.getsource(presentation._retained_carrier_packets)
        prior = prior.replace(
            '        | set(getattr(fight, "native_owned_spatial_effects", {}))\n', ""
        ).replace(
            '        if uid in getattr(fight, "native_owned_spatial_effects", {}):\n'
            '            sources.append(fight.native_owned_spatial_effects[uid].get("payload"))\n',
            "",
        )
        namespace = dict(vars(presentation))
        exec(compile(prior, "<prior-spatial-carrier-policy>", "exec"), namespace)
        with self.assertRaisesRegex(ValueError, "incomplete retained-effect view"):
            namespace["_retained_carrier_packets"](fight, 916)
        for _ in range(2):
            packets = presentation._retained_carrier_packets(fight, 916)
            self.assertEqual(len(packets), 1)
            opcode, body = packets[0]
            self.assertEqual(opcode, 12613)
            self.assertEqual(
                struct.unpack_from(">iiiBi", body), (fight.id, 916, -1, 0, 937)
            )
            from wakfu_server.combat_effect_removal import _identity_fields

            fields = _identity_fields(body[19:])
            self.assertEqual(fields[1], 778)
            self.assertEqual(
                fields[7],
                fight.native_retained_records[778]["target_id"] & ((1 << 64) - 1),
            )
            self.assertEqual(snapshot(fight), before)
            self.assertEqual(
                {
                    key: (actor.hp, actor.ap, actor.mp)
                    for key, actor in fight.actors.items()
                },
                resources,
            )
