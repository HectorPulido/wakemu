"""Fresh area listener serialization follows installed eYQ, before calculation."""
from pathlib import Path
import unittest
from test_combat_subscription_runners import fields
from wakfu_server.combat_subscription_runners import deferred_payload


class DeferredArea314Tests(unittest.TestCase):
    def test_registered_native_prototype_fresh_wire_matches(self):
        rows = (
            (
                Path(__file__).parent
                / "fixtures/native_combat_oracles"
                / "deferred314-wire-oracle.txt"
            )
            .read_text()
            .splitlines()
        )
        oracle = [
            bytes.fromhex(row.split(" proto=")[1]) for row in rows if " proto=" in row
        ]
        self.assertEqual(len(oracle), 2)
        self.assertEqual(oracle[0], oracle[1])
        actual = deferred_payload(
            family=314,
            uid=901,
            base_uid=800,
            generic_effect=350552,
            caster_id=7,
            target_id=-7,
            cell=(4, 5, 0),
            container_type=None,
            container_id=None,
            timing_payload=bytes.fromhex(
                "08001a0f080010ffffffffffffffffff01180020ffffffffffffffffff01"
            ),
        )
        got, wanted = fields(actual), fields(oracle[1])
        self.assertEqual(fields(got.pop(11)), fields(wanted.pop(11)))
        self.assertEqual(got, wanted)

    def test_actual_listener_waits_for1001_then_creates_owned_area_and_removes(self):
        import json
        from copy import deepcopy
        from wakfu_server.combat_effect_area import NativeEffectAreaHandler
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_event_replay import NativeExternalEvent
        import test_combat_event_replay as replay_fixture

        fixture = replay_fixture.NativeEventReplayTests()
        fixture.setUpClass()
        fixture.fixture = deepcopy(fixture.fixture)
        for row in fixture.fixture["retained_metadata"]["effects"].values():
            row["event_execution_count_per_level"] = 0.0
        fixture.setUp()
        fight = fixture.fight
        fight.native_owned_group_effects.clear()
        fight.native_retained_records.clear()
        effect = json.loads(
            (
                Path(__file__).parent
                / "fixtures/next_central_recovery"
                / "actual111558.json"
            ).read_text()
        )
        metadata = json.loads(
            (
                Path(__file__).parent
                / "fixtures/next_central_recovery"
                / "actual111558-metadata.json"
            ).read_text()
        )
        fixture.effects["111558"] = effect
        fixture.retention.metadata["effects"]["111558"] = metadata
        handler = NativeEffectAreaHandler(
            fight,
            fixture.packets,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda *_: StatExecutionContext(
                True, True, None, True, b"\x08\x00"
            ),
            container=fixture.retention.container,
        )
        handler.on_created = lambda row: None
        from unittest.mock import patch

        owners = json.loads(
            (
                Path(__file__).parent
                / "fixtures/next_central_recovery"
                / "actual314-owner.json"
            ).read_text()
        )
        owner_patch = patch(
            "wakfu_server.combat_delivery_owners.owner_catalog", return_value=owners
        )
        owner_patch.start()
        self.addCleanup(owner_patch.stop)
        fixture.dispatcher.handlers = {314: fixture.retention.wrap(handler)}
        target = fight.actors[7]
        fixture.dispatcher.execute(EffectInvocation(111558, 1, 7, 7, target.position))
        self.assertFalse(fight.native_effect_areas)
        self.assertEqual(len(fight.native_owned_group_effects), 1)
        fixture.replay(NativeExternalEvent(7, (1000,), 6), authority=fixture.authority)
        self.assertFalse(fight.native_effect_areas)
        fixture.replay(NativeExternalEvent(7, (1001,), 6), authority=fixture.authority)
        self.assertEqual(len(fight.native_effect_areas), 1)
        self.assertEqual(len(fight.native_owned_area_effects), 1)
        self.assertEqual(
            next(iter(fight.native_effect_areas.values()))["reference"], 669
        )
        area_uids = tuple(fight.native_owned_area_effects)
        fixture.retention.removal(fixture.retention.view()).remove(area_uids)
        fixture.retention.synchronize()
        self.assertFalse(fight.native_effect_areas)
        self.assertFalse(fight.native_owned_area_effects)
        self.assertFalse(set(area_uids) & set(fight.native_retained_records))
