"""Minimal source-shaped initial subscription witnesses; no runtime grants."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import initial_subscription_preparation as preparation


def source_fixture(event=1003, mask=5, criterion=""):
    records = {
        "10": dict(
            effect_class=330,
            children=[11],
            parameters=[0, 0],
            criteria=criterion,
            target_masks=[None] * 7,
        ),
        "11": dict(
            effect_class=304,
            children=[],
            parameters=[42, 0, 1, 0, -1, 0],
            criteria="",
            target_masks=[None] * 7,
        ),
    }
    records["10"]["target_masks"][mask] = [event]
    abilities = [dict(spell_id=99, level_parameter=-1)]
    row = dict(
        ref=7,
        blocked_spell=99,
        required_caster_state=42,
        owned_abilities=abilities,
        native_initial_state_triples=[8, 1, 0],
        initial_state_producer_paths=[
            dict(initial_state=8, producer_effect=11, path=[10, 11])
        ],
    )
    audit = dict(
        schema="native-owned-state-producer-audit-v1",
        rows=[row],
        native_records=records,
    )
    native = {
        7: dict(
            ref=7,
            min_level=1,
            max_level=200,
            native_abilities=deepcopy(abilities),
            initial_state_triples=[8, 1, 0],
        )
    }
    return audit, native


class InitialSubscriptionRecipeTests(unittest.TestCase):
    def tearDown(self):
        preparation.configure_source_audit(None)

    def test_disabled_default(self):
        self.assertEqual(
            preparation.recovery_recipes(7, 1, 99, 'HasState(42,"caster")', {}), []
        )

    def test_start_recipe_from_native_path(self):
        audit, native = source_fixture()
        preparation.configure_source_audit(audit)
        r = preparation.recovery_recipes(7, 1, 99, 'HasState(42,"caster")', native)[0]
        self.assertEqual(r["mode"], "normal_fight_start")
        self.assertEqual(r["kind"], "owned_spell_sequence")
        self.assertFalse(r["state_injection"])

    def test_direct_damage_requires_owned_native_witness(self):
        audit, native = source_fixture(2, 3, "not IsTriggeredByIndirectEffect()")
        audit["incoming_attack_witness"] = dict(reference=9, level=2, spell=123)
        native[9] = dict(
            min_level=1,
            max_level=3,
            native_abilities=[dict(spell_id=123, level_parameter=-1)],
        )
        preparation.configure_source_audit(audit)
        r = preparation.recovery_recipes(7, 1, 99, 'HasState(42,"caster")', native)[0]
        self.assertEqual(r["opponent"], dict(reference=9, level=2, team=0))
        self.assertEqual(r["attacker_spell"], 123)

    def test_missing_attack_witness_remains_pending(self):
        audit, native = source_fixture(2, 3, "not IsTriggeredByIndirectEffect()")
        preparation.configure_source_audit(audit)
        self.assertEqual(
            preparation.recovery_recipes(7, 1, 99, 'HasState(42,"caster")', native), []
        )

    def test_unowned_attack_rejected(self):
        audit, native = source_fixture(2, 3, "not IsTriggeredByIndirectEffect()")
        audit["incoming_attack_witness"] = dict(reference=9, level=2, spell=123)
        native[9] = dict(min_level=1, max_level=3, native_abilities=[])
        preparation.configure_source_audit(audit)
        with self.assertRaises(ValueError):
            preparation.recovery_recipes(7, 1, 99, 'HasState(42,"caster")', native)

    def test_constructor_initial_states_must_match(self):
        audit, native = source_fixture()
        native[7]["initial_state_triples"] = []
        preparation.configure_source_audit(audit)
        with self.assertRaises(ValueError):
            preparation.recovery_recipes(7, 1, 99, 'HasState(42,"caster")', native)

    def test_required_state_must_be_necessary(self):
        audit, native = source_fixture()
        preparation.configure_source_audit(audit)
        self.assertEqual(
            preparation.recovery_recipes(
                7, 1, 99, 'HasState(42,"caster") or HasState(43,"caster")', native
            ),
            [],
        )

    def test_wrong_state_and_unowned_spell(self):
        audit, _ = source_fixture()
        self.assertEqual(preparation.plans(audit, 7, 99, 41), [])
        self.assertEqual(preparation.plans(audit, 7, 100, 42), [])

    def test_unknown_event_and_missing_leaf_fail_closed(self):
        audit, _ = source_fixture(9999)
        self.assertEqual(preparation.plans(audit, 7, 99, 42), [])
        audit, _ = source_fixture()
        del audit["native_records"]["11"]
        self.assertEqual(preparation.plans(audit, 7, 99, 42), [])

    def test_ko_is_plan_only(self):
        audit, _ = source_fixture(1010)
        self.assertFalse(preparation.plans(audit, 7, 99, 42)[0]["executable"])

    def test_start_verifies_genuine_delivery_and_state(self):
        audit, _ = source_fixture()
        r = preparation.plans(audit, 7, 99, 42)[0]
        f = SimpleNamespace(
            native_start_event_delivered=True,
            actors={
                -200: SimpleNamespace(
                    hp=10,
                    state_ledger=SimpleNamespace(
                        entries=[SimpleNamespace(reference=42)]
                    ),
                )
            },
        )
        self.assertTrue(preparation.prepare_started(f, recipe=r)["state_verified"])
        f.native_start_event_delivered = False
        with self.assertRaises(ValueError):
            preparation.prepare_started(f, recipe=r)

    def test_configured_input_is_defensively_copied(self):
        audit, native = source_fixture()
        preparation.configure_source_audit(audit)
        audit["native_records"].clear()
        self.assertEqual(
            len(
                preparation.recovery_recipes(7, 1, 99, 'HasState(42,"caster")', native)
            ),
            1,
        )


class InitialSubscriptionSourceGeneratorTests(unittest.TestCase):
    def test_any_native_reference_and_owned_spell_generate_exact_path(self):
        audit, native = source_fixture()
        out = preparation.build_source_audit(
            [(7, 99, 42)], native, {"8": [10]}, audit["native_records"]
        )
        self.assertEqual(
            out["rows"][0]["initial_state_producer_paths"][0]["path"], [10, 11]
        )
        self.assertEqual(
            preparation.plans(out, 7, 99, 42)[0]["mode"], "normal_fight_start"
        )

    def test_formula_reference_not_treated_as_constant(self):
        audit, native = source_fixture()
        audit["native_records"]["11"]["parameter0_by_level"] = [42, 43]
        out = preparation.build_source_audit(
            [(7, 99, 42)], native, {"8": [10]}, audit["native_records"]
        )
        self.assertEqual(out["rows"][0]["initial_state_producer_paths"], [])

    def test_missing_native_effect_is_error_not_empty_authority(self):
        audit, native = source_fixture()
        del audit["native_records"]["11"]
        with self.assertRaises(ValueError):
            preparation.build_source_audit(
                [(7, 99, 42)], native, {"8": [10]}, audit["native_records"]
            )

    def test_unowned_query_is_never_generated(self):
        audit, native = source_fixture()
        self.assertEqual(
            preparation.build_source_audit(
                [(7, 100, 42)], native, {"8": [10]}, audit["native_records"]
            )["rows"],
            [],
        )


class SubscribedDamageDeliveryTests(unittest.TestCase):
    def proof(self, amount=0, packets=((1, b"x"),), hp=10):
        before = dict(hp=10, max_hp=10, armor=0, barrier=0)
        after = dict(before, hp=hp)
        return preparation.verify_subscribed_damage(
            before,
            after,
            [dict(kind="damage", source_id=-201, target_id=-200, amount=amount)],
            attacker_id=-201,
            caster_id=-200,
            packets=packets,
            native_events=[
                dict(
                    uid=20,
                    caster_id=-201,
                    target_id=-200,
                    event_ids=[2],
                    channel=3,
                    native_events_verified=True,
                )
            ],
            before_uid=20,
            after_uid=21,
            state_verified=True,
        )

    def test_actual_zero_damage_is_native_event_not_hp_prerequisite(self):
        self.assertEqual(self.proof()["damage_events"][0]["amount"], 0)

    def test_damage_without_packets_rejected(self):
        with self.assertRaises(ValueError):
            self.proof(packets=())

    def test_dead_recipient_rejected(self):
        with self.assertRaises(ValueError):
            self.proof(amount=10, hp=0)

    def test_negative_damage_rejected(self):
        with self.assertRaises(ValueError):
            self.proof(amount=-1)

    def test_fake_event_without_uid_or_state_fails(self):
        before = dict(hp=10, max_hp=10, armor=0, barrier=0)
        args = dict(
            attacker_id=-201,
            caster_id=-200,
            packets=[(1, b"x")],
            before_uid=20,
            after_uid=21,
            state_verified=True,
        )
        damage = [dict(kind="damage", source_id=-201, target_id=-200, amount=0)]
        with self.assertRaises(ValueError):
            preparation.verify_subscribed_damage(
                before, before, damage, native_events=[], **args
            )
        args["state_verified"] = False
        with self.assertRaises(ValueError):
            preparation.verify_subscribed_damage(
                before,
                before,
                damage,
                native_events=[
                    dict(
                        uid=20,
                        caster_id=-201,
                        target_id=-200,
                        event_ids=[2],
                        channel=3,
                        native_events_verified=True,
                    )
                ],
                **args
            )
