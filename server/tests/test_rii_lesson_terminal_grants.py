"""Temporary Rii spells are removed by fight finish and exit hooks."""
import unittest
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_combat_maximum_resource as maximum_fixture
import test_combat_pve_withdraw as withdrawal_fixture
from wakfu_server.combat_lifecycle import prepare_finish, prepare_finish_shared
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server import rii_lesson_grants
from wakfu_server.combat_spell_grant import granted_spells


class RiiLessonTerminalGrantTests(unittest.TestCase):
    grant_count = 4

    def make_fight(self):
        fixture = maximum_fixture.MaximumResourceTests()
        fixture.setUp()
        fight = fixture.fight
        contract = {"owner": 7, "target": -7, "hits": 0, "last_turn": None}
        fight.rii_element_lesson_contract = contract
        refs = patch(
            "wakfu_server.combat_spell_grant.native_spell_references",
            return_value=frozenset(
                (*rii_lesson_grants.SPELLS, 7967, 7972, 7973, 7974, 7975)
            ),
        )
        casts = patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={
                str(spell): {"maximum_level": 200}
                for spell in (*rii_lesson_grants.SPELLS, 7967, 7972, 7973, 7974, 7975)
            },
        )
        refs.start()
        casts.start()
        self.addCleanup(refs.stop)
        self.addCleanup(casts.stop)
        uid = [1000]

        def allocate():
            uid[0] += 1
            return uid[0]

        contract["grant_uids"] = rii_lesson_grants.install(
            fight, 7, [], action_id=1, allocate_uid=allocate
        )
        contract["initialized"] = True
        return fight

    @staticmethod
    def store_for(character):
        db = Mock()
        store = Mock()
        store.connection.return_value = nullcontext(db)
        store.character.return_value = character
        store.now.return_value = SimpleNamespace(timestamp=lambda: 0)
        return store, db

    @staticmethod
    def terminal_fight(fight):
        candidate = deepcopy(fight)
        candidate.phase = "finished"
        candidate.winner = 1  # the player loses, avoiding reward/catalog code
        return candidate

    def assert_grants_removed(self, fight):
        self.assertFalse(granted_spells(fight, 7))

    def test_local_finish_removes_grants_without_compiled_catalog(self):
        fight = self.terminal_fight(self.make_fight())
        runtime = RuntimeMessages(fight)
        character = {"id": 7, "account_id": 3, "name": "Rii"}
        store, db = self.store_for(character)
        terminal = deepcopy(fight)
        with patch("wakfu_server.combat_results.fight_report"), patch(
            "wakfu_server.combat_results.finish_messages", return_value=[]
        ), patch("wakfu_server.fight_store.finish"), patch(
            "wakfu_server.combat_scene_outcome.prepare_outcome",
            return_value=(fight, ()),
        ), patch(
            "wakfu_server.combat_equipment_finish.prepare_equipment_finish",
            return_value=(terminal, ()),
        ), patch(
            "wakfu_server.combat_captured_roster_checkpoint.persist_captured_roster_updates"
        ), patch(
            "wakfu_server.fight_store._write_terminal_checkpoint"
        ):
            result = prepare_finish(
                store,
                3,
                5,
                character,
                runtime,
                {},
                duration_ms=1,
                fight_instance_id=fight.id,
            )
        self.assertEqual(
            [op for op, _ in result["packets"]].count(13560), self.grant_count
        )
        self.assert_grants_removed(runtime.fight)
        self.assertIsNotNone(db)

    def test_local_finish_removes_state_carrier_and_states_lesson_grant(self):
        from types import SimpleNamespace
        from wakfu_server.combat_state_carrier import state_carrier_payload

        fight = self.make_fight()
        fight.rii_states_lesson_contract = {"owner": 7, "target": -7}
        grant_uids = rii_lesson_grants.install(
            fight, 7, [], action_id=1, allocate_uid=lambda: 2000, lesson="states"
        )
        target = fight.actors[-7]

        class Ledger:
            entries = [SimpleNamespace(uid=42, reference=8016)]

            def remove(self, uid):
                self.entries = [entry for entry in self.entries if entry.uid != uid]

        target.state_ledger = Ledger()
        payload = state_carrier_payload(
            uid=42,
            base_uid=None,
            caster_id=7,
            target_id=-7,
            state_id=8016,
            level=1,
            native_turn_clock=-1,
            native_realtime_remaining=0,
        )
        fight.state_wire_payloads = {42: payload.hex()}
        fight.native_retained_records[42] = {"target_id": -7, "effect_class": 310}
        fight.native_retained_order.append(42)
        fight.rii_states_lesson_contract.update(
            initialized=True, state_uid=42, visible_state=8016, grant_uids=grant_uids
        )
        fight.phase = "finished"
        fight.winner = 1
        runtime = RuntimeMessages(fight)
        character = {"id": 7, "account_id": 3, "name": "Rii"}
        store, db = self.store_for(character)
        terminal = deepcopy(fight)
        with patch("wakfu_server.combat_results.fight_report"), patch(
            "wakfu_server.combat_results.finish_messages", return_value=[]
        ), patch("wakfu_server.fight_store.finish"), patch(
            "wakfu_server.combat_scene_outcome.prepare_outcome",
            return_value=(fight, ()),
        ), patch(
            "wakfu_server.combat_equipment_finish.prepare_equipment_finish",
            return_value=(terminal, ()),
        ), patch(
            "wakfu_server.combat_captured_roster_checkpoint.persist_captured_roster_updates"
        ), patch(
            "wakfu_server.fight_store._write_terminal_checkpoint"
        ):
            result = prepare_finish(
                store,
                3,
                5,
                character,
                runtime,
                {},
                duration_ms=1,
                fight_instance_id=fight.id,
            )
        self.assertEqual(
            [op for op, _ in result["packets"]].count(13560), self.grant_count + 2
        )
        self.assertFalse(granted_spells(runtime.fight, 7))
        self.assertEqual(runtime.fight.actors[-7].state_ledger.entries, [])
        self.assertEqual(runtime.fight.state_wire_payloads, {})
        self.assertNotIn(42, runtime.fight.native_retained_records)
        self.assertNotIn(42, runtime.fight.native_retained_order)
        self.assertIsNotNone(db)

    def test_local_finish_removes_movement_grants_and_both_state_carriers(self):
        from wakfu_server.combat_state_carrier import state_carrier_payload

        fight = self.make_fight()
        fight.rii_movement_lesson_contract = {"owner": 7, "target": -7}
        packets = []
        next_uid = [2100]

        def allocate_uid():
            next_uid[0] += 1
            return next_uid[0]

        grant_uids = rii_lesson_grants.install(
            fight, 7, packets, action_id=1, allocate_uid=allocate_uid, lesson="movement"
        )

        class Ledger:
            def __init__(self, entries):
                self.entries = entries

            def remove(self, uid):
                self.entries = [entry for entry in self.entries if entry.uid != uid]

        fight.actors[-7].state_ledger = Ledger(
            [SimpleNamespace(uid=42, reference=8011)]
        )
        fight.actors[7].state_ledger = Ledger([SimpleNamespace(uid=43, reference=8011)])
        fight.state_wire_payloads = {}
        for uid, target_id in ((42, -7), (43, 7)):
            payload = state_carrier_payload(
                uid=uid,
                base_uid=None,
                caster_id=7,
                target_id=target_id,
                state_id=8011,
                level=3 if target_id == -7 else 4,
                native_turn_clock=-1,
                native_realtime_remaining=0,
            )
            fight.state_wire_payloads[uid] = payload.hex()
            fight.native_retained_records[uid] = {
                "target_id": target_id,
                "effect_class": 310,
            }
            fight.native_retained_order.append(uid)
        fight.rii_movement_lesson_contract.update(
            initialized=True, grant_uids=grant_uids, state_uid=42, owner_state_uid=43
        )
        fight = self.terminal_fight(fight)
        runtime = RuntimeMessages(fight)
        character = {"id": 7, "account_id": 3, "name": "Rii"}
        store, db = self.store_for(character)
        terminal = deepcopy(fight)
        with patch("wakfu_server.combat_results.fight_report"), patch(
            "wakfu_server.combat_results.finish_messages", return_value=[]
        ), patch("wakfu_server.fight_store.finish"), patch(
            "wakfu_server.combat_scene_outcome.prepare_outcome",
            return_value=(fight, ()),
        ), patch(
            "wakfu_server.combat_equipment_finish.prepare_equipment_finish",
            return_value=(terminal, ()),
        ), patch(
            "wakfu_server.combat_captured_roster_checkpoint.persist_captured_roster_updates"
        ), patch(
            "wakfu_server.fight_store._write_terminal_checkpoint"
        ):
            result = prepare_finish(
                store,
                3,
                5,
                character,
                runtime,
                {},
                duration_ms=1,
                fight_instance_id=fight.id,
            )
        self.assertEqual(
            [op for op, _ in result["packets"]].count(13560),
            self.grant_count + len(grant_uids) + 2,
        )
        self.assertFalse(granted_spells(runtime.fight, 7))
        self.assertEqual(runtime.fight.actors[-7].state_ledger.entries, [])
        self.assertEqual(runtime.fight.actors[7].state_ledger.entries, [])
        self.assertEqual(runtime.fight.state_wire_payloads, {})
        self.assertNotIn(42, runtime.fight.native_retained_records)
        self.assertNotIn(43, runtime.fight.native_retained_records)
        self.assertNotIn(42, runtime.fight.native_retained_order)
        self.assertNotIn(43, runtime.fight.native_retained_order)
        self.assertIsNotNone(db)

    def test_shared_finish_removes_grants_without_compiled_catalog(self):
        fight = self.terminal_fight(self.make_fight())
        runtime = RuntimeMessages(fight)
        character = {"id": 7, "account_id": 3, "name": "Rii"}
        store, db = self.store_for(character)
        member = {
            "character_id": 7,
            "account_id": 3,
            "session_generation": 5,
            "withdrawn": False,
        }

        def settle_shared(
            _store, _account, _generation, _character_id, source, callback, **_kwargs
        ):
            return callback(db, (member,), source)

        with patch(
            "wakfu_server.fight_store.settle_shared", side_effect=settle_shared
        ), patch("wakfu_server.combat_results.finish_messages", return_value=[]), patch(
            "wakfu_server.combat_scene_outcome.prepare_outcome",
            side_effect=lambda candidate, *_a, **_k: (candidate, ()),
        ), patch(
            "wakfu_server.combat_equipment_finish.prepare_equipment_finish",
            side_effect=lambda candidate, *_a, **_k: (deepcopy(candidate), ()),
        ), patch(
            "wakfu_server.combat_captured_roster_checkpoint.persist_captured_roster_updates"
        ), patch(
            "wakfu_server.fight_store._write_terminal_checkpoint"
        ), patch(
            "wakfu_server.combat_reward_ownership.is_earned_rift_recipient",
            return_value=False,
        ), patch(
            "wakfu_server.characters.companions.settle_rewards"
        ), patch(
            "wakfu_server.combat_companions.report_metadata",
            side_effect=lambda _db, _fight, report: report,
        ):
            result = prepare_finish_shared(
                store,
                3,
                5,
                7,
                runtime,
                {7: {"kind": "player"}, -7: {"kind": "monster"}},
                duration_ms=1,
                fight_instance_id=fight.id,
                policy_resolver=lambda *_: None,
                expected_accounts={3},
                owner_character_ids={3: 7},
            )
        self.assertEqual([op for op, _ in result[3]].count(13560), self.grant_count)
        self.assert_grants_removed(runtime.fight)

    def test_local_abandon_removes_grants_before_terminal_adoption(self):
        from wakfu_server import combat_abandon

        fight = self.make_fight()
        runtime = RuntimeMessages(fight)
        character = {"id": 7, "account_id": 3, "name": "Rii"}
        store, db = self.store_for(character)
        cursor = Mock(rowcount=1)
        cursor.fetchone.return_value = {"id": fight.id}
        db.execute.return_value = cursor
        with patch(
            "wakfu_server.combat_health.persist_owned",
            return_value={"character": character},
        ), patch("wakfu_server.rift_withdrawal_rewards.settle", return_value={}), patch(
            "wakfu_server.rift_runtime.abort_bound_fight"
        ):
            result = combat_abandon.prepare(store, 3, 5, character, runtime, b"")
        self.assertTrue(result["applied"])
        self.assertEqual(
            [op for op, _ in result["packets"]].count(13560), self.grant_count
        )
        self.assert_grants_removed(runtime.fight)
        self.assertEqual(runtime.fight.phase, "finished")

    def test_shared_individual_withdrawal_removes_departing_owner_grants(self):
        from wakfu_server.combat_pve_withdraw import plan

        helper = withdrawal_fixture.WithdrawalPlanTests()
        helper.setUp()
        fight, runtime, session = helper.fight, helper.runtime, helper.session
        owner = fight.actors[10]
        contract = {"owner": 10, "target": -200, "hits": 1, "last_turn": 1}
        fight.rii_element_lesson_contract = contract
        refs = patch(
            "wakfu_server.combat_spell_grant.native_spell_references",
            return_value=frozenset(rii_lesson_grants.SPELLS),
        )
        casts = patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={
                str(spell): {"maximum_level": 200} for spell in rii_lesson_grants.SPELLS
            },
        )
        refs.start()
        casts.start()
        self.addCleanup(refs.stop)
        self.addCleanup(casts.stop)
        uid = [1000]

        def allocate():
            uid[0] += 1
            return uid[0]

        contract["grant_uids"] = rii_lesson_grants.install(
            fight, owner.id, [], action_id=1, allocate_uid=allocate
        )
        contract["initialized"] = True
        fight.phase = "placement"
        with patch("wakfu_server.combat_pve_departure.retire_pve_actor"), patch(
            "wakfu_server.combat_death.death_messages", return_value=[]
        ):
            result = plan(session, fight, runtime)
        self.assertEqual(
            [op for op, _ in result.public_packets].count(13560), self.grant_count
        )
        self.assertNotIn("rii_element_lesson_contract", result.fight.__dict__)
        self.assertFalse(granted_spells(result.fight, owner.id))
        self.assertNotIn(
            "rii_element_lesson_contract", result.private_runtime.fight.__dict__
        )

    def test_shared_full_abandon_removes_requester_grants(self):
        from collections import deque
        from wakfu_server.combat_shared import Session, SharedFight
        from wakfu_server.combat_shared_abandon import prepare

        fight = self.make_fight()
        runtime = RuntimeMessages(fight)
        session = Session(3, 7, "generation", 1388, 0)
        shared = SharedFight(fight, 1388, 0, runtime)
        shared.participants[3] = session
        shared.connected.add(3)
        shared.outboxes[3] = deque()

        class Registry:
            def __init__(self):
                self.fights = {fight.id: shared}

            def lookup_character(self, identity):
                return shared if identity == 7 else None

            @staticmethod
            def _live(_session):
                return None

            @staticmethod
            def _member(_shared, _session):
                return None

            @staticmethod
            def _packets(packets):
                return tuple(packets)

            @staticmethod
            def _retire_join_aliases_locked(_shared):
                return None

        registry = Registry()
        character = {"id": 7, "account_id": 3, "name": "Rii"}
        store, db = self.store_for(character)
        cursor = Mock()
        cursor.fetchone.return_value = {"revision": 1}
        db.execute.return_value = cursor

        with patch(
            "wakfu_server.combat_captured_roster_lifecycle.restore_departing_roster"
        ), patch(
            "wakfu_server.combat_health.persist_aborted_shared_fight",
            return_value={7: {"character": character}},
        ), patch(
            "wakfu_server.combat_captured_roster_checkpoint.persist_captured_roster_updates"
        ), patch(
            "wakfu_server.fight_store._write_terminal_checkpoint"
        ):
            result = prepare(store, registry, session, character, b"")

        self.assertTrue(result["applied"])
        self.assertTrue(result["shared_full_abort"])
        self.assertEqual(
            [op for op, _ in result["packets"]].count(13560), self.grant_count
        )
        self.assertFalse(granted_spells(shared.fight, 7))
        self.assertEqual(shared.fight.phase, "finished")
        self.assertEqual(shared.fight.winner, None)


if __name__ == "__main__":
    unittest.main()
