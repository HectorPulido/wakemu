"""Owned Enutrof initialization, companion and native form integration."""
import random
import struct
import unittest

import test_combat_spell_transaction as native_fixture
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_start,
)
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.spells import encode_deck, available_spells
from wakfu_server.fight_checkpoint_store import snapshot


class EnutrofRuntimeTests(unittest.TestCase):
    def fixture(
        self, *, passives=(), actives=(2008, 2014, 2018), seed=7, target_distance=3
    ):
        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            3,
            200,
            native_qi=True,
            full_health=True,
            target_hp=20000,
            target_distance=target_distance,
            variation_seed=17,
        )
        deck = encode_deck(actives, passives)
        rng = random.Random(seed)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        # Production Ready installs roots/start1003 before the first actual
        # turn-start1001. Deposits are native1001 subscribers, not1003 grants.
        fight, _ = prepare_server_turn_start(
            character,
            {-7: monster},
            fight,
            deck,
            actor_id=fight.current.id,
            action_id=2,
            rng=rng,
            area_callbacks=True,
        )
        return character, monster, fight, deck, rng

    def cast(self, fixture, reference, cell, *, action_id=3):
        character, monster, fight, deck, rng = fixture
        before = snapshot(fight)
        uid = (
            granted_spells(fight, 7)
            .get(reference, {})
            .get("uid", (7 << 32) | reference)
        )
        transaction = prepare_server_spell(
            struct.pack(">qqiih", 7, uid, *cell),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=action_id,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(transaction.outcomes))
        return transaction

    def test_actual_ready_grants_all_four_owned_actions_without_duplicates(self):
        for passive in (
            None,
            *(
                row["id"]
                for row in available_spells(3, 200)
                if row["breed"] == 3 and row["kind"] == "passive"
            ),
        ):
            with self.subTest(passive=passive):
                fixture = self.fixture(passives=() if passive is None else (passive,))
                fight = fixture[2]
                grants = granted_spells(fight, 7)
                for slot, reference in enumerate((2063, 6405, 2027, 2038)):
                    self.assertIn(reference, grants)
                self.assertIn(
                    3652,
                    {entry.reference for entry in fight.actors[7].state_ledger.entries},
                )
                self.assertEqual(
                    len({row["uid"] for row in grants.values()}), len(grants)
                )

    def test_actual_ready_companion_keeps_book_and_rejects_duplicate_invocation(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book

        fixture = self.fixture()
        fight = fixture[2]
        companions = [
            actor
            for actor in fight.actors.values()
            if getattr(actor, "native_summon_source", None)
        ]
        self.assertEqual(len(companions), 1)
        companion = companions[0]
        self.assertEqual(companion.owner_id, 3)
        self.assertEqual(companion.native_summon_source["controller_id"], 7)
        self.assertIn(companion.native_summon_source["ref"], range(1380, 1385))
        book = actor_action_book(companion)
        self.assertEqual(
            {row["reference"] for row in book["actions"]},
            {2058, 2077, 3541, 3542, 8257, 8258, 8259},
        )
        caster = fight.actors[7]
        # Ready already constructs the real companion. A second2027 is a
        # native negative prerequisite, not a missing summon producer.
        cell = (caster.position[0] + 1, caster.position[1], caster.position[2])
        self.assertIn(cell, fight.walkable)
        before = snapshot(fight)
        with self.assertRaisesRegex(ValueError, "twV"):
            self.cast(fixture, 2027, cell)
        self.assertEqual(snapshot(fight), before)

    def test_perforserker_actual_entry_and_exit_restore_native_ap_mp_authority(self):
        fixture = self.fixture()
        source = fixture[2].actors[7]
        before = (source.ap, source.mp, source.max_ap, source.max_mp)
        entered = self.cast(fixture, 2038, source.position)
        actor = entered.fight.actors[7]
        self.assertIn(702, {entry.reference for entry in actor.state_ledger.entries})
        # eWq808 adds the AP maximum/current to MP and installs AP_AS_MP;
        # native AP remains an observed characteristic, not a second budget.
        paid_ap = entered.plan["costs"]["ap"]
        self.assertEqual(actor.ap, before[0] - paid_ap)
        self.assertEqual(actor.mp, before[1] + before[0] - paid_ap)
        self.assertEqual(actor.max_mp, before[3] + before[2])
        self.assertIn(50, actor.native_fight_properties)
        # The installed active branch386138 does not consume the companion.
        # Historical fusion87760/38039 is explicitly gated by `and False`.
        companions = [
            summon
            for summon in entered.fight.actors.values()
            if getattr(summon, "native_summon_source", None)
        ]
        self.assertEqual(len(companions), 1)
        self.assertGreater(companions[0].hp, 0)
        fixture = (*fixture[:2], entered.fight, *fixture[3:])
        # The native exit uses eYv913 and removes702 through88401; it is a real
        # second owned grant activation, never a direct state-removal fixture.
        exited = self.cast(fixture, 2038, actor.position, action_id=4)
        actor = exited.fight.actors[7]
        self.assertNotIn(702, {entry.reference for entry in actor.state_ledger.entries})
        self.assertEqual(actor.max_ap, before[2])
        # Native242970 is eWO57 amount100 with target-clock duration1.
        # It consumes the remaining form MP until its actual next-turn expiry.
        self.assertEqual(actor.max_mp, 0)
        from test_aniripsa_grant_summon_pipeline import AniripsaGrantSummonPipelineTests

        helper = AniripsaGrantSummonPipelineTests()
        fixture = (*fixture[:2], exited.fight, *fixture[3:])
        helper.next_player_turn(exited.fight, fixture)
        actor = exited.fight.actors[7]
        self.assertEqual((actor.max_ap, actor.max_mp), before[2:])
        snapshot(exited.fight)

    def test_owned_elemental_attacks_deal_damage_and_reject_self_atomically(self):
        # Baseline human-form positive branches; form resource gates are tested
        # separately, rather than treating a failed form prerequisite as damage.
        for reference in (
            2008,
            2010,
            2011,
            2012,
            2013,
            2014,
            2015,
            2016,
            2017,
            2018,
            2019,
            2021,
            2022,
            2032,
        ):
            with self.subTest(reference=reference):
                fixture = self.fixture(
                    actives=(reference,), target_distance=1 if reference == 2013 else 3
                )
                fight = fixture[2]
                before = snapshot(fight)
                with self.assertRaises(ValueError):
                    self.cast(fixture, reference, fight.actors[7].position)
                self.assertEqual(snapshot(fight), before)
                result = self.cast(fixture, reference, fight.actors[-7].position)
                self.assertLess(result.fight.actors[-7].hp, fight.actors[-7].hp)
                self.assertLess(result.fight.actors[7].ap, fight.actors[7].ap)

    def test_actual_excavation_consumes_owned_deposit_and_geology_returns_ap(self):
        from wakfu_server.combat_drops import native_prospection_bonus

        for passive in (None, 2009):
            with self.subTest(passive=passive):
                fixture = self.fixture(passives=() if passive is None else (passive,))
                fight = fixture[2]
                caster = fight.actors[7]
                deposits = [
                    row
                    for row in fight.native_effect_areas.values()
                    if row["reference"] in (202, 203, 204, 205)
                    and row["owner_id"] == 7
                    and 1
                    <= sum(abs(row["cell"][i] - caster.position[i]) for i in (0, 1))
                    <= 5
                ]
                self.assertTrue(
                    deposits, "Actual Ready must create a reachable native deposit"
                )
                deposit = min(
                    deposits,
                    key=lambda row: (
                        sum(abs(row["cell"][i] - caster.position[i]) for i in (0, 1)),
                        row["uid"],
                    ),
                )
                pp = native_prospection_bonus(caster)
                result = self.cast(fixture, 2063, tuple(deposit["cell"]))
                self.assertNotIn(deposit["uid"], result.fight.native_effect_areas)
                after = result.fight.actors[7]
                self.assertEqual(native_prospection_bonus(after), pp)
                self.assertEqual(after.ap - caster.ap, 0 if passive == 2009 else -1)
                if passive == 2009:
                    self.assertIn(
                        8895, {entry.reference for entry in after.state_ledger.entries}
                    )

    def test_form_native_passive_tables_change_range_and_utility_cost(self):
        for passive in (None, 8272, 8275):
            with self.subTest(range_passive=passive):
                fixture = self.fixture(
                    passives=() if passive is None else (passive,),
                    actives=(2008,),
                    target_distance=5 if passive == 8275 else 3,
                )
                entered = self.cast(fixture, 2038, fixture[2].actors[7].position)
                fixture = (*fixture[:2], entered.fight, *fixture[3:])
                target = entered.fight.actors[-7].position
                if passive == 8272:
                    before = snapshot(entered.fight)
                    with self.assertRaises(ValueError):
                        self.cast(fixture, 2008, target, action_id=4)
                    self.assertEqual(snapshot(entered.fight), before)
                else:
                    attacked = self.cast(fixture, 2008, target, action_id=4)
                    self.assertLess(
                        attacked.fight.actors[-7].hp, entered.fight.actors[-7].hp
                    )
                    self.assertEqual(attacked.plan["costs"]["ap"], 0)
                    self.assertEqual(attacked.plan["costs"]["mp"], 2)
                    self.assertEqual(
                        attacked.fight.actors[7].ap, entered.fight.actors[7].ap
                    )
                    self.assertEqual(
                        attacked.fight.actors[7].mp,
                        entered.fight.actors[7].mp - 2,
                    )
        for passive in (None, 8274):
            with self.subTest(cost_passive=passive):
                fixture = self.fixture(
                    passives=() if passive is None else (passive,),
                    actives=(6337,),
                    target_distance=3,
                )
                entered = self.cast(fixture, 2038, fixture[2].actors[7].position)
                fixture = (*fixture[:2], entered.fight, *fixture[3:])
                cast = self.cast(
                    fixture, 6337, entered.fight.actors[-7].position, action_id=4
                )
                self.assertEqual(cast.plan["costs"]["ap"], 0)
                self.assertEqual(cast.plan["costs"]["mp"], 0 if passive == 8274 else 1)

    def test_actual_controlled_drheller_turn_creates_owned_deposit(self):
        from pathlib import Path
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from class_spell_eligible_targets import eligible_cast_targets
        from test_aniripsa_grant_summon_pipeline import AniripsaGrantSummonPipelineTests
        from wakfu_server.combat_server_spell import server_runtime

        fixture = self.fixture(actives=(8240,))
        # 385439 counts the controller's existing203 deposits after385405
        # rebinds to that actual controller. Remove the existing203 through a
        # legal owned active before asking the Drheller to create another.
        initial_deposit = next(
            row
            for row in fixture[2].native_effect_areas.values()
            if row["reference"] == 203 and row["owner_id"] == 7
        )
        consumed = self.cast(fixture, 8240, tuple(initial_deposit["cell"]))
        fixture = (*fixture[:2], consumed.fight, *fixture[3:])
        character, monster, fight, deck, rng = fixture
        self.assertFalse(
            any(
                row["reference"] == 203 and row["owner_id"] == 7
                for row in fight.native_effect_areas.values()
            )
        )
        companion = next(
            actor
            for actor in fight.actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        helper = AniripsaGrantSummonPipelineTests()
        for _ in range(20):
            if fight.current.id == companion.id:
                break
            helper.end_current_turn(fight, fixture)
        self.assertEqual(fight.current.id, companion.id)
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=20, critical=False, rng=rng
        )
        candidates = eligible_cast_targets(
            fight,
            character,
            deck,
            3541,
            actor_id=companion.id,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            limit=128,
            maximum_eligible=3,
        )
        self.assertTrue(candidates["eligible"], candidates)
        cell = candidates["eligible"][0]["target"]
        before = snapshot(fight)
        original_areas = set(fight.native_effect_areas)
        from unittest.mock import patch
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        observed = []
        original_execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = original_execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (
                157697,
                255120,
                385405,
                385406,
                385439,
                385454,
                385455,
            ):
                observed.append(
                    (
                        invocation.reference,
                        invocation.caster_id,
                        invocation.target_id,
                        invocation.cell,
                        result,
                    )
                )
            return result

        with patch.object(EffectDispatcher, "execute", observe):
            tx = prepare_server_spell(
                struct.pack(">qqiih", companion.id, 3541, *cell),
                character,
                {-7: monster},
                fight,
                3,
                deck,
                action_id=20,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(tx.outcomes))
        created = [
            row
            for uid, row in tx.fight.native_effect_areas.items()
            if uid not in original_areas and row["reference"] == 203
        ]
        self.assertEqual(
            len(created),
            1,
            {
                "effects": observed,
                "areas": [
                    (row["uid"], row["reference"], row["owner_id"], row["cell"])
                    for row in tx.fight.native_effect_areas.values()
                ],
            },
        )
        self.assertEqual(tuple(created[0]["cell"]), tuple(cell))
        self.assertEqual(created[0]["owner_id"], 7)
        self.assertEqual(tx.fight.actors[companion.id].ap, companion.ap - 3)
        snapshot(tx.fight)

    def test_actual_deposit_conversion_uses_quotation_native_area(self):
        for passive in (None, 5076):
            with self.subTest(passive=passive):
                fixture = self.fixture(
                    passives=() if passive is None else (passive,), actives=(2026,)
                )
                fight = fixture[2]
                deposits = [
                    row
                    for row in fight.native_effect_areas.values()
                    if row["reference"] in (202, 203, 204, 205) and row["owner_id"] == 7
                ]
                self.assertTrue(deposits)
                tx = self.cast(fixture, 2026, fight.actors[7].position)
                converted = [
                    row
                    for row in tx.fight.native_effect_areas.values()
                    if row["reference"] in (207, 209) and row["owner_id"] == 7
                ]
                self.assertEqual(
                    {row["reference"] for row in converted},
                    {209 if passive == 5076 else 207},
                )
                self.assertEqual(len(converted), len(deposits))
                self.assertTrue(
                    all(
                        row["uid"] not in tx.fight.native_effect_areas
                        for row in deposits
                    )
                )

    def test_actual_debt_passive_changes_level_and_rejects_repeated_mark(self):
        for passive in (None, 6326):
            with self.subTest(passive=passive):
                fixture = self.fixture(passives=() if passive is None else (passive,))
                target = fixture[2].actors[-7].position
                tx = self.cast(fixture, 6405, target)
                marks = [
                    row
                    for row in tx.fight.actors[-7].state_ledger.entries
                    if row.reference == 3643
                ]
                self.assertEqual(sum(row.level for row in marks), 2 if passive else 1)
                fixture = (*fixture[:2], tx.fight, *fixture[3:])
                before = snapshot(tx.fight)
                with self.assertRaisesRegex(ValueError, "twV"):
                    self.cast(fixture, 6405, target, action_id=4)
                self.assertEqual(snapshot(tx.fight), before)

    def test_actual_ore_buff_consumes_deposit_with_native_state(self):
        fixture = self.fixture(actives=(8240,))
        fight = fixture[2]
        caster = fight.actors[7]
        deposits = [
            row
            for row in fight.native_effect_areas.values()
            if row["reference"] in (202, 203, 204, 205)
            and row["owner_id"] == 7
            and 1 <= sum(abs(row["cell"][i] - caster.position[i]) for i in (0, 1)) <= 5
        ]
        self.assertTrue(deposits)
        deposit = min(deposits, key=lambda row: row["uid"])
        tx = self.cast(fixture, 8240, tuple(deposit["cell"]))
        self.assertNotIn(deposit["uid"], tx.fight.native_effect_areas)
        states = {row.reference for row in tx.fight.actors[7].state_ledger.entries}
        self.assertIn(
            {202: 8563, 203: 8560, 204: 8561, 205: 8562}[deposit["reference"]], states
        )

    def test_actual_mobility_support_and_mature_interest_have_native_recipients(self):
        fixture = self.fixture(actives=(6324,))
        before = fixture[2].actors[7]
        tx = self.cast(fixture, 6324, before.position)
        self.assertGreater(tx.fight.actors[7].max_mp, before.max_mp)
        self.assertEqual(tx.fight.actors[7].effect_stats[4], before.effect_stats[4] - 1)
        self.assertEqual(tx.fight.actors[-7].hp, fixture[2].actors[-7].hp)

        fixture = self.fixture(actives=(8242,))
        tx = self.cast(fixture, 8242, fixture[2].actors[-7].position)
        target_states = {
            entry.reference for entry in tx.fight.actors[-7].state_ledger.entries
        }
        caster_states = {
            entry.reference for entry in tx.fight.actors[7].state_ledger.entries
        }
        self.assertIn(8582, target_states)
        self.assertNotIn(8582, caster_states)

    def test_actual_firedamp_cross_hits_enemy_from_owned_deposit(self):
        fixture = self.fixture(actives=(2037,), target_distance=1)
        fight = fixture[2]
        target = fight.actors[-7]
        deposits = [
            row
            for row in fight.native_effect_areas.values()
            if row["reference"] in (202, 203, 204, 205)
            and row["owner_id"] == 7
            and (
                row["cell"][0] == target.position[0]
                or row["cell"][1] == target.position[1]
            )
            and sum(abs(row["cell"][i] - target.position[i]) for i in (0, 1)) <= 2
        ]
        self.assertTrue(
            deposits, "Actual deposit must place the enemy in the native two-cell cross"
        )
        tx = self.cast(fixture, 2037, tuple(deposits[0]["cell"]))
        self.assertLess(tx.fight.actors[-7].hp, target.hp)
        self.assertEqual(tx.fight.actors[7].ap, fight.actors[7].ap - 4)

    def test_actual_mine_pouch_supports_companion_after_legal_owned_movement(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_actor import actual_actor_stats

        fixture = self.fixture(actives=(2064,))
        character, monster, fight, deck, rng = fixture
        companion = next(
            actor
            for actor in fight.actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        caster = fight.actors[7]
        occupied = {actor.position for actor in fight.actors.values()}
        destinations = [
            end
            for start, end in sorted(fight.edges)
            if start == caster.position
            and end not in occupied
            and sum(abs(end[i] - companion.position[i]) for i in (0, 1)) == 1
        ]
        self.assertTrue(destinations)
        runtime = RuntimeMessages(fight)
        apply_client(
            runtime,
            3,
            struct.pack(">qiih", 7, *destinations[0]),
            lambda actor: actual_actor_stats(
                character,
                actor,
                runtime.fight.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
            ),
            area_provider=lambda candidate, **boundary: prepare_area_movement(
                character, {-7: monster}, candidate, deck, rng=rng, **boundary
            ),
        )
        fixture = (*fixture[:2], runtime.fight, *fixture[3:])
        companion = runtime.fight.actors[companion.id]
        tx = self.cast(
            fixture, 2064, companion.position, action_id=runtime.action_id + 1
        )
        self.assertEqual(tx.fight.actors[companion.id].max_mp, companion.max_mp + 3)
        self.assertEqual(
            tx.fight.actors[7].effect_stats[4],
            runtime.fight.actors[7].effect_stats[4] - 1,
        )

    def test_actual_excavation_passives_change_native_cost_and_minimum_range(self):
        for passive in (None, 2028, 8278):
            with self.subTest(passive=passive):
                fixture = self.fixture(passives=() if passive is None else (passive,))
                fight = fixture[2]
                caster = fight.actors[7]
                deposits = [
                    row
                    for row in fight.native_effect_areas.values()
                    if row["reference"] in (202, 203, 204, 205) and row["owner_id"] == 7
                ]
                if passive == 8278:
                    close = next(
                        row
                        for row in deposits
                        if sum(abs(row["cell"][i] - caster.position[i]) for i in (0, 1))
                        < 3
                    )
                    before = snapshot(fight)
                    with self.assertRaises(ValueError):
                        self.cast(fixture, 2063, tuple(close["cell"]))
                    self.assertEqual(snapshot(fight), before)
                deposit = next(
                    row
                    for row in deposits
                    if sum(abs(row["cell"][i] - caster.position[i]) for i in (0, 1))
                    == 3
                )
                tx = self.cast(fixture, 2063, tuple(deposit["cell"]))
                self.assertEqual(tx.plan["costs"]["ap"], 0 if passive == 2028 else 1)
                self.assertEqual(tx.plan["costs"]["mp"], 1 if passive == 2028 else 0)

    def test_actual_blessing_turn_start_and_stirrup_form_states(self):
        for passive in (None, 2039):
            with self.subTest(blessing=passive):
                fixture = self.fixture(passives=() if passive is None else (passive,))
                treasure = sum(
                    row.level
                    for row in fixture[2].actors[7].state_ledger.entries
                    if row.reference == 8552
                )
                self.assertEqual(treasure, 1 if passive == 2039 else 0)
        for passive in (None, 8273):
            with self.subTest(stirrup=passive):
                fixture = self.fixture(passives=() if passive is None else (passive,))
                tx = self.cast(fixture, 2038, fixture[2].actors[7].position)
                states = {
                    row.reference for row in tx.fight.actors[7].state_ledger.entries
                }
                self.assertEqual(842 in states, passive == 8273)
