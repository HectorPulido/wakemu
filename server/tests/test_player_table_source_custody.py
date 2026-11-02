"""Only genuine boss-descended player state roots receive the round event."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_encounter_player_table_events import player_table_deliveries


class PlayerTableSourceCustodyTests(unittest.TestCase):
    def test_current_successor_uid_retains_source_but_foreign_copies_do_not(self):
        player = SimpleNamespace(
            id=1,
            controlled=True,
            hp=10,
            team=1,
            state_ledger=SimpleNamespace(
                entries=[SimpleNamespace(uid=12, reference=4510, target_id=1)]
            ),
        )
        boss = SimpleNamespace(id=-1, controlled=False, hp=10, team=0)
        fight = SimpleNamespace(
            actors={1: player, -1: boss},
            native_encounter_player_table_policies={
                "test": dict(
                    declaration=dict(player_state=4510, effect_reference=186113),
                    boss_id=-1,
                    constructor_uid=10,
                ),
            },
            native_owned_group_effects={21: dict(invocation=dict(state_uid=12))},
        )
        entry = SimpleNamespace(uid=21, manager_id=1, generic_effect=186113)
        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(
                fight=fight, view=lambda: SimpleNamespace(entries=(entry,))
            )
        )
        ancestry = {
            12: dict(parent_known=True, parent_state_uid=11),
            11: dict(parent_known=True, parent_state_uid=10),
        }
        with patch(
            "wakfu_server.combat_npc_external_event_scope.qualified_npc_uids",
            return_value=frozenset((21,)),
        ), patch(
            "wakfu_server.combat_retained_source_provenance.state_source_provenance",
            return_value=ancestry,
        ):
            self.assertEqual(
                player_table_deliveries(dispatcher),
                [dict(actor_id=1, eligible_uids=[21])],
            )
            original = deepcopy(ancestry)
            # Same source reference without the actual constructor UID is not custody.
            ancestry[11]["parent_state_uid"] = 99
            self.assertEqual(player_table_deliveries(dispatcher), [])
            ancestry.update(deepcopy(original))
            # A class/item origin with unknown parent cannot claim NPC ancestry.
            ancestry[12]["parent_known"] = False
            self.assertEqual(player_table_deliveries(dispatcher), [])
            ancestry.update(deepcopy(original))
            player.state_ledger.entries = []
            self.assertEqual(player_table_deliveries(dispatcher), [])
            player.state_ledger.entries = [
                SimpleNamespace(uid=12, reference=4510, target_id=1)
            ]
            player.controlled = False
            self.assertEqual(player_table_deliveries(dispatcher), [])
            player.controlled = True
            player.hp = 0
            self.assertEqual(player_table_deliveries(dispatcher), [])
