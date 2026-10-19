"""Actual non-retained dial hours in both native bootstrap roles."""
import struct
import unittest
from types import SimpleNamespace

import test_xelor_runtime_pipeline as helpers


def actual_bootstraps(data):
    from wakfu_server.breed_resources import live_wp
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
    from wakfu_server.combat_summon_stats import registered_summon_stats
    from wakfu_server.combat_remote_effects import active_actor_effects
    from wakfu_server.combat_reconnect_snapshot import owned_snapshot
    from wakfu_server.combat_spectator_snapshot import current_snapshot
    from wakfu_server.combat_spectator_wire import decode_spectator_bootstrap
    from wakfu_server.combat_wire import decode_bootstrap

    fight = data[2]

    def actor_payload(current, actor, session=None):
        if getattr(actor, "native_summon_source", None) is not None:
            stats = registered_summon_stats(actor, current, 1134)
        else:
            wp, maximum = live_wp(current, actor.id)
            if actor.controlled:
                stats = actual_actor_stats(
                    data[0],
                    actor,
                    current.id,
                    fight=current,
                    wp_current=wp,
                    wp_maximum=maximum,
                )
            else:
                monster = dict(
                    data[1],
                    level=actor.effective_level,
                    x=actor.position[0],
                    y=actor.position[1],
                    z=actor.position[2],
                )
                stats = actual_monster_actor_stats(
                    monster,
                    actor,
                    current.id,
                    fight=current,
                    wp_current=wp,
                    wp_maximum=maximum,
                )
        return stats, active_actor_effects(current, actor.id)

    qi = fight.native_qi_snapshot
    arena = dict(
        map_id=1134,
        instance_id=7,
        x=qi["x"],
        y=qi["y"],
        width=qi["width"],
        height=qi["height"],
        min_z=min(cell[2] for cell in fight.walkable),
        max_z=max(cell[2] for cell in fight.walkable),
        cell_masks=qi["cell_masks"],
        team_values=[],
    )
    shared = SimpleNamespace(
        map_id=1134,
        instance_id=0,
        is_duel=False,
        reconnect_remaining_turn_seconds=None,
        join_context=dict(
            arena=arena,
            terrain_effect_id=1,
            terrain_instance_id=0,
            leaders={0: 7, 1: -7},
        ),
        runtime=SimpleNamespace(
            native_action_id=30, turn_deadline=None, awaiting_ack=None, clock=lambda: 0
        ),
    )
    packets = {
        "spectator": current_snapshot(
            fight, shared, actor_payload=actor_payload, deadline_ms=1
        ),
        "owned": owned_snapshot(
            fight,
            shared,
            SimpleNamespace(account_id=3, character_id=7),
            actor_payload=actor_payload,
        ),
    }
    return {
        "spectator": decode_spectator_bootstrap(
            next(payload for opcode, payload in packets["spectator"] if opcode == 12044)
        ),
        "owned": decode_bootstrap(
            next(payload for opcode, payload in packets["owned"] if opcode == 12847)
        ),
    }


class XelorHourSnapshotTests(unittest.TestCase):
    maxDiff = None

    def test_actual_standard_hours_survive_both_bootstraps_without_marker_duplication(
        self,
    ):
        from wakfu_server.combat_spectator_snapshot import _retained_carrier_packets
        from wakfu_server.combat_remote_effects import decode_remote_effects
        from wakfu_server.combat_effect_removal import _identity_fields

        helper = helpers.XelorRuntimePipelineTests()
        data = helper.fixture(target_distance=5)
        dial = helper.dial(data)
        data = helper.adopt(data, dial.fight)
        fight = data[2]
        before = helpers.snapshot(fight)
        standards = {
            uid: row
            for uid, row in fight.native_effect_areas.items()
            if row.get("owner_id") == 7 and 1546 <= row["reference"] <= 1557
        }
        self.assertEqual(len(standards), 12)
        creator_ids = {row["effect_uid"] for row in standards.values()}
        self.assertTrue(creator_ids.isdisjoint(fight.native_owned_area_effects))
        self.assertTrue(creator_ids.isdisjoint(fight.native_retained_records))
        markers = {
            uid: row
            for uid, row in fight.native_effect_areas.items()
            if row.get("owner_id") == 7 and row["reference"] == 1558
        }
        self.assertEqual(len(markers), 1)
        rehydration = {}
        _retained_carrier_packets(fight, action_id=30, area_rehydration=rehydration)
        self.assertTrue(
            {row["effect_uid"] for row in markers.values()} <= set(rehydration)
        )
        bootstraps = actual_bootstraps(data)
        observed = {}
        for role, bootstrap in bootstraps.items():
            sections = {}
            duplicates = []
            for section in bootstrap["myK"]:
                if len(section) < 41:
                    continue
                reference, uid = struct.unpack_from(">qq", section)
                if uid in standards:
                    if uid in sections:
                        duplicates.append(uid)
                    sections[uid] = section
                    self.assertEqual(reference, standards[uid]["reference"])
                    self.assertEqual(section[41:], b"\x00\x00")
                self.assertNotIn(
                    uid,
                    markers,
                    "retained current marker must not get a second myK constructor",
                )
            owner = next(
                row for row in bootstrap["participants"] if row["actor_id"] == 7
            )
            retained_uids = {
                _identity_fields(row.payload, integer_fields=(1,)).get(1)
                for row in decode_remote_effects(owner["myF"])
            }
            self.assertTrue(creator_ids.isdisjoint(retained_uids))
            observed[role] = dict(
                missing=sorted(set(standards) - set(sections)),
                duplicates=sorted(duplicates),
            )
        self.assertEqual(helpers.snapshot(fight), before)
        self.assertEqual(
            observed,
            {
                "spectator": dict(missing=[], duplicates=[]),
                "owned": dict(missing=[], duplicates=[]),
            },
        )
