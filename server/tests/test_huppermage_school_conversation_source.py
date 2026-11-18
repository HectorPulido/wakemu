"""Finite School declarations preserve native travel and possession authority."""
import json
from pathlib import Path
import unittest


class HuppermageSchoolConversationSourceTests(unittest.TestCase):
    def test_actual_routes_and_registration_do_not_invent_payments(self):
        root = Path(__file__).resolve().parents[1]
        source = json.loads(
            (
                root
                / "wakfu_server/achievements/conversation_archetypes/huppermage_school_initial_contracts.json"
            ).read_text()
        )
        placements = {p["row"]["reference_id"]: p for p in source["placements"]}
        jang = placements[3934]
        self.assertEqual(jang["interaction_anchor"], dict(x=79, y=46, z=3))
        self.assertEqual(jang["choice_routes"][0]["choice_id"], 8297)
        self.assertFalse(any(b["reference_id"] == 3934 for b in source["bindings"]))
        registrar = placements[3913]
        self.assertEqual(
            (
                registrar["row"]["map_id"],
                registrar["row"]["x"],
                registrar["row"]["y"],
                registrar["row"]["z"],
            ),
            (1018, 1, -3, 0),
        )
        self.assertEqual(
            {(b["choice_id"], b["objective_id"]) for b in source["bindings"]},
            {(8177, 5596), (8182, 5595)},
        )
        self.assertEqual(source["turnins"], [])
        definition = next(d for d in source["definitions"] if d["d"] == 2776)
        self.assertEqual(
            next(o["ckc"] for o in definition["cjJ"] if o["d"] == 5595),
            "IsAchievementObjectiveComplete(5596)",
        )
