"""Read-only presentation must not recreate spatially retired Qf creators."""
from copy import deepcopy
import unittest

from test_combat_spectator_snapshot import shared_fixture
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_runtime import group_payload
from wakfu_server.combat_spectator_snapshot import _retained_carrier_packets
from wakfu_server.combat_private_target_aura import SOURCE
from wakfu_server.combat_effect_removal import _identity_fields
import struct


class RetiredAreaSnapshotTests(unittest.TestCase):
    def fixture(self):
        fight, _ = shared_fixture()
        for uid, area_uid in ((11, 101), (12, 102), (13, 103), (14, 104)):
            private = uid == 14
            family = 338 if private else 315
            target = 5 if private else None
            payload = group_payload(
                uid=uid,
                base_uid=uid,
                generic_effect=1000 + uid,
                caster_id=5,
                target_id=target,
                cell=(1, 0, 0),
                container_type=None,
                container_id=None,
                timing_payload=b"\x00",
            )
            row = dict(
                uid=uid,
                area_uid=area_uid,
                effect_class=family,
                target_id=target,
                caster_id=5,
                state_uid=None,
                payload=payload.hex(),
                keep_after=uid == 13,
                executed=True,
            )
            if private:
                row.update(
                    native_manager_source="eYJ.PK.owner_on_caster",
                    native_manager_id=5,
                    native_private_area=dict(
                        uid=area_uid,
                        reference=1474,
                        level=1,
                        anchor_id=5,
                        owner_id=5,
                        source=SOURCE,
                        native_area_contract="faN",
                        registered=False,
                        creation_callbacks_executed=False,
                    ),
                )
            fight.native_owned_area_effects[uid] = row
            record = RetainedEffect(uid, target, family, 1000 + uid, manager_id=5)
            fight.native_retained_order.append(uid)
            fight.native_retained_records[uid] = vars(record)
        fight.native_effect_areas[101] = dict(uid=101)
        fight.native_retained_tracking = True
        return fight

    def test_reconnect_shared_stream_keeps_active_and_private_areas_without_resurrection(
        self,
    ):
        fight = self.fixture()

        def authority():
            return (
                fight.native_effect_areas,
                fight.native_owned_area_effects,
                fight.native_retained_records,
                fight.native_retained_order,
                fight.turn_id,
                fight.sequence,
                {
                    actor.id: (actor.hp, actor.ap, actor.mp)
                    for actor in fight.actors.values()
                },
            )

        before = deepcopy(authority())
        packets = _retained_carrier_packets(fight, 4)
        uids = []
        for opcode, body in packets:
            self.assertEqual(opcode, 12613)
            self.assertEqual(body[12], 0)
            size = struct.unpack_from(">h", body, 17)[0]
            uids.append(_identity_fields(body[19 : 19 + size])[1])
        self.assertEqual(uids, [11, 14])
        self.assertEqual(authority(), before)
        self.assertEqual(set(fight.native_owned_area_effects), {11, 12, 13, 14})

    def test_restoring_registered_spatial_identity_restores_only_its_presentation(self):
        fight = self.fixture()
        fight.native_effect_areas[102] = dict(uid=102)
        packets = _retained_carrier_packets(fight, 4)
        self.assertEqual(len(packets), 3)
        self.assertEqual(fight.native_retained_order, [11, 12, 13, 14])
