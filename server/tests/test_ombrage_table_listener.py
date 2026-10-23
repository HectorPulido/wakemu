"""Boss-owned listeners retain native constructor authority and table journals."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_encounter_table_listeners as listeners
from wakfu_server.combat_npc_phase_controller import deliver_npc_table_phase


POLICY = dict(
    policy="test-ombrage-table-listener",
    authority="explicit-test-data",
    map_id=1229,
    monster_references=[4770],
    catalog_revision="fixture",
    boss_reference=4770,
    boss_constructor_state=5649,
    owner_reference=4770,
    owner_constructor_state=5659,
    effect_reference=266725,
    event_id=1003,
    channel=61,
    timing="owned_boss_table_start",
)


class OmbrageTableListenerTests(unittest.TestCase):
    def test_owned_boss_once_per_table_scope_constructor_uid_and_checkpoint(self):
        boss = SimpleNamespace(
            id=-7,
            controlled=False,
            hp=100,
            state_ledger=SimpleNamespace(
                entries=(SimpleNamespace(uid=101, reference=5659, target_id=-7),)
            ),
        )
        player = SimpleNamespace(id=7, controlled=True, hp=100)
        fight = SimpleNamespace(
            phase="active",
            current=boss,
            actors={-7: boss, 7: player},
            native_start_event_delivered=True,
            native_table_turn=1,
            native_encounter_table_listener_policy=deepcopy(POLICY),
            native_npc_initialization_receipts={
                -7: dict(
                    ref=4770, initialized=True, resolved_states=[dict(state_id=5649)]
                )
            },
            native_owned_group_effects={31: dict(invocation=dict(state_uid=101))},
        )
        entries = (
            SimpleNamespace(uid=31, generic_effect=266725, manager_id=-7),
            SimpleNamespace(uid=32, generic_effect=266725, manager_id=7),
            SimpleNamespace(uid=33, generic_effect=266402, manager_id=-7),
        )
        calls = []
        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(
                fight=fight, view=lambda: SimpleNamespace(entries=entries)
            ),
            native_clone_authority=object(),
            replay_event=lambda event, **kwargs: calls.append((event, kwargs))
            or ("deadline",),
        )
        with patch.object(
            listeners, "_version", side_effect=lambda policy: deepcopy(POLICY)
        ):
            # Opening1003 is already native; the reconstruction starts at table2.
            self.assertEqual(deliver_npc_table_phase(dispatcher, actor_id=-7), ())
            fight.native_table_turn = 2
            self.assertEqual(
                deliver_npc_table_phase(dispatcher, actor_id=-7), ("deadline",)
            )
            event, arguments = calls[0]
            self.assertEqual(
                (event.manager_actor_id, event.event_ids, event.channel),
                (-7, (1003,), 61),
            )
            self.assertEqual(arguments["eligible_uids"], frozenset((31,)))
            self.assertIs(arguments["authority"], dispatcher.native_clone_authority)
            self.assertFalse(hasattr(boss, "native_summon_source"))
            self.assertFalse(hasattr(fight, "boss_score_profile"))
            fight.native_npc_phase_deliveries = json.loads(
                json.dumps(fight.native_npc_phase_deliveries)
            )
            self.assertEqual(deliver_npc_table_phase(dispatcher, actor_id=-7), ())
            self.assertEqual(len(calls), 1)
            fight.current = player
            self.assertEqual(deliver_npc_table_phase(dispatcher, actor_id=7), ())
            fight.current = boss
            fight.native_table_turn = 3
            receipt = fight.native_npc_initialization_receipts[-7]
            receipt["resolved_states"] = []
            with self.assertRaisesRegex(ValueError, "constructor receipt"):
                deliver_npc_table_phase(dispatcher, actor_id=-7)
            receipt["resolved_states"] = [dict(state_id=5649)]
            fight.native_owned_group_effects[31]["invocation"]["state_uid"] = 999
            with self.assertRaisesRegex(ValueError, "does not belong"):
                deliver_npc_table_phase(dispatcher, actor_id=-7)
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(fight.native_npc_phase_deliveries), 1)
            fight.native_owned_group_effects[31]["invocation"]["state_uid"] = 101
            self.assertEqual(
                deliver_npc_table_phase(dispatcher, actor_id=-7), ("deadline",)
            )
            self.assertEqual(len(calls), 2)
            # The original deadline may remove its timer state/listener while
            # leaving the boss alive. Future tables must not recreate it.
            fight.native_table_turn = 4
            boss.state_ledger.entries = ()
            with self.assertRaisesRegex(ValueError, "constructor state"):
                deliver_npc_table_phase(dispatcher, actor_id=-7)
            entries = ()
            self.assertEqual(deliver_npc_table_phase(dispatcher, actor_id=-7), ())
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(fight.native_npc_phase_deliveries), 3)
            del fight.native_encounter_table_listener_policy
            fight.native_table_turn = 5
            self.assertEqual(deliver_npc_table_phase(dispatcher, actor_id=-7), ())
            self.assertEqual(len(calls), 2)  # Legacy/ordinary fights infer no policy.

        # No policy is a frozen admission decision, not a reason to opt into a
        # newly published pointer when that same fight is rebound later.
        fresh = SimpleNamespace()
        roles = SimpleNamespace(map_id=1229, monster_references=(4770,))
        with patch.object(
            listeners,
            "freeze_table_listener_policy",
            side_effect=(None, deepcopy(POLICY)),
        ) as active:
            self.assertIsNone(
                listeners.freeze_encounter_table_listener_policy(fresh, roles=roles)
            )
            self.assertTrue(hasattr(fresh, "native_encounter_table_listener_policy"))
            self.assertIsNone(
                listeners.freeze_encounter_table_listener_policy(fresh, roles=roles)
            )
            self.assertEqual(active.call_count, 1)
            self.assertIsNone(listeners.frozen_table_listener_policy(fresh))
            fresh.boss_score_profile = dict(table_listener_policy=deepcopy(POLICY))
            with self.assertRaisesRegex(ValueError, "differs from score"):
                listeners.frozen_table_listener_policy(fresh)
