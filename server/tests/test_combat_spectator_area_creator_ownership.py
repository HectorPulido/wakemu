"""A late observer must hydrate each visual eYQ object exactly once."""
from copy import deepcopy
from dataclasses import asdict
import struct
import unittest

from test_combat_spectator_snapshot import shared_fixture
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_runtime import group_payload
from wakfu_server.combat_remote_effects import (
    RemoteRunningEffect,
    encode_remote_effects,
    decode_remote_effects,
)
from wakfu_server.combat_spectator_snapshot import current_snapshot
from wakfu_server.combat_spectator_wire import decode_spectator_bootstrap
from wakfu_server.combat_effect_removal import _identity_fields, running_effect_removal


class SpectatorAreaCreatorOwnershipTests(unittest.TestCase):
    def fixture(self, *, executed=True, live=True, private=False):
        fight, shared = shared_fixture()
        fight.ready(1)
        fight.native_retained_tracking = True
        rows = []
        family = 338 if private else 315
        generic = 318679 if private else 146766
        target = 5 if private else None
        for uid in range(504, 520, 2):
            payload = group_payload(
                uid=uid,
                base_uid=uid,
                generic_effect=generic,
                caster_id=5,
                target_id=target,
                cell=(1, 0, 0),
                container_type=None,
                container_id=None,
                timing_payload=b"\x08\x00",
                initial_value=1649 if private else 837,
            )
            fight.native_owned_area_effects[uid] = dict(
                uid=uid,
                area_uid=uid - 1,
                effect_class=family,
                target_id=target,
                caster_id=5,
                payload=payload.hex(),
                keep_after=False,
                executed=executed,
                native_private_area=None,
            )
            if private:
                # Exact eYJ-only private constructor contract, as exercised by
                # PrivateTargetAuraTests: faN1649 is absent from global Qs.
                from wakfu_server.combat_private_target_aura import SOURCE

                fight.native_owned_area_effects[uid].update(
                    native_manager_source="eYJ.PK.owner_on_caster",
                    native_manager_id=5,
                    native_private_area=dict(
                        uid=uid - 1,
                        reference=1649,
                        level=1,
                        anchor_id=5,
                        owner_id=5,
                        source=SOURCE,
                        native_area_contract="faN",
                        registered=False,
                        creation_callbacks_executed=False,
                    ),
                )
            if live and not private:
                fight.native_effect_areas[uid - 1] = dict(uid=uid - 1)
            entry = RetainedEffect(
                uid, target, family, generic, manager_id=5, definition_type=0
            )
            fight.native_retained_records[uid] = asdict(entry)
            fight.native_retained_order.append(uid)
            rows.append(RemoteRunningEffect(family, payload, 1234))
        other_payload = group_payload(
            uid=1000,
            base_uid=1000,
            generic_effect=124,
            caster_id=5,
            target_id=5,
            cell=(0, 0, 0),
            container_type=None,
            container_id=None,
            timing_payload=b"\x08\x00",
        )
        fight.native_owned_group_effects[1000] = dict(
            uid=1000,
            target_id=5,
            effect_class=400,
            state_uid=None,
            payload=other_payload.hex(),
        )
        fight.native_retained_records[1000] = asdict(
            RetainedEffect(1000, 5, 400, 124, manager_id=5, definition_type=0)
        )
        fight.native_retained_order.append(1000)
        # Preserve unrelated Qf row order, payload, and remote timer exactly.
        rows.insert(3, RemoteRunningEffect(400, other_payload, 5678))
        effects = encode_remote_effects(rows)
        return fight, shared, effects, rows

    def snapshot(self, fight, shared, effects):
        return current_snapshot(
            fight,
            shared,
            deadline_ms=123456,
            actor_payload=lambda current, actor: (
                b"owned-stats",
                effects if actor.id == 5 else bytes(2),
            ),
        )

    def carrier_uids(self, packets):
        found = []
        for opcode, body in packets:
            if opcode != 12613:
                continue
            family, size = struct.unpack_from(">ih", body, 13)
            if family in (315, 338):
                found.append(_identity_fields(body[19 : 19 + size])[1])
        return found

    def test_late_observer_live_cloud_creators_have_one_qf_owner_before_expiry(self):
        fight, shared, effects, rows = self.fixture()
        before = deepcopy(
            (
                fight.native_owned_area_effects,
                fight.native_retained_records,
                fight.native_retained_order,
                fight.native_effect_areas,
                fight.sequence,
                shared.runtime.native_action_id,
            )
        )
        packets = self.snapshot(fight, shared, effects)
        bootstrap = decode_spectator_bootstrap(packets[0][1])
        remote = next(p["myF"] for p in bootstrap["participants"] if p["actor_id"] == 5)
        kept = decode_remote_effects(remote)
        self.assertEqual(kept, (rows[3],))
        self.assertEqual(self.carrier_uids(packets), list(range(504, 520, 2)))
        for uid in self.carrier_uids(packets):
            row = fight.native_owned_area_effects[uid]
            removal = running_effect_removal(
                fight.id,
                99,
                effect_class=315,
                target_id=5,
                uid=uid,
                running_effect_payload=bytes.fromhex(row["payload"]),
            )
            self.assertEqual(
                struct.unpack_from(">qq", removal, len(removal) - 16), (5, uid)
            )
        self.assertEqual(
            (
                fight.native_owned_area_effects,
                fight.native_retained_records,
                fight.native_retained_order,
                fight.native_effect_areas,
                fight.sequence,
                shared.runtime.native_action_id,
            ),
            before,
        )
        # Reentry uses the same one-owner projection without mutating the fight.
        self.assertEqual(self.snapshot(fight, shared, effects), packets)

    def test_retired_creator_remains_remote_without_recreating_removed_area(self):
        fight, shared, effects, _ = self.fixture(live=False)
        packets = self.snapshot(fight, shared, effects)
        bootstrap = decode_spectator_bootstrap(packets[0][1])
        self.assertEqual(
            next(p["myF"] for p in bootstrap["participants"] if p["actor_id"] == 5),
            effects,
        )
        self.assertEqual(self.carrier_uids(packets), [])

    def test_delayed_and_private_creators_keep_existing_remote_contract(self):
        for kwargs in (dict(executed=False), dict(private=True)):
            with self.subTest(**kwargs):
                fight, shared, effects, _ = self.fixture(**kwargs)
                packets = self.snapshot(fight, shared, effects)
                bootstrap = decode_spectator_bootstrap(packets[0][1])
                self.assertEqual(
                    next(
                        p["myF"]
                        for p in bootstrap["participants"]
                        if p["actor_id"] == 5
                    ),
                    effects,
                )
                self.assertEqual(self.carrier_uids(packets), list(range(504, 520, 2)))

    def test_conflicting_remote_family_for_rehydrated_uid_rejects_without_mutation(
        self,
    ):
        fight, shared, _, rows = self.fixture()
        rows[0] = RemoteRunningEffect(
            400, rows[0].payload, rows[0].remaining_milliseconds
        )
        before = deepcopy(fight.native_owned_area_effects)
        with self.assertRaisesRegex(ValueError, "Conflicting spectator area creator"):
            self.snapshot(fight, shared, encode_remote_effects(rows))
        self.assertEqual(fight.native_owned_area_effects, before)

    def test_summon_birth_followup_effect_reset_uses_same_projected_qf(self):
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_wire import decode_actor_state

        fight, shared, effects, rows = self.fixture()
        # Reuse the existing snapshot unit producer contract: birth bytes are
        # opaque to this envelope test, which does not claim native admission.
        summoned = Actor(33, 0, (1, 0, 0), 10, 0, 0, 0, 1)
        fight.actors[summoned.id] = summoned
        fight.native_summon_registrations = {33: {"fight_properties": (114,)}}
        birth = (12613, struct.pack(">i", fight.id) + b"summon")
        fight.native_summon_creation_deliveries = {
            33: dict(opcode=birth[0], payload_hex=birth[1].hex())
        }
        packets = self.snapshot(fight, shared, effects)
        bootstrap = decode_spectator_bootstrap(packets[0][1])
        projected = next(
            p["myF"] for p in bootstrap["participants"] if p["actor_id"] == 5
        )
        reset = next(
            decode_actor_state(opcode, body)["state"]
            for opcode, body in packets
            if opcode == 13912 and decode_actor_state(opcode, body)["actor_id"] == 5
        )
        self.assertEqual(decode_remote_effects(projected), (rows[3],))
        self.assertEqual(reset, projected)
        self.assertEqual(packets.count(birth), 1)
