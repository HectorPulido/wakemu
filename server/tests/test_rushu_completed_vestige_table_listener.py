"""Actual Rushu opening and recurring source publication through table six.

This verifies the missing publisher with an owned six-player healing party.
It does not assert terminal victory.
Native predicates, resources, original seed programs and turn ACKs remain live.
"""
from unittest.mock import patch

from postgres_case import PostgresCase


class RushuCompletedVestigeTableListenerTests(PostgresCase):
    def test_actual_constructor_reaches_native_table_six_with_owned_listener(self):
        from test_rushu_native_party_phase_one import RushuNativePartyPhaseOneTests
        from wakfu_server import combat_encounter_table_listeners as listeners
        from wakfu_server.combat_event_replay import NativeEventReplay

        listeners._version.cache_clear()
        self.addCleanup(listeners._version.cache_clear)
        observed = []
        original = NativeEventReplay.__call__

        def observe(replay, event, **kwargs):
            fight = replay.retention.fight
            eligible = kwargs.get("eligible_uids")
            if (
                event.manager_actor_id == -200
                and eligible is not None
                and tuple(event.event_ids) == (1003,)
                and event.channel == 61
            ):
                roots = {
                    entry.generic_effect
                    for entry in replay.retention.view().entries
                    if entry.uid in eligible
                }
                if roots == {325771}:
                    observed.append(
                        (
                            fight.native_table_turn,
                            tuple(event.event_ids),
                            event.channel,
                            roots,
                        )
                    )
            return original(replay, event, **kwargs)

        with patch.object(
            listeners, "_database", return_value=self.store
        ), patch.object(NativeEventReplay, "__call__", observe):
            fight = RushuNativePartyPhaseOneTests._run(self, stop_at_table=6)
            policy = fight.native_encounter_table_listener_policy
            self.assertEqual(policy["effect_reference"], 325771)
            self.assertEqual(policy["owner_constructor_state"], 7000)
            self.assertTrue(
                any(
                    s.reference == 7000 for s in fight.actors[-200].state_ledger.entries
                )
            )
            # Replay observers also see speculative previews. The adopted
            # journal and actual areas below own the exactly-once assertion.
            self.assertEqual(sorted({row[0] for row in observed}), [2, 3, 4, 5, 6])
            journal = list(fight.native_npc_phase_deliveries.values())
            self.assertEqual(
                sorted(row["table_turn"] for row in journal), [2, 3, 4, 5, 6]
            )
            for row in journal:
                self.assertEqual(row["actor_id"], -200)
                self.assertEqual(len(row["owned_listeners"]), 1)
                listener = row["owned_listeners"][0]
                self.assertEqual(listener["policy"], policy["policy"])
                self.assertEqual(listener["owner_id"], -200)
                self.assertEqual(len(listener["eligible_uids"]), 1)
            retired = {
                entry.reference: entry.level
                for entry in fight.actors[-200].state_ledger.entries
                if entry.reference in (7013, 7017, 7018, 7024)
            }
            self.assertEqual(retired, dict.fromkeys((7013, 7017, 7018, 7024), 99))
            completed_cells = {
                tuple(area["cell"])
                for area in fight.native_effect_areas.values()
                if area["reference"] in (1654, 1658, 1659, 1665)
            }
            marker_cells = {
                tuple(area["cell"])
                for area in fight.native_effect_areas.values()
                if area["reference"] == 1687
            }
            self.assertEqual(len(completed_cells), 4)
            self.assertEqual(marker_cells, completed_cells)
            self.assertEqual(
                sum(
                    area["reference"] == 1687
                    for area in fight.native_effect_areas.values()
                ),
                4,
            )
