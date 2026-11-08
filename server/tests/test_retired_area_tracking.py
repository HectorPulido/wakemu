"""Whole-prune equivalence for actual indexed storage and mutable root aliases."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_owned_container_facts import OwnedContainerFacts
from wakfu_server.combat_owned_container_row import OwnedContainerRow
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server import combat_state_managers as managers


def plain_reference(fight):
    fields = dict(vars(fight))
    for name in (
        "native_effect_areas",
        "native_retired_area_managers",
        "native_retained_records",
        "native_owned_state_containers",
        "owned_stat_effects",
        "native_owned_group_effects",
        "native_owned_area_effects",
        "native_owned_spatial_effects",
    ):
        fields[name] = {uid: dict(row) for uid, row in fields[name].items()}
    fields["actors"] = dict(fight.actors)
    return SimpleNamespace(**fields)


class RetiredAreaTrackingTests(unittest.TestCase):
    def test_mutating_actual_root_aliases_matches_legacy_and_never_scans_population(
        self,
    ):
        owner = RetainedCollections()
        fight = Fight.__new__(Fight)
        fight.actors = owner.actors
        fight.native_retained_records = owner.records
        fight.native_retained_order = owner.order
        for name, rows in (*owner.sources.items(), *owner.area_sources.items()):
            setattr(fight, name, rows)
        fight.native_owned_state_containers = OwnedContainerFacts()
        owner.retired_tracking.bind_facts(fight.native_owned_state_containers)
        owner.actors[1] = Actor(1, 0, (0, 0, 0), 10, 6, 3, 1, 1)
        retired = fight.native_retired_area_managers
        retired[101] = OwnedAreaRow(uid=101, owner_id=102)
        retired[102] = OwnedAreaRow(uid=102, owner_id=101)
        retired[103] = OwnedAreaRow(uid=103, executing=True)
        retired[104] = OwnedAreaRow(uid=104)
        record = owner.records.install_owned(
            900, {"uid": 900, "manager_id": 1, "caster_id": 101}
        )
        owner.order.append(900)
        child = OwnedStateSourceRow(state_uid=700)
        fight.owned_stat_effects[900] = child
        descriptor = OwnedContainerRow(uid=700, target_id=102, caster_id=1)
        fight.native_owned_state_containers[700] = descriptor
        for phase in range(3):
            reference = plain_reference(fight)
            managers.prune_retired_state_managers(reference)
            with patch.object(
                managers,
                "_retained_manager_users",
                side_effect=AssertionError("global records"),
            ):
                with patch.object(
                    managers,
                    "_owned_container_state_users",
                    side_effect=AssertionError("global sources"),
                ):
                    managers.prune_retired_state_managers(fight)
            self.assertEqual(set(retired), set(reference.native_retired_area_managers))
            if phase == 0:
                self.assertEqual(set(retired), {101, 102, 103})
                record["caster_id"] = None
                descriptor["target_id"] = 103
                retired[103]["owner_id"] = 101
            elif phase == 1:
                self.assertEqual(set(retired), {101, 102, 103})
                child["state_uid"] = None
                retired[103]["executing"] = False
        self.assertEqual(retired, {})


if __name__ == "__main__":
    unittest.main()
