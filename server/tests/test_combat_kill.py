import json
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
from wakfu_server.combat_kill import (
    NativeKillHandler,
    kill_parameters,
    resource_transition,
    remove_kill,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext, NativeStatHandler
from wakfu_server.combat_ordinary_death import registered_ordinary_death
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_runner_callbacks import runner_value_scope


class NativeKillTests(unittest.TestCase):
    def fixture(self, parameter=0, *, minimum=0, frozen=(), mutation=None):
        actors = [
            Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 20, 3, True),
            Actor(-7, 1, (1, 0, 0), 100, 6, 3, 8, 20),
            Actor(-8, 1, (2, 0, 0), 100, 6, 3, 6, 20),
        ]
        fight = Fight(
            77,
            actors,
            {a.position for a in actors},
            {0: {actors[0].position}, 1: {actors[1].position, actors[2].position}},
        )
        fight.ready(3)
        target = fight.actors[-7]
        target.hp = 80
        target.effect_stats = {1: 80, 14: 3}
        target.effect_minima = {1: minimum, 14: 0}
        target.effect_maxima = {1: 100, 14: 10}
        target.effect_base_minima = dict(target.effect_minima)
        target.effect_base_maxima = dict(target.effect_maxima)
        target.effect_percentages = {1: 0, 14: 0}
        target.effect_frozen = frozenset(frozen)
        packets, phases = [], []
        sequence = iter(range(101, 500))
        authority = SimpleNamespace(
            property_counts=lambda p, a: getattr(a, "native_fight_property_counts", {})
        )
        handler = NativeKillHandler(
            fight,
            packets,
            action_id=5,
            allocate_uid=lambda: next(sequence),
            context=lambda *args: StatExecutionContext(
                True, True, None, True, b"", None
            ),
            rng=lambda: 0,
            authority=authority,
        )

        class Events:
            def phase(self, effect, invocation, **kwargs):
                phases.append(
                    (
                        kwargs["channel"],
                        kwargs["uid"],
                        kwargs["value"],
                        kwargs["_event_ids"],
                    )
                )
                if mutation:
                    mutation(kwargs["channel"], kwargs["runner_modifier"], handler)

            def register_applied(self, effect, invocation, uid):
                self.registered = uid

        handler.event_lifecycle = Events()
        effect = dict(
            effect_class=28,
            parameter_count=0 if parameter is None else 1,
            parameters=[] if parameter is None else [parameter, 0],
            target_masks=[[] for _ in range(7)],
        )
        invocation = EffectInvocation(112822, 20, 7, -7, (1, 0, 0))
        return fight, target, packets, phases, handler, effect, invocation

    def test_actual_minimum_not_forced_zero_and_removal_has_no_reversal(self):
        fight, target, packets, phases, handler, effect, invocation = self.fixture(
            1, minimum=5
        )
        handler(effect, {}, handler.prepare(effect, {}, invocation))
        self.assertEqual(target.hp, 5)
        self.assertEqual(
            (
                target.effect_base_maxima[14],
                target.effect_maxima[14],
                target.effect_stats[14],
            ),
            (0, 0, 0),
        )
        self.assertEqual(target.native_fight_property_counts[65], 1)
        self.assertFalse(any(e["kind"] == "death" for e in fight.events))
        stat = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=5,
            allocate_uid=lambda: 999,
            context=lambda *args: None,
        )
        stat.remove(101)
        self.assertEqual(
            (
                target.hp,
                target.effect_base_maxima[14],
                target.native_fight_property_counts[65],
            ),
            (5, 0, 1),
        )
        self.assertEqual(packets[-1][0], 13560)

    def test_zero_minimum_creates_owned_corpse_without_damage_or_damage_amount(self):
        fight, target, packets, phases, handler, effect, invocation = self.fixture()
        observed = []
        with runner_value_scope(lambda i, value: observed.append(value)) as scope:
            invocation = replace(invocation, native_value_scope=scope)
            handler(effect, {}, handler.prepare(effect, {}, invocation))
        self.assertEqual(target.hp, 0)
        self.assertTrue(registered_ordinary_death(fight, target))
        self.assertFalse(any(e["kind"] == "damage" for e in fight.events))
        self.assertEqual([p[0] for p in phases], [1, 2, 3, 4])
        self.assertEqual({p[1] for p in phases}, {101})
        self.assertTrue(all(p[2:] == (0, (0, 192)) for p in phases))
        self.assertEqual(observed, [0])
        self.assertEqual(
            _identity_fields(bytes.fromhex(fight.owned_stat_effects[101]["payload"]))[
                4
            ],
            0,
        )
        self.assertEqual(packets[0][0], 12613)

    def test_frozen_hp_and_clock_still_apply_independent_native_side_effects(self):
        fight, target, packets, phases, handler, effect, invocation = self.fixture(
            1, frozen=(1, 14)
        )
        handler(effect, {}, handler.prepare(effect, {}, invocation))
        self.assertEqual(target.hp, 80)
        self.assertEqual(
            (target.effect_base_maxima[14], target.effect_stats[14]), (0, 0)
        )
        self.assertIn(65, target.native_fight_properties)
        self.assertFalse(any(e["kind"] == "death" for e in fight.events))

    def test_parameter_count_and_context_forced_amount_do_not_change_runner_amount(
        self,
    ):
        for parameter in [None, -1, 0, 1, 2]:
            fight, target, packets, phases, handler, effect, invocation = self.fixture(
                parameter, minimum=5
            )
            invocation = replace(invocation, native_context_hex="08ff01")
            handler(effect, {}, handler.prepare(effect, {}, invocation))
            counts = getattr(target, "native_fight_property_counts", {})
            self.assertEqual(counts.get(65, 0), 1 if parameter == 1 else 0)
            self.assertEqual(fight.owned_stat_effects[101]["actual"], 0)

    def test_l2_revalidates_live_snapshot_and_cancellation_before_mutation(self):
        def change(channel, runner, handler):
            if channel == 2:
                target = handler.fight.actors[-7]
                target.effect_minima[1] = target.effect_base_minima[1] = 5

        fight, target, packets, phases, handler, effect, invocation = self.fixture(
            mutation=change
        )
        handler(effect, {}, handler.prepare(effect, {}, invocation))
        self.assertEqual(target.hp, 5)

        def cancel(channel, runner, handler):
            if channel == 2:
                handler.context = lambda *args: StatExecutionContext(
                    False, True, None, True, b"", None
                )

        fight, target, packets, phases, handler, effect, invocation = self.fixture(
            mutation=cancel
        )
        self.assertFalse(handler(effect, {}, handler.prepare(effect, {}, invocation)))
        self.assertEqual(target.hp, 80)
        self.assertEqual(packets, [])
        self.assertEqual(handler.runners, {})

    def test_unknown_clock_or_property_authority_rejects_before_mutation(self):
        for missing in ["clock", "properties"]:
            fight, target, packets, phases, handler, effect, invocation = self.fixture(
                1
            )
            if missing == "clock":
                del target.effect_stats[14]
            else:
                handler.authority = object()
            with self.assertRaises(ValueError):
                handler(effect, {}, handler.prepare(effect, {}, invocation))
            self.assertEqual(target.hp, 80)
            self.assertEqual(fight.owned_stat_effects, {})
            self.assertEqual(packets, [])
            self.assertEqual(handler.runners, {})

    def test_eXc_registered_area_without_hp_is_a_noop_and_hp_or_unknown_reject(self):
        from wakfu_server.combat_simple_area import simple_area_constructor
        from wakfu_server.combat_state_ledger import StateLedger
        from wakfu_server.combat_fake_fighter import fake_fighter_constructor
        from wakfu_server.combat_fake_fighter_resources import install_fake_fighter_hp

        simple = dict(
            type="SIMPLE",
            native_class="bcW",
            native_type_id=6,
            native_container_type=3,
            native_area_properties=[],
            entry_masks=[],
            native_shape_class="anD",
            native_shape_description="point",
        )
        hp_area = dict(
            type="FAKE_FIGHTER",
            native_class="bcQ",
            native_type_id=15,
            native_container_type=3,
            raw_bdh=[0.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, -1.0, -1.0],
            native_area_properties=[],
            entry_masks=[],
            native_shape_class="anD",
            native_shape_description="point",
        )
        definitions = {"314": simple, "1031": hp_area}

        def simple_row(identity=901):
            return dict(
                uid=identity,
                reference=314,
                level=1,
                cell=(1, 1, 0),
                owner_id=7,
                direction=0,
                native_area_contract="fbb",
                native_type_id=6,
                native_simple_constructor=simple_area_constructor(simple),
                native_running_effect_manager=False,
                native_obstacle_id=-1,
            )

        def hp_row(identity=902):
            row = dict(
                uid=identity,
                reference=1031,
                level=1,
                cell=(2, 1, 0),
                owner_id=7,
                direction=0,
                native_area_contract="faW",
                native_faw_constructor=fake_fighter_constructor(
                    hp_area, 1, allow_hp=True
                ),
                native_running_effect_manager=True,
                native_obstacle_id=-1,
                native_obstacle_source="QI.g(QK)",
                state_ledger=StateLedger(identity),
            )
            install_fake_fighter_hp(row, hp_area)
            return row

        def run_target(target_id, rows):
            fight, _, packets, _, handler, effect, invocation = self.fixture()
            fight.native_effect_areas = rows
            handler.context = lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            )
            invocation = replace(invocation, target_id=target_id)
            with patch(
                "wakfu_server.combat_effect_area.native_effect_areas",
                return_value=definitions,
            ):
                prepared = handler.prepare(effect, {}, invocation)
                outcome = handler(effect, {}, prepared)
            return fight, packets, handler, effect, prepared, outcome

        with self.subTest(target="registered-no-hp-area"):
            fight, packets, handler, effect, prepared, outcome = run_target(
                901, {901: simple_row()}
            )
            self.assertTrue(outcome)
            self.assertNotIn("hp", fight.native_effect_areas[901])
            self.assertNotIn("effect_stats", fight.native_effect_areas[901])
            self.assertEqual(fight.actors[-7].hp, 80)
            self.assertEqual(packets, [])
            self.assertEqual(fight.owned_stat_effects, {})
            self.assertEqual(handler.runners, {})

        for label, target_id, rows in (
            ("HP-owning-area", 902, {902: hp_row()}),
            ("unknown-area", 999, {}),
        ):
            with self.subTest(target=label):
                fight, _, _, _, _, _, _ = self.fixture()
                fight.native_effect_areas = rows
                _, _, packets, _, handler, effect, invocation = self.fixture()
                handler.fight.native_effect_areas = rows
                with patch(
                    "wakfu_server.combat_effect_area.native_effect_areas",
                    return_value=definitions,
                ):
                    with self.assertRaises(ValueError):
                        handler.prepare(
                            effect, {}, replace(invocation, target_id=target_id)
                        )
                self.assertEqual(packets, [])
                self.assertEqual(handler.runners, {})

    def test_malformed_removal_keeps_owned_identity_and_permanent_changes(self):
        fight, target, packets, phases, handler, effect, invocation = self.fixture(
            1, minimum=5
        )
        handler(effect, {}, handler.prepare(effect, {}, invocation))
        fight.owned_stat_effects[101]["payload"] = "00"
        with self.assertRaises(ValueError):
            remove_kill(handler, 101)
        self.assertIn(101, fight.owned_stat_effects)
        self.assertEqual(target.hp, 5)
        self.assertIn(65, target.native_fight_properties)

    def test_native_bulk_oracle_matches_shared_parameter_and_resource_contract(self):
        path = (
            Path(__file__).resolve().parents[2]
            / "server/test-fixtures/combat/kill-oracle.json"
        )
        oracle = json.loads(path.read_text())
        self.assertEqual(oracle["events"], [0, 192])
        self.assertEqual(len(oracle["rows"]), 384)
        for row in oracle["rows"]:
            effect = dict(
                parameter_count=row["parameter_count"], parameters=[row["parameter"], 0]
            )
            self.assertEqual(
                kill_parameters(effect, row["level"]), "property65" in row["order"]
            )
            self.assertEqual(
                resource_transition(
                    80,
                    row["hp_min"],
                    row["hp_min"],
                    0,
                    frozen=row["hp_frozen"],
                    hp=True,
                )[0],
                row["hp_after"],
            )
            current, raw, maximum = resource_transition(
                3, 0, 0, 0, frozen=row["ko_frozen"], hp=False
            )
            self.assertEqual(
                (current, raw, maximum), (row["ko_current"], row["ko_raw_max"], 0)
            )


if __name__ == "__main__":
    unittest.main()
