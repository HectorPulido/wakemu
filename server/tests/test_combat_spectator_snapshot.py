import copy
import unittest
from types import SimpleNamespace

from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_spectator_snapshot import current_snapshot
from wakfu_server.combat_spectator_wire import decode_spectator_bootstrap
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_wire import arena, topology


def shared_fixture():
    cells = [(0, 0, 0), (1, 0, 0)]
    fight = Fight(
        900,
        [
            Actor(5, 0, cells[0], 60, 6, 3, 100, 1, 1, True),
            Actor(-200, 1, cells[1], 20, 4, 2, 10, 1),
        ],
        set(cells),
        {0: {cells[0]}, 1: {cells[1]}},
    )
    terrain = arena(1134, 7, cells, {0: cells[0], 1: cells[1]})
    shared = SimpleNamespace(
        fight=fight,
        map_id=1134,
        instance_id=7,
        is_duel=False,
        runtime=SimpleNamespace(native_action_id=4),
        join_context={
            "arena": terrain,
            "terrain_effect_id": 378,
            "terrain_instance_id": -300,
            "leaders": {0: 5, 1: -200},
        },
    )
    return fight, shared


def actor_payload(fight, actor):
    return (b"stats:" + str(actor.id).encode(), b"\x00\x00")


class SpectatorSnapshotTests(unittest.TestCase):
    def test_public_world_scope_is_distinct_from_native_arena_identity(self):
        fight, shared = shared_fixture()
        shared.instance_id = 0
        packets = current_snapshot(fight, shared, actor_payload=actor_payload)
        decoded = decode_spectator_bootstrap(packets[0][1])
        self.assertEqual(decoded["myD"], topology(shared.join_context["arena"]))
        self.assertEqual(shared.join_context["arena"]["instance_id"], 7)
        for invalid in (-1, True):
            shared.instance_id = invalid
            with self.assertRaisesRegex(ValueError, "shared location"):
                current_snapshot(fight, shared, actor_payload=actor_payload)

    def test_foreign_map_arena_is_rejected_even_with_valid_world_instance(self):
        fight, shared = shared_fixture()
        shared.instance_id = 0
        shared.join_context["arena"]["map_id"] = 527
        with self.assertRaisesRegex(ValueError, "shared location"):
            current_snapshot(fight, shared, actor_payload=actor_payload)

    def test_placement_snapshot_uses_current_owned_roster_and_topology(self):
        fight, shared = shared_fixture()
        packets = current_snapshot(fight, shared, actor_payload=actor_payload)
        self.assertEqual([opcode for opcode, _ in packets], [12044])
        decoded = decode_spectator_bootstrap(packets[0][1])
        self.assertEqual(decoded["fight_id"], fight.id)
        self.assertEqual(decoded["phase_code"], 1)
        self.assertEqual(
            [row["actor_id"] for row in decoded["participants"]], [5, -200]
        )
        self.assertEqual(decoded["myD"], topology(shared.join_context["arena"]))

    def test_active_snapshot_uses_current_timeline_and_turn_deadline(self):
        fight, shared = shared_fixture()
        fight.ready(1)
        packet = current_snapshot(
            fight, shared, actor_payload=actor_payload, deadline_ms=123456
        )[0]
        decoded = decode_spectator_bootstrap(packet[1])
        self.assertEqual(decoded["phase_code"], 2)
        self.assertEqual(decoded["timeline"]["period"], 3)
        self.assertEqual(decoded["timeline"]["fYZ_entries"], {})
        self.assertEqual(decoded["timeline"]["fZb_entries"], {})
        from wakfu_server.combat_recovery import timeline

        self.assertEqual(decoded["myG"][:15], timeline(fight, deadline_ms=123456)[:15])
        self.assertEqual(decoded["myG"][7:15], (123456).to_bytes(8, "big"))

    def test_active_native_state_and_group_area_carriers_reinstall_without_mutation(
        self,
    ):
        from wakfu_server.combat_subscription_runners import GROUP_SUBSCRIPTION_FAMILIES
        from wakfu_server.combat_retained_runtime import group_payload

        fight, shared = shared_fixture()
        fight.ready(1)
        actor = fight.actors[5]
        state = RunningState(
            uid=77,
            reference=404,
            level=1,
            caster_id=5,
            target_id=5,
            duration=1,
            clock_actor="target",
            tick_at_turn_end=False,
            effect_ids=(),
            realtime_duration=0,
            retained=True,
            timer=None,
            protected=False,
        )
        actor.state_ledger._entries = (state,)
        from wakfu_server.combat_state_carrier import state_carrier_payload

        fight.state_wire_payloads[77] = state_carrier_payload(
            uid=77,
            base_uid=77,
            caster_id=5,
            target_id=5,
            state_id=404,
            level=1,
            native_turn_clock=-1,
            native_realtime_remaining=0,
        ).hex()
        state_record = RetainedEffect(
            77,
            5,
            310,
            -1,
            manager_id=5,
            definition_type=0,
            state_unremovable=False,
            state_dispellable=True,
        )

        group_class = min(GROUP_SUBSCRIPTION_FAMILIES)
        group_uid = 88
        group_payload_bytes = group_payload(
            uid=group_uid,
            base_uid=group_uid,
            generic_effect=123,
            caster_id=5,
            target_id=None,
            cell=(0, 0, 0),
            container_type=None,
            container_id=None,
            timing_payload=b"\x00",
        )
        fight.native_owned_group_effects[group_uid] = dict(
            uid=group_uid,
            target_id=None,
            effect_class=group_class,
            state_uid=None,
            payload=group_payload_bytes.hex(),
        )
        group_record = RetainedEffect(
            group_uid,
            None,
            group_class,
            123,
            manager_id=5,
            definition_type=0,
        )

        area_uid = 89
        area_payload_bytes = group_payload(
            uid=area_uid,
            base_uid=area_uid,
            generic_effect=124,
            caster_id=5,
            target_id=None,
            cell=(1, 0, 0),
            container_type=None,
            container_id=None,
            timing_payload=b"\x00",
        )
        fight.native_owned_area_effects[area_uid] = dict(
            uid=area_uid,
            area_uid=99,
            effect_class=315,
            target_id=None,
            caster_id=5,
            state_uid=None,
            payload=area_payload_bytes.hex(),
            keep_after=True,
            executed=True,
        )
        area_record = RetainedEffect(
            area_uid,
            None,
            315,
            124,
            manager_id=5,
            definition_type=0,
        )
        fight.native_retained_tracking = True
        fight.native_retained_order[:] = [77, group_uid, area_uid]
        fight.native_retained_records = {
            record.uid: vars(record)
            for record in (state_record, group_record, area_record)
        }

        before = copy.deepcopy(
            (
                fight.state_wire_payloads,
                fight.native_owned_group_effects,
                fight.native_owned_area_effects,
                fight.native_retained_records,
                fight.native_retained_order,
                fight.sequence,
                shared.runtime.native_action_id,
            )
        )
        packets = current_snapshot(
            fight, shared, actor_payload=actor_payload, deadline_ms=123456
        )
        self.assertEqual(
            [opcode for opcode, _ in packets], [12044, 12613, 12613, 12613]
        )
        self.assertEqual(
            before,
            (
                fight.state_wire_payloads,
                fight.native_owned_group_effects,
                fight.native_owned_area_effects,
                fight.native_retained_records,
                fight.native_retained_order,
                fight.sequence,
                shared.runtime.native_action_id,
            ),
        )

    def test_active_snapshot_fails_closed_for_untracked_or_private_effect_state(self):
        fight, shared = shared_fixture()
        fight.ready(1)
        fight.native_retained_tracking = False
        with self.assertRaisesRegex(ValueError, "retained-effect ledger"):
            current_snapshot(
                fight, shared, actor_payload=actor_payload, deadline_ms=123456
            )

        fight.native_retained_tracking = True
        shared.is_duel = True
        with self.assertRaisesRegex(ValueError, "Private duel"):
            current_snapshot(
                fight, shared, actor_payload=actor_payload, deadline_ms=123456
            )


if __name__ == "__main__":
    unittest.main()
