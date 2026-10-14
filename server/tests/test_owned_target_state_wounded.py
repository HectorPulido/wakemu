"""Source-bound compound recipe and native preview/state clock guards."""
import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from owned_target_state_wounded import (
    target_requirements,
    recipes,
    verify_damage_preview,
    verify_target_state,
)

SOURCE = json.loads(
    (
        Path(__file__).parent
        / "fixtures/owned_target_state_wounded/representative-native-source.json"
    ).read_text()
)


class CompoundTests(unittest.TestCase):
    def discover(self, fixture=None):
        d = copy.deepcopy(SOURCE if fixture is None else fixture)
        return recipes(
            2557,
            127,
            3929,
            d["casting"]["3929"]["cast_criterion_raw"],
            d["abilities"],
            d["document"],
            d["casting"],
            d["definitions"],
        )

    def test_native_owned_3921_not_3923_produces_target131(self):
        r = self.discover()[0]
        self.assertEqual(r["target_state_producer"]["spell_id"], 3921)
        self.assertEqual(
            r["target_state_producer"]["target_state_effect"]["effect_id"], 100248
        )
        self.assertEqual(r["damage_producer"]["spell_id"], 3924)
        self.assertEqual(
            r["native_charge_maximum"] - r["target_state_producer"]["consumed_charge"],
            4,
        )

    def test_no_owned_target_producer_stays_pending(self):
        d = copy.deepcopy(SOURCE)
        d["abilities"] = [a for a in d["abilities"] if a["spell_id"] != 3921]
        self.assertEqual(self.discover(d), [])

    def test_unknown_target_state_selector_or_chance_fails_closed(self):
        for field, value in [
            ("native_target_selector", {"class": "fcE", "mask": 2}),
            ("parameters", [131, 0, 1, 0, 50, 0]),
        ]:
            d = copy.deepcopy(SOURCE)
            d["document"]["effects"]["100248"][field] = value
            self.assertEqual(self.discover(d), [])

    def test_finite_target_clock_not_probability100(self):
        r = self.discover()[0]
        self.assertEqual(r["target_state_duration"], 1)
        d = copy.deepcopy(SOURCE)
        d["definitions"]["131"]["clock_actor"] = "caster"
        self.assertEqual(self.discover(d), [])

    def test_caster_native_cap_must_cover_consumption_and_final_threshold(self):
        d = copy.deepcopy(SOURCE)
        d["definitions"]["2071"]["maximum_level"] = 5
        self.assertEqual(self.discover(d), [])

    def test_required_target_predicates_ignore_or_and_negation(self):
        self.assertEqual(
            target_requirements(
                'HasState(131,"target") && GetCharacInPct("HP","target") < 20'
            ),
            (131, 20),
        )
        self.assertIsNone(
            target_requirements(
                '!HasState(131,"target") && GetCharacInPct("HP","target") < 20'
            )
        )
        self.assertIsNone(
            target_requirements(
                'HasState(131,"target") || GetCharacInPct("HP","target") < 20'
            )
        )

    def frame(self, old_level=5, new_level=6, old_uid=20, new_uid=21, hp=300):
        old = NS(
            reference=2071, level=old_level, uid=old_uid, target_id=-200, caster_id=-200
        )
        new = NS(
            reference=2071, level=new_level, uid=new_uid, target_id=-200, caster_id=-200
        )
        before = NS(
            actors={
                -200: NS(id=-200, state_ledger=NS(entries=[old])),
                -201: NS(hp=400, max_hp=2000),
            }
        )
        events = [
            dict(kind="damage", source_id=-200, target_id=-201, amount=100),
            dict(
                kind="state_applied",
                state_id=2071,
                actor_id=-200,
                source_id=-200,
                uid=new_uid,
            ),
        ]
        preview = NS(
            fight=NS(
                actors={
                    -200: NS(id=-200, state_ledger=NS(entries=[new])),
                    -201: NS(hp=hp, max_hp=2000),
                }
            ),
            spell=NS(events=events),
        )
        return before, preview

    def test_actual_safe_damage_and_native_charge_growth_require_events(self):
        before, preview = self.frame()
        proof = verify_damage_preview(before, preview, -200, -201, self.discover()[0])
        self.assertEqual(proof["charge_level"], 6)
        preview.spell.events = []
        with self.assertRaises(ValueError):
            verify_damage_preview(before, preview, -200, -201, self.discover()[0])

    def test_forecast_kill_rejected_before_normal_commit(self):
        before, preview = self.frame(hp=0)
        with self.assertRaises(ValueError):
            verify_damage_preview(before, preview, -200, -201, self.discover()[0])

    def test_native_cap_allows_damage_without_fabricated_new_state(self):
        before, preview = self.frame(old_level=6, new_level=6, old_uid=20, new_uid=20)
        preview.spell.events = preview.spell.events[:1]
        proof = verify_damage_preview(before, preview, -200, -201, self.discover()[0])
        self.assertTrue(proof["charge_at_native_cap"])
        preview.fight.actors[-200].state_ledger.entries[0].uid = 21
        with self.assertRaises(ValueError):
            verify_damage_preview(before, preview, -200, -201, self.discover()[0])

    def test_below_cap_missing_state_application_uid_rejected(self):
        before, preview = self.frame(old_level=5, new_level=6, old_uid=20, new_uid=20)
        preview.spell.events = preview.spell.events[:1]
        with self.assertRaises(ValueError):
            verify_damage_preview(before, preview, -200, -201, self.discover()[0])

    def state_frame(self):
        state = NS(
            reference=131,
            level=1,
            uid=55,
            target_id=-201,
            caster_id=-200,
            duration=1,
            clock_actor="target",
            tick_at_turn_end=True,
        )
        charge = NS(reference=2071, level=4, uid=56, target_id=-200, caster_id=-200)
        return NS(
            actors={
                -200: NS(id=-200, state_ledger=NS(entries=[charge])),
                -201: NS(id=-201, state_ledger=NS(entries=[state])),
            }
        ), [
            dict(
                kind="state_applied",
                state_id=131,
                uid=55,
                actor_id=-201,
                source_id=-200,
            )
        ]

    def test_target_actual_uid_owner_and_finite_clock_preserved(self):
        fight, events = self.state_frame()
        r = self.discover()[0]
        p = verify_target_state(fight, events, -200, -201, r)
        self.assertEqual(p["target_state_uid"], 55)
        self.assertEqual(
            verify_target_state(fight, (), -200, -201, r, prior_uid=55)["charge_level"],
            4,
        )
        fight.actors[-201].state_ledger.entries[0].caster_id = 7
        with self.assertRaises(ValueError):
            verify_target_state(fight, events, -200, -201, r)

    def test_expired_target_state_or_insufficient_charge_rejected(self):
        fight, events = self.state_frame()
        fight.actors[-201].state_ledger.entries[0].duration = 0
        with self.assertRaises(ValueError):
            verify_target_state(fight, events, -200, -201, self.discover()[0])
        fight, events = self.state_frame()
        fight.actors[-200].state_ledger.entries[0].level = 3
        with self.assertRaises(ValueError):
            verify_target_state(fight, events, -200, -201, self.discover()[0])

    def test_matching_uid_wrong_state_event_is_not_native_charge_proof(self):
        before, preview = self.frame()
        preview.spell.events[1]["state_id"] = 999
        with self.assertRaises(ValueError):
            verify_damage_preview(before, preview, -200, -201, self.discover()[0])


if __name__ == "__main__":
    unittest.main()
