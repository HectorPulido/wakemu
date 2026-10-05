import unittest
from copy import deepcopy
from wakfu_server.combat_checkpoint_containers import reconstruct_state_containers
from wakfu_server.combat_stat_effects import owned_effect_payload
from wakfu_server.combat_effects import _integer
from wakfu_server.combat_effect_removal import _identity_fields


class CheckpointContainerTests(unittest.TestCase):
    def fixture(self):
        packed = 3442 << 16 | 20
        payload = (
            owned_effect_payload(
                uid=200,
                base_uid=None,
                generic_effect=150327,
                caster_id=7,
                target_id=7,
                value=0,
            )
            + _integer(9, 3)
            + _integer(10, packed)
        )
        state = dict(uid=100, reference=3442, level=20, caster_id=7, target_id=7)
        return dict(
            actors={"7": dict(state_ledger=dict(entries=[state]))},
            owned_stat_effects={"200": dict(state_uid=100, payload=payload.hex())},
            native_retained_records={
                "200": dict(owner_uid=100, container_type=3, container_id=packed),
                "300": dict(owner_uid=None, container_type=3, container_id=123),
            },
            native_owned_state_containers={},
        )

    def test_legacy_state_reconstructs_from_actual_ledger_and_keeps_area(self):
        data = self.fixture()
        before = deepcopy(data)
        restored = reconstruct_state_containers(data)
        self.assertEqual(data, before)
        self.assertEqual(
            restored["native_retained_records"]["200"]["container_type"], 1
        )
        self.assertEqual(
            restored["native_retained_records"]["300"],
            data["native_retained_records"]["300"],
        )
        fields = _identity_fields(
            bytes.fromhex(restored["owned_stat_effects"]["200"]["payload"]),
            integer_fields=(1, 9, 10),
        )
        self.assertEqual(fields, {1: 200, 9: 1, 10: 3442 << 16 | 20})

    def test_missing_owner_or_mismatching_identity_rejected(self):
        for change in ("missing", "mismatch"):
            data = self.fixture()
            if change == "missing":
                data["actors"]["7"]["state_ledger"]["entries"] = []
            else:
                data["native_retained_records"]["200"]["container_id"] = 123
            with self.assertRaises(ValueError):
                reconstruct_state_containers(data)

    def test_instant_state_snapshot_requires_actual_owned_child(self):
        data = self.fixture()
        state = data["actors"]["7"]["state_ledger"]["entries"].pop()
        data["native_owned_state_containers"]["100"] = state
        self.assertEqual(
            reconstruct_state_containers(data)["native_retained_records"]["200"][
                "container_type"
            ],
            1,
        )
        data["owned_stat_effects"].clear()
        with self.assertRaises(ValueError):
            reconstruct_state_containers(data)
