"""Finite original aMR coverage without creating scene-object identities."""
from copy import deepcopy
import unittest

from wakfu_server.haven_ranch_building_catalog import definitions
from wakfu_server.haven_ranch_building_children import validate_building_children


class RanchBuildingChildrenTests(unittest.TestCase):
    def test_all_original_views_distinguish_empty_and_actual_children(self):
        empty, populated = set(), set()
        for building in definitions().values():
            for mode in building["epD"]:
                for kind, field, selector in ((0, "epP", "epS"), (1, "epQ", "epL")):
                    for choice in mode[field]:
                        args = building, mode["p"], kind, choice[selector]
                        if choice["epM"]["epT"]:
                            populated.add(building["p"])
                            with self.assertRaisesRegex(
                                ValueError, "producer is not qualified"
                            ):
                                validate_building_children(*args)
                        else:
                            empty.add(building["p"])
                            self.assertEqual((), validate_building_children(*args))
        self.assertEqual({58, 63, 140}, populated)
        self.assertEqual(109, len(empty - populated))

    def test_changed_definition_or_missing_selector_is_not_empty(self):
        building = next(iter(definitions().values()))
        changed = deepcopy(building)
        changed["epD"][0]["epP"][0]["epM"].pop("epT")
        with self.assertRaises(ValueError):
            validate_building_children(changed, changed["epF"], 0, 1)
        with self.assertRaises(ValueError):
            validate_building_children(building, building["epF"], 0, 999999)
