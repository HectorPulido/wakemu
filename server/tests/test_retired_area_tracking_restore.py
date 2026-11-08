"""Cold clone/decode binds current root objects without retaining old aliases."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_retained_collections import bound_collections
from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_owned_container_row import OwnedContainerRow
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_server import combat_state_managers as managers


class RetiredAreaColdRestoreTests(unittest.TestCase):
    def test_real_fight_clone_and_codec_rebind_roots_and_preserve_actual_aliases(self):
        first = Actor(1, 0, (0, 0, 0), 10, 6, 3, 1, 1)
        second = Actor(2, 1, (1, 0, 0), 10, 6, 3, 1, 1)
        fight = Fight(
            7, [first, second], {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        for uid in (101, 102, 103):
            fight.native_retired_area_managers[uid] = OwnedAreaRow(uid=uid)
        descriptor = OwnedContainerRow(uid=700, target_id=101, caster_id=1)
        source = OwnedStateSourceRow(uid=900, state_uid=700)
        fight.native_owned_state_containers[700] = descriptor
        fight.owned_stat_effects[900] = source
        owner = bound_collections(vars(fight))
        owner.records.install_owned(900, {"uid": 900, "manager_id": 1})
        owner.order.append(900)
        first.state_ledger._entries = (
            RunningState(950, 1, 1, 102, 1, -1, "target", False, (), 0, True, None),
        )
        fight.descriptor_alias = descriptor
        fight.source_alias = source
        fight.area_alias = fight.native_retired_area_managers[101]
        restored = decode_state(json.loads(json.dumps(encode_state(fight))))
        for clone in (deepcopy(fight), restored):
            with self.subTest(restored=clone is restored):
                cloned_owner = bound_collections(vars(clone))
                self.assertIs(
                    cloned_owner.retired_tracking.facts,
                    clone.native_owned_state_containers,
                )
                self.assertIs(
                    clone.descriptor_alias, clone.native_owned_state_containers[700]
                )
                self.assertIs(clone.source_alias, clone.owned_stat_effects[900])
                self.assertIs(clone.area_alias, clone.native_retired_area_managers[101])
                self.assertIsNot(clone.descriptor_alias, descriptor)
                with patch.object(
                    managers,
                    "_retained_manager_users",
                    side_effect=AssertionError("global records"),
                ):
                    managers.prune_retired_state_managers(clone)
                    self.assertEqual(
                        set(clone.native_retired_area_managers), {101, 102}
                    )
                    del clone.owned_stat_effects[900]
                    managers.prune_retired_state_managers(clone)
                    self.assertEqual(set(clone.native_retired_area_managers), {102})
                    clone.actors[1].state_ledger._entries = ()
                    managers.prune_retired_state_managers(clone)
                    self.assertEqual(clone.native_retired_area_managers, {})
        self.assertEqual(set(fight.native_retired_area_managers), {101, 102, 103})
        self.assertIs(fight.owned_stat_effects[900], source)
        self.assertEqual(len(first.state_ledger.entries), 1)


if __name__ == "__main__":
    unittest.main()
