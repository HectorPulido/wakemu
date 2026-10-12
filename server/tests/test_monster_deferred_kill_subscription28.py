"""Native eXc listeners retain fresh wire and execute only on matched events."""
import unittest
from copy import deepcopy

import test_combat_event_replay as replay_fixture
import test_combat_kill as kill_fixture
from test_combat_subscription_runners import fields
from wakfu_server.combat_subscription_runners import deferred_payload
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_event_replay import NativeExternalEvent


class DeferredKillSubscriptionTests(unittest.TestCase):
    def test_installed_java_fresh_excc_payload(self):
        # ProbeNativeDeferredRunner28 invokes the installed eXc constructor/bca.
        expected = bytes.fromhex(
            "08850710a00618d8b21520002a06080410051800300738f9ffffffffffffffff01"
            "5a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff011800"
            "20ffffffffffffffffff012800"
        )
        actual = deferred_payload(
            family=28,
            uid=901,
            base_uid=800,
            generic_effect=350552,
            caster_id=7,
            target_id=-7,
            cell=(4, 5, 0),
            timing_payload=bytes.fromhex(
                "08001a0f080010ffffffffffffffffff01180020ffffffffffffffffff01"
            ),
            container_type=None,
            container_id=None,
        )
        got, wanted = fields(actual), fields(expected)
        self.assertEqual(fields(got.pop(11)), fields(wanted.pop(11)))
        self.assertEqual(got, wanted)

    def test_central_registration_and_real_replay_defer_native_kill(self):
        # Reuse sealed replay metadata/container fixture with an explicit eXc
        # definition. This tests the generic engine, not qualification of90788.
        fixture = replay_fixture.NativeEventReplayTests()
        fixture.setUpClass()
        fixture.fixture = deepcopy(fixture.fixture)
        for row in fixture.fixture["retained_metadata"]["effects"].values():
            row["event_execution_count_per_level"] = 0.0
        fixture.setUp()
        fight = fixture.fight
        fight.native_owned_group_effects.clear()
        fight.native_retained_records.clear()
        effect = fixture.effects["308265"]
        effect.update(effect_class=28, parameter_count=0, parameters=[], criteria="")
        effect["target_masks"] = [[], [], [], [], [], [192], []]
        metadata = fixture.retention.metadata["effects"]["308265"]
        metadata.update(
            effect_class=28,
            parameters=[],
            event_reverse_subscription=False,
            event_global_subscription=False,
        )
        native_fixture = kill_fixture.NativeKillTests()
        _, template, _, _, handler, _, _ = native_fixture.fixture()
        target = fight.actors[7]
        for name in (
            "effect_stats",
            "effect_minima",
            "effect_maxima",
            "effect_base_minima",
            "effect_base_maxima",
            "effect_percentages",
            "effect_frozen",
        ):
            setattr(target, name, deepcopy(getattr(template, name)))
        target.max_hp = 100
        target.hp = 80
        handler.fight = fight
        handler.packets = fixture.packets
        fixture.dispatcher.handlers = {28: handler}
        fixture.dispatcher.execute(EffectInvocation(308265, 1, 7, 7, target.position))
        self.assertEqual(target.hp, 80)
        self.assertEqual(len(fight.native_owned_group_effects), 1)
        fixture.replay(NativeExternalEvent(7, (191,), 6), authority=fixture.authority)
        self.assertEqual(target.hp, 80)
        fixture.replay(NativeExternalEvent(7, (192,), 6), authority=fixture.authority)
        self.assertEqual(target.hp, 0)


if __name__ == "__main__":
    unittest.main()
