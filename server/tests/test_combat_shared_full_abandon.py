"""Real isolated leases, KO mutation and per-owner native abort continuations."""
import json
import struct
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.combat_shared import Session
from wakfu_server.combat_state import Actor
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_shared_abandon import prepare


class SharedFullAbandonTests(PostgresCase):
    def fixture(self, *, ko=True, disconnected=False, requester_ko=False):
        from test_combat_abandon import setup_abandon_state
        from wakfu_server import health_store
        from native_combat_fixture import initialize_fixture_qi

        store, account, generation, character, fight, runtime = setup_abandon_state(
            self.store
        )
        adapter = CombatSessionAdapter(store)
        requester = adapter.session(account, generation, character)
        fight.walkable.update({(0, 1, 0), (1, 1, 0)})
        fight.placement[0].update({(0, 1, 0), (1, 1, 0)})
        native = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "native_sram_double227_owner_population.json"
            ).read_text()
        )
        double = Actor(208, 0, (1, 1, 0), 661, 6, 3, 80, 200, account, True)
        double.native_summon_source = deepcopy(native["native_summon_source"])
        double.native_summon_source.update(
            caster_id=character["id"], controller_id=character["id"]
        )
        registration = deepcopy(native["native_summon_registration"])
        registration.update(caster_id=character["id"], controller_id=character["id"])
        registration["authority"]["native_controller_id"] = character["id"]
        registration["authority"]["summon_root_id"] = character["id"]
        for key in ("dpr_id", "dpu_id"):
            registration["authority"]["targeting"][key] = character["id"]
        fight.actors[208] = double
        fight.native_summon_registrations = {208: registration}
        if requester_ko:
            hero = store.create_character(account, "LivingHero")
            hero = store.select_character(account, generation, hero["id"])
            hero = health_store.initialize(
                store, account, generation, hero["id"], coefficient=0
            )
            store.select_character(account, generation, character["id"])
            fight.walkable.add((2, 1, 0))
            fight.placement[0].add((2, 1, 0))
            fight.actors[hero["id"]] = Actor(
                hero["id"], 0, (2, 1, 0), hero["hp"], 6, 3, 70, 1, account, True
            )
            with store.connection() as db:
                db.execute(
                    "INSERT INTO combat_fight_participants "
                    "(fight_id,character_id,account_id,team,session_generation,entry_hp,"
                    "entry_max_hp,entry_hp_damage,entry_health_dead) "
                    "VALUES(%s,%s,%s,0,%s,%s,%s,%s,%s)",
                    (
                        fight.id,
                        hero["id"],
                        account,
                        generation,
                        hero["hp"],
                        hero["max_hp"],
                        hero["hp_damage"],
                        hero["health_dead"],
                    ),
                )
        # Own the complete initial constructor population before consuming
        # fresh QI/PV registration. Later join uses its incremental producer.
        from wakfu_server.combat_state import Fight
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        fight = Fight(
            fight.id,
            tuple(fight.actors.values()),
            fight.walkable,
            fight.placement,
            valid_edges=fight.edges,
        )
        fight.native_summon_registrations = {208: registration}
        self.assertEqual(fight.native_qi_fresh_actor_order, tuple(fight.actors))
        self.assertEqual(fight.phase, "placement")
        self.assertIsNone(fight.native_effect_uid_next)
        self.assertIsNone(fight.native_qi_slots)
        self.assertFalse(getattr(fight, "native_effect_areas", {}))
        self.assertFalse(hasattr(fight, "native_global_pv_collections"))
        self.assertTrue(all(actor.hp > 0 for actor in fight.actors.values()))
        initialize_fixture_qi(fight)
        runtime = RuntimeMessages(fight)
        shared = adapter.registry.register(fight, requester, runtime=runtime)
        other_account = store.register("other-owner", "test-password")["id"]
        other_generation = store.begin_session(other_account)
        other_character = store.create_character(other_account, "Other")
        other_character = store.select_character(
            other_account, other_generation, other_character["id"]
        )
        other_character = health_store.initialize(
            store, other_account, other_generation, other_character["id"], coefficient=0
        )
        other = adapter.session(other_account, other_generation, other_character)
        with store.connection() as db:
            db.execute(
                "INSERT INTO combat_fight_participants "
                "(fight_id,character_id,account_id,team,session_generation,entry_hp,"
                "entry_max_hp,entry_hp_damage,entry_health_dead) "
                "VALUES(%s,%s,%s,0,%s,%s,%s,%s,%s)",
                (
                    fight.id,
                    other.character_id,
                    other.account_id,
                    other.generation,
                    other_character["hp"],
                    other_character["max_hp"],
                    other_character["hp_damage"],
                    other_character["health_dead"],
                ),
            )
        joined_actor = Actor(
            other.character_id,
            0,
            (0, 1, 0),
            other_character["hp"],
            6,
            3,
            90,
            1,
            other_account,
            True,
        )
        joined_actor.physical_radius = 0
        joined_actor.native_physical_position = joined_actor.position
        shared = adapter.registry.join(
            other,
            struct.pack(">qB", requester.character_id, 0),
            joined_actor,
            actor_payload=lambda *_: (b"owned-stats", b"owned-effects"),
            bootstrap_packets=lambda *_: [(12847, b"isolated-placement-constructor")],
        )
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_global_pv_collections import global_fighter_guards

        current_registry(shared.fight)
        self.assertIsNone(shared.fight.native_qi_fresh_actor_order)
        self.assertTrue(
            all(
                global_fighter_guards(shared.fight, identity)["baF"]
                for identity in shared.fight.actors
            )
        )
        shared.fight.ready(requester.account_id)
        shared.fight.ready(other.account_id)
        from wakfu_server.fight_store import activate

        activate(
            store,
            requester.account_id,
            requester.generation,
            requester.character_id,
            shared.fight.id,
        )
        shared.runtime.fight = shared.fight
        for queue in shared.outboxes.values():
            queue.clear()
        if ko:
            victim = shared.fight.actors[other.character_id]
            shared.fight.apply_effect_damage(-200, other.character_id, victim.hp)
        if requester_ko:
            shared.fight.apply_effect_damage(
                -200,
                requester.character_id,
                shared.fight.actors[requester.character_id].hp,
            )
        if disconnected:
            adapter.disconnect(other)
            store.end_session(other.account_id, other.generation)
        return adapter, shared, requester, character, other, other_character

    def terminal_rosters(self, packets):
        body = next(body for opcode, body in packets if opcode == 12238)
        fight_id, action_id, reserved = struct.unpack_from(">iii", body)
        self.assertEqual((fight_id, reserved, body[12]), (7, -1, 0))
        self.assertGreaterEqual(action_id, 0)
        offset = 13
        rosters = []
        for _ in range(3):
            count = struct.unpack_from(">b", body, offset)[0]
            self.assertGreaterEqual(count, 0)
            offset += 1
            rosters.append(struct.unpack_from(">" + "q" * count, body, offset))
            offset += count * 8
        self.assertEqual(offset, len(body))
        return rosters

    def requester_ack(self, adapter, shared, requester, character):
        result = adapter.return_withdrawn_pve(
            requester,
            shared.fight.id,
            character,
            struct.pack(">iB", shared.fight.id, 1),
            wp=6,
            pending=shared.withdrawals[requester.account_id],
        )
        self.assertTrue(shared.runtime.abandon_returned)
        self.assertIn(requester.account_id, shared.returned)
        self.assertNotIn(requester.account_id, shared.connected)
        return result

    def test_connected_ko_gets_native_terminal_and_each_ack_cleans_only_its_owner(self):
        adapter, shared, requester, character, other, other_character = self.fixture()
        before = shared.fight.actors[requester.character_id].hp
        result = prepare(self.store, adapter.registry, requester, character, b"")
        self.assertTrue(result["applied"])
        self.assertEqual((shared.fight.phase, shared.fight.winner), ("finished", None))
        delivered = {}
        adapter.dispatch_connected(
            shared.fight.id,
            lambda session, batches: delivered.setdefault(
                session.account_id,
                tuple(packet for batch in batches for packet in batch.packets),
            ),
        )
        self.assertEqual(set(delivered), {other.account_id})
        losers, winners, unused = self.terminal_rosters(delivered[other.account_id])
        self.assertIn(other.character_id, losers)
        self.assertEqual(losers, (other.character_id,))
        self.assertIn(208, self.terminal_rosters(result["packets"])[0])
        self.assertEqual(winners, (-200,))
        self.assertEqual(unused, ())
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT status FROM combat_fights WHERE id=7").fetchone()[
                    "status"
                ],
                "aborted",
            )
            checkpoint = db.execute(
                "SELECT status,snapshot FROM fight_checkpoints WHERE fight_id=7"
            ).fetchone()
            self.assertEqual(
                (checkpoint["status"], checkpoint["snapshot"]["phase"]),
                ("aborted", "finished"),
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_rewards").fetchone()["n"], 0
            )
        self.requester_ack(adapter, shared, requester, result["character"])
        self.assertIn(shared.fight.id, adapter.registry.fights)
        self.assertEqual(shared.returned, {requester.account_id})
        returned = adapter.return_withdrawn_pve(
            other,
            shared.fight.id,
            self.store.character(other.account_id, other.character_id),
            struct.pack(">iB", shared.fight.id, 1),
            wp=6,
        )
        self.assertGreater(returned["character"]["hp"], 0)
        self.assertEqual(shared.fight.actors[requester.character_id].hp, before)
        self.assertNotIn(shared.fight.id, adapter.registry.fights)
        self.assertFalse(
            any(value == 7 for value in adapter.registry.by_character.values())
        )
        self.assertFalse(
            any(value == 7 for value in adapter.registry.by_actor.values())
        )

    def test_disconnected_ko_recovers_on_real_replacement_lease_without_terminal_replay(
        self,
    ):
        adapter, shared, requester, character, other, other_character = self.fixture(
            disconnected=True
        )
        result = prepare(self.store, adapter.registry, requester, character, b"")
        self.requester_ack(adapter, shared, requester, result["character"])
        generation = self.store.begin_session(other.account_id)
        selected = self.store.select_character(
            other.account_id, generation, other.character_id
        )
        replacement = adapter.session(other.account_id, generation, selected)
        saved = adapter.recover_withdrawn_pve(replacement)
        self.assertGreater(saved["hp"], 0)
        self.assertNotIn(shared.fight.id, adapter.registry.fights)
        self.assertIsNone(adapter.recover_withdrawn_pve(replacement))

    def test_foreign_live_owner_and_wrong_session_reject_without_any_health_or_packet_mutation(
        self,
    ):
        adapter, shared, requester, character, other, other_character = self.fixture(
            ko=False
        )
        before = (shared.fight, shared.runtime, shared.sequence)
        with self.assertRaisesRegex(ValueError, "live primary"):
            prepare(self.store, adapter.registry, requester, character, b"")
        foreign = Session(
            other.account_id,
            requester.character_id,
            other.generation,
            requester.map_id,
            requester.instance_id,
        )
        with self.assertRaises(ValueError):
            prepare(self.store, adapter.registry, foreign, character, b"")
        self.assertEqual((shared.fight, shared.runtime, shared.sequence), before)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_health_exits").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM combat_pve_withdrawals"
                ).fetchone()["n"],
                0,
            )
        self.assertTrue(all(not queue for queue in shared.outboxes.values()))

    def test_replaced_ko_generation_and_late_encoder_failure_are_atomic(self):
        adapter, shared, requester, character, other, other_character = self.fixture()
        before = (shared.fight, shared.runtime, shared.sequence)
        with patch(
            "wakfu_server.combat_abandon._terminal_packets",
            side_effect=ValueError("encode-failed"),
        ):
            with self.assertRaisesRegex(ValueError, "encode-failed"):
                prepare(self.store, adapter.registry, requester, character, b"")
        replacement = self.store.begin_session(other.account_id)
        self.store.select_character(other.account_id, replacement, other.character_id)
        with self.assertRaisesRegex(ValueError, "generation was replaced"):
            prepare(self.store, adapter.registry, requester, character, b"")
        self.assertEqual((shared.fight, shared.runtime, shared.sequence), before)
        self.assertTrue(all(not queue for queue in shared.outboxes.values()))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_health_exits").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM combat_pve_withdrawals"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute("SELECT status FROM combat_fights WHERE id=7").fetchone()[
                    "status"
                ],
                "active",
            )

    def test_preexisting_pending_withdrawal_receipt_and_terminal_are_preserved(self):
        adapter, shared, requester, character, other, other_character = self.fixture()
        receipt = adapter.withdraw_pve(other, other_character, b"")
        before_packets = receipt["withdrawal"].private_packets
        result = prepare(self.store, adapter.registry, requester, character, b"")
        self.assertIs(shared.withdrawals[other.account_id], receipt)
        self.assertIs(receipt["withdrawal"].private_packets, before_packets)
        self.assertFalse(shared.outboxes[other.account_id])
        self.requester_ack(adapter, shared, requester, result["character"])
        returned = adapter.return_withdrawn_pve(
            other,
            shared.fight.id,
            self.store.character(other.account_id, other.character_id),
            struct.pack(">iB", shared.fight.id, 1),
            wp=6,
        )
        self.assertGreater(returned["character"]["hp"], 0)
        self.assertNotIn(shared.fight.id, adapter.registry.fights)

    def test_wrong_ack_and_duplicate_request_cannot_change_another_owner(self):
        from wakfu_server.combat_abandon import return_to_world

        adapter, shared, requester, character, other, other_character = self.fixture()
        result = prepare(self.store, adapter.registry, requester, character, b"")
        before_sequence = shared.sequence
        retry = prepare(
            self.store, adapter.registry, requester, result["character"], b""
        )
        self.assertFalse(retry["applied"])
        self.assertEqual(retry["packets"], ())
        self.assertEqual(shared.sequence, before_sequence)
        with self.assertRaises(ValueError):
            adapter.return_withdrawn_pve(
                other,
                shared.fight.id,
                self.store.character(other.account_id, other.character_id),
                struct.pack(">iB", 999, 1),
                wp=6,
            )
        self.assertFalse(shared.returned)
        self.requester_ack(adapter, shared, requester, result["character"])
        retry_return = return_to_world(
            self.store,
            requester.account_id,
            requester.generation,
            result["character"],
            shared.runtime,
            struct.pack(">iB", shared.fight.id, 1),
            wp=6,
        )
        self.assertFalse(retry_return["applied"])
        self.assertEqual(retry_return["packets"], [])
        self.assertNotIn(other.account_id, shared.returned)

    def test_old_ack_after_abort_cannot_mutate_replacement_selected_lease(self):
        adapter, shared, requester, character, other, other_character = self.fixture()
        prepare(self.store, adapter.registry, requester, character, b"")
        generation = self.store.begin_session(other.account_id)
        selected = self.store.select_character(
            other.account_id, generation, other.character_id
        )
        before = dict(self.store.character(other.account_id, other.character_id))
        with self.assertRaises(ValueError):
            adapter.return_withdrawn_pve(
                other,
                shared.fight.id,
                before,
                struct.pack(">iB", shared.fight.id, 1),
                wp=6,
            )
        self.assertNotIn(other.account_id, shared.returned)
        self.assertEqual(
            self.store.character(other.account_id, other.character_id)["hp"],
            before["hp"],
        )
        replacement = adapter.session(other.account_id, generation, selected)
        saved = adapter.recover_withdrawn_pve(replacement)
        self.assertGreater(saved["hp"], 0)
        self.assertIn(other.account_id, shared.returned)

    def test_late_transaction_failure_rolls_back_health_receipts_checkpoint_and_queues(
        self,
    ):
        adapter, shared, requester, character, other, other_character = self.fixture()
        before = (shared.fight, shared.runtime, shared.sequence)
        with patch(
            "wakfu_server.fight_store._write_terminal_checkpoint",
            side_effect=ValueError("terminal-store-failed"),
        ):
            with self.assertRaisesRegex(ValueError, "terminal-store-failed"):
                prepare(self.store, adapter.registry, requester, character, b"")
        self.assertEqual((shared.fight, shared.runtime, shared.sequence), before)
        self.assertTrue(all(not queue for queue in shared.outboxes.values()))
        self.assertFalse(shared.withdrawals)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_health_exits").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM combat_pve_withdrawals"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_checkpoints").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute("SELECT status FROM combat_fights WHERE id=7").fetchone()[
                    "status"
                ],
                "active",
            )

    def test_actual_world_binding_selects_private_ko_ack_and_requester_idle_is_safe(
        self,
    ):
        import ast
        from test_pve_withdraw_dispatcher import WithdrawalDispatcherTests

        adapter, shared, requester, character, other, other_character = self.fixture()
        result = {}
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        refresh = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "refresh_shared_combat"
        )
        wrapper = ast.parse(
            """
def bind(shared, owner, before_dispatch=None):
    fight = shared.fight
    fight_messages = shared.runtime
    group_lease = None
    TEST_MONSTERS = ()
    TEST_MONSTERS_BY_ID = {}
    pve_withdrawal_pending = None
    combat_session = owner
    loaded = True
    if before_dispatch is not None:
        before_dispatch()
    return locals()
"""
        )
        function = wrapper.body[0]
        function.body.insert(-1, refresh)
        # The socket snapshots these locals before receiving the ACK frame.
        # Execute the real pre-packet refresh after another owner's commit.
        packet_refresh = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test)
            == "combat_session is not None and fight is not None"
            and len(node.body) == 1
            and ast.unparse(node.body[0]) == "refresh_shared_combat()"
        )
        function.body.insert(-1, packet_refresh)
        from wakfu_server.performance_profiler import PROFILER

        scope = dict(COMBAT_SESSIONS=adapter, PROFILER=PROFILER)
        exec(compile(ast.fix_missing_locations(wrapper), str(source), "exec"), scope)
        bound = scope["bind"](
            shared,
            other,
            lambda: result.update(
                prepare(self.store, adapter.registry, requester, character, b"")
            ),
        )
        self.assertIs(
            bound["pve_withdrawal_pending"], shared.withdrawals[other.account_id]
        )
        self.assertIsNone(bound["combat_session"])
        self.assertIsNone(bound["fight"])
        self.assertFalse(bound["loaded"])
        main = scope["bind"](shared, requester)
        self.assertIs(main["fight"], shared.fight)
        self.assertTrue(main["loaded"])
        self.assertIsNone(main["pve_withdrawal_pending"])
        self.assertEqual(
            adapter.expire_current_turn(shared.fight.id, requester, now_ms=1000),
            (False, None),
        )
        fixture = WithdrawalDispatcherTests()
        fixture.tree = tree
        context = fixture.context()
        context.update(
            COMBAT_SESSIONS=adapter,
            STORE=self.store,
            account_id=other.account_id,
            generation=other.generation,
            character=dict(self.store.character(other.account_id, other.character_id)),
            body=struct.pack(">iB", shared.fight.id, 1),
            pve_withdrawal_pending=bound["pve_withdrawal_pending"],
        )
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test)
            == "opcode == 12925 and pve_withdrawal_pending is not None"
        )
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(body=branch.body, type_ignores=[])
                ),
                str(source),
                "exec",
            ),
            context,
        )
        context["record"].assert_any_call(
            event="shared_pve_withdrawal_returned",
            actor_id=other.character_id,
            fight_id=shared.fight.id,
        )
        self.assertIsNone(context["pve_withdrawal_pending"])
        self.assertTrue(context["loaded"])
        self.assertGreater(context["character"]["hp"], 0)
        self.assertIn(other.account_id, shared.returned)
        self.requester_ack(adapter, shared, requester, result["character"])
        self.assertNotIn(shared.fight.id, adapter.registry.fights)

    def test_real_group_restore_rolls_back_with_failed_terminal_checkpoint(self):
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.monsters import owned_instance

        adapter, shared, requester, character, other, other_character = self.fixture()
        groups = PersistentGroups(self.store)
        key = groups.register(
            requester.map_id,
            requester.instance_id,
            501,
            [owned_instance(5525, 1, -200, map_id=requester.map_id, x=1, y=0, z=0)],
        )
        lease, _ = groups.claim(key, requester.generation, shared.fight.id)
        shared.group_lease = lease
        with patch(
            "wakfu_server.fight_store._write_terminal_checkpoint",
            side_effect=ValueError("checkpoint-failed"),
        ):
            with self.assertRaisesRegex(ValueError, "checkpoint-failed"):
                prepare(
                    self.store,
                    adapter.registry,
                    requester,
                    character,
                    b"",
                    groups=groups,
                )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT status,generation,fight_id FROM combat_groups "
                "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                key,
            ).fetchone()
            self.assertEqual(
                (row["status"], row["generation"], row["fight_id"]),
                ("fighting", requester.generation, shared.fight.id),
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_health_exits").fetchone()[
                    "n"
                ],
                0,
            )
        result = prepare(
            self.store, adapter.registry, requester, character, b"", groups=groups
        )
        self.assertTrue(result["group_restored"])
        with self.store.connection() as db:
            row = db.execute(
                "SELECT status,generation,fight_id FROM combat_groups "
                "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                key,
            ).fetchone()
            self.assertEqual(
                (row["status"], row["generation"], row["fight_id"]),
                ("available", None, None),
            )

    def test_returned_withdrawn_owner_new_selected_lease_is_not_rewritten(self):
        adapter, shared, requester, character, other, other_character = self.fixture()
        receipt = adapter.withdraw_pve(other, other_character, b"")
        adapter.return_withdrawn_pve(
            other,
            shared.fight.id,
            self.store.character(other.account_id, other.character_id),
            struct.pack(">iB", shared.fight.id, 1),
            wp=6,
        )
        generation = self.store.begin_session(other.account_id)
        replacement = self.store.create_character(other.account_id, "NewSelected")
        selected = self.store.select_character(
            other.account_id, generation, replacement["id"]
        )
        before = dict(self.store.character(other.account_id, other.character_id))
        result = prepare(self.store, adapter.registry, requester, character, b"")
        self.assertTrue(result["applied"])
        self.assertIs(shared.withdrawals[other.account_id], receipt)
        self.assertEqual(
            self.store.character(other.account_id, other.character_id)["hp"],
            before["hp"],
        )
        self.assertTrue(
            self.store.current_character_session(
                other.account_id, generation, selected["id"]
            )
        )

    def test_requester_disconnect_recovers_its_receipt_after_other_owner_native_ack(
        self,
    ):
        from wakfu_server.combat_abandon import return_to_world

        adapter, shared, requester, character, other, other_character = self.fixture()
        result = prepare(self.store, adapter.registry, requester, character, b"")
        adapter.disconnect(requester)
        self.store.end_session(requester.account_id, requester.generation)
        adapter.return_withdrawn_pve(
            other,
            shared.fight.id,
            self.store.character(other.account_id, other.character_id),
            struct.pack(">iB", shared.fight.id, 1),
            wp=6,
        )
        self.assertIn(shared.fight.id, adapter.registry.fights)
        self.assertEqual(shared.returned, {other.account_id})
        generation = self.store.begin_session(requester.account_id)
        selected = self.store.select_character(
            requester.account_id, generation, requester.character_id
        )
        with self.assertRaises(ValueError):
            return_to_world(
                self.store,
                requester.account_id,
                requester.generation,
                result["character"],
                shared.runtime,
                struct.pack(">iB", shared.fight.id, 1),
                wp=6,
            )
        self.assertNotIn(requester.account_id, shared.returned)
        replacement = adapter.session(requester.account_id, generation, selected)
        saved = adapter.recover_withdrawn_pve(replacement)
        self.assertEqual(saved["hp"], result["character"]["hp"])
        self.assertNotIn(shared.fight.id, adapter.registry.fights)
        self.assertFalse(
            any(value == 7 for value in adapter.registry.by_character.values())
        )
        self.assertFalse(
            any(value == 7 for value in adapter.registry.by_actor.values())
        )
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT session_generation,returned_at FROM combat_pve_withdrawals "
                "WHERE fight_id=7 AND character_id=%s",
                (requester.character_id,),
            ).fetchone()
            self.assertEqual(receipt["session_generation"], generation)
            self.assertIsNotNone(receipt["returned_at"])

    def test_pending_native_barrier_survives_failed_abort_then_cancels_before_ko_disconnect(
        self,
    ):
        adapter, shared, requester, character, other, _ = self.fixture()
        shared.runtime.awaiting_ack = 17
        shared.ack.arm(17, (requester, other))
        shared.ack.accept(requester, struct.pack(">i", 17))
        with patch(
            "wakfu_server.fight_store._write_terminal_checkpoint",
            side_effect=ValueError("late checkpoint failure"),
        ):
            with self.assertRaisesRegex(ValueError, "late checkpoint failure"):
                prepare(self.store, adapter.registry, requester, character, b"")
        self.assertEqual(shared.ack.turn, 17)
        self.assertEqual(shared.ack.received, {requester.account_id})
        self.assertEqual(shared.runtime.awaiting_ack, 17)
        result = prepare(self.store, adapter.registry, requester, character, b"")
        self.assertTrue(result["applied"])
        self.assertIsNone(shared.ack.turn)
        self.assertEqual(shared.ack.expected, {})
        self.assertIsNone(shared.runtime.awaiting_ack)
        adapter.disconnect(other)
        self.assertEqual(shared.fight.phase, "finished")
        self.assertFalse(shared.runtime.abandon_returned)

    def test_requester_ack_failure_leaves_publication_retryable_until_durable_ack(self):
        adapter, shared, requester, character, other, _ = self.fixture()
        result = prepare(self.store, adapter.registry, requester, character, b"")
        receipt = shared.withdrawals[requester.account_id]
        with patch(
            "wakfu_server.combat_pve_withdraw_store.acknowledge",
            side_effect=ValueError("durable ACK failed"),
        ):
            with self.assertRaisesRegex(ValueError, "durable ACK failed"):
                self.requester_ack(adapter, shared, requester, result["character"])
        self.assertFalse(shared.runtime.abandon_returned)
        self.assertFalse(receipt["withdrawal"].private_runtime.abandon_returned)
        self.assertNotIn(requester.account_id, shared.returned)
        self.assertIn(requester.account_id, shared.connected)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT returned_at FROM combat_pve_withdrawals "
                "WHERE fight_id=%s AND character_id=%s",
                (shared.fight.id, requester.character_id),
            ).fetchone()
            self.assertIsNone(row["returned_at"])
        returned = self.requester_ack(adapter, shared, requester, result["character"])
        self.assertTrue(returned["packets"])
        self.assertNotIn(other.account_id, shared.returned)

    def test_requester_main_ko_with_living_owned_hero_publishes_committed_one_hp(self):
        from wakfu_server import health
        from wakfu_server.combat_lifecycle import outside_progression

        adapter, shared, requester, character, other, _ = self.fixture(
            requester_ko=True
        )
        self.assertEqual(shared.fight.actors[requester.character_id].hp, 0)
        result = prepare(self.store, adapter.registry, requester, character, b"")
        self.assertEqual(result["character"]["hp"], 0)
        returned = self.requester_ack(adapter, shared, requester, result["character"])
        saved = returned["character"]
        self.assertEqual(saved["hp"], 1)
        self.assertIn(
            (12436, health.packet(requester.character_id, 1, 1)), returned["packets"]
        )
        self.assertIn(outside_progression(saved, wp=6, ap=6, mp=3), returned["packets"])
        self.assertNotIn(
            (12436, health.packet(requester.character_id, 0, 0)), returned["packets"]
        )
        self.assertEqual(shared.fight.actors[requester.character_id].hp, 0)
        self.assertNotIn(other.account_id, shared.returned)

    def test_requester_ack_then_socket_disconnect_preserves_pending_ko_continuation(
        self,
    ):
        adapter, shared, requester, character, other, _ = self.fixture()
        result = prepare(self.store, adapter.registry, requester, character, b"")
        other_receipt = shared.withdrawals[other.account_id]
        other_batches = tuple(shared.outboxes[other.account_id])
        self.requester_ack(adapter, shared, requester, result["character"])
        self.assertIn(requester.account_id, shared.outboxes)
        self.assertFalse(shared.outboxes[requester.account_id])
        adapter.disconnect(requester)
        self.assertIs(adapter.registry.lookup(shared.fight.id), shared)
        self.assertIs(shared.withdrawals[other.account_id], other_receipt)
        self.assertEqual(tuple(shared.outboxes[other.account_id]), other_batches)
        self.assertNotIn(other.account_id, shared.returned)
        returned = adapter.return_withdrawn_pve(
            other,
            shared.fight.id,
            self.store.character(other.account_id, other.character_id),
            struct.pack(">iB", shared.fight.id, 1),
            wp=6,
        )
        self.assertTrue(returned["packets"])
        self.assertEqual(shared.returned, set(shared.participants))
        self.assertNotIn(shared.fight.id, adapter.registry.fights)
