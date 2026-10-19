"""Receipt-fenced dead exploration return; combat corpses stay untouched."""
from dataclasses import replace
import struct
from unittest.mock import patch
from postgres_case import PostgresCase
import test_combat_pve_withdraw as withdrawal_fixture
from wakfu_server import health_store, health_policy, health
from wakfu_server.combat_state import Actor
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_pve_withdraw_store import acknowledge, recover_pending


class WithdrawalHealthReturnTests(PostgresCase):
    def withdrawn(self, *, hero=False):
        values = withdrawal_fixture.WithdrawalPostgresTests.state(self)
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *other,
        ) = values
        # The public trusted damage API requires the actual source turn.
        # Advance the real FSM instead of rewriting current/order or using a
        # reaction-only API to bypass ordinary damage source validation.
        for _ in range(len(fight.actors) * 2):
            if fight.current.id == -200:
                break
            current = fight.current
            if current.controlled:
                fight.end_turn(current.owner_id, current.id, current.turn_count)
            else:
                fight.end_server_turn(current.id, fight.turn_id)
        self.assertEqual(fight.current.id, -200)
        hero_character = None
        if hero:
            hero_character = store.create_character(account, "Return Hero")
            actor = Actor(
                hero_character["id"],
                0,
                (3, 0, 0),
                hero_character["hp"],
                6,
                3,
                80,
                hero_character["level"],
                account,
                True,
                max_hp=hero_character["max_hp"],
            )
            fight.walkable.add(actor.position)
            fight.placement[0].add(actor.position)
            fight.actors[actor.id] = actor
            adapter.registry.by_character[actor.id] = fight.id
            adapter.registry.by_actor[actor.id] = fight.id
            with store.connection() as db:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                    (fight.id, actor.id, account, generation),
                )
            fight.apply_damage(-200, actor.id, actor.hp)
        actor = fight.actors[character["id"]]
        fight.apply_damage(-200, actor.id, actor.hp)
        self.assertEqual(fight.phase, "active")
        self.assertEqual(actor.hp, 0)
        receipt = adapter.withdraw_pve(owner, character, b"")
        self.assertEqual(receipt["character"]["hp"], 0)
        self.assertTrue(receipt["character"]["health_dead"])
        return values, receipt, hero_character

    def test_dead_ack_recovers_committed_health_packets_regeneration_and_preserves_active_corpse(
        self,
    ):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        corpse = shared.fight.actors[character["id"]]
        ledger = corpse.state_ledger
        before = snapshot(shared.fight)
        from wakfu_server import combat_abandon

        actual_return = combat_abandon.return_to_world
        prior = []

        def observe_return(*args, **kwargs):
            result = actual_return(*args, **kwargs)
            prior.extend(result["packets"])
            return result

        with patch.object(
            combat_abandon, "return_to_world", side_effect=observe_return
        ):
            returned = adapter.return_withdrawn_pve(
                owner,
                fight.id,
                receipt["character"],
                struct.pack(">iB", fight.id, 1),
                wp=6,
            )
        # Every actor's format17/FOR_PHOENIX teardown must remain byte-exact;
        # sharing opcode13046 does not make it the selected fmt3 HP refresh.
        old_teardown = [
            packet
            for packet in prior
            if packet[0] == 13046 and packet[1][10:11] == b"\x11"
        ]
        self.assertTrue(old_teardown)
        self.assertEqual(
            [
                packet
                for packet in returned["packets"]
                if packet[0] == 13046 and packet[1][10:11] == b"\x11"
            ],
            old_teardown,
        )
        self.assertEqual(returned["character"]["hp"], 1)
        self.assertFalse(returned["character"]["health_dead"])
        hp_packets = [
            payload for opcode, payload in returned["packets"] if opcode == 12436
        ]
        self.assertEqual(
            hp_packets,
            [
                struct.pack(
                    ">qii",
                    character["id"],
                    1,
                    health.exploration_coefficient(returned["character"]["max_hp"], 1),
                )
            ],
        )
        self.assertIs(shared.fight.actors[character["id"]], corpse)
        self.assertIs(corpse.state_ledger, ledger)
        self.assertEqual(snapshot(shared.fight), before)
        self.assertEqual(shared.fight.phase, "active")
        self.assertEqual(fight.actors[character["id"]].hp, 0)
        with store.connection() as db:
            row = db.execute(
                "SELECT reason,return_acknowledged_at FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                (fight.id, character["id"]),
            ).fetchone()
            self.assertEqual(row["reason"], "abort")
            self.assertIsNone(row["return_acknowledged_at"])
            self.assertIsNotNone(
                db.execute(
                    "SELECT health_returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["health_returned_at"]
            )
        store.clock = lambda: 1005
        maximum = store.character(account, character["id"])["max_hp"]
        coefficient = health.exploration_coefficient(maximum, 1)
        self.assertEqual(
            health_store.tick(store, account, generation, character["id"], 1)["hp"],
            health.regenerated(1, maximum, 5000, coefficient),
        )

    def test_duplicate_ack_does_not_reverse_later_world_death_or_restart_regeneration(
        self,
    ):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        acknowledge(store, owner, fight.id)
        store.clock = lambda: 1005
        health_store.sync(
            store, account, generation, character["id"], 1, 0, coefficient=0
        )
        before = store.character(account, character["id"])
        with store.connection() as db:
            baseline = dict(
                db.execute(
                    "SELECT * FROM character_regeneration WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()
            )
        self.assertEqual(acknowledge(store, owner, fight.id)["hp"], 0)
        self.assertEqual(store.character(account, character["id"]), before)
        with store.connection() as db:
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM character_regeneration WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone()
                ),
                baseline,
            )

    def test_replacement_lease_completes_interrupted_dead_return_once(self):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        new = store.begin_session(account)
        selected = store.select_character(account, new, character["id"])
        session = replace(owner, generation=new)
        result = recover_pending(store, session)
        self.assertEqual(result["hp"], 1)
        self.assertFalse(result["health_dead"])
        self.assertIsNone(recover_pending(store, session))
        self.assertEqual(shared.fight.actors[character["id"]].hp, 0)

    def test_historical_already_returned_dead_exit_can_complete_only_unchanged_baseline(
        self,
    ):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=%s WHERE fight_id=%s",
                (store.now(), fight.id),
            )
        result = recover_pending(store, owner)
        self.assertEqual(result["hp"], 1)
        self.assertIsNone(recover_pending(store, owner))

    def test_historical_changed_dead_baseline_is_not_discovered_or_healed(self):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=%s WHERE fight_id=%s",
                (store.now(), fight.id),
            )
        store.clock = lambda: 1005
        health_store.initialize(
            store, account, generation, character["id"], coefficient=0
        )
        self.assertIsNone(recover_pending(store, owner))
        with self.assertRaisesRegex(ValueError, "exit baseline"):
            acknowledge(store, owner, fight.id)
        self.assertEqual(store.character(account, character["id"])["hp"], 0)

    def test_all_owned_dead_heroes_recover_without_touching_foreign_owner(self):
        values, receipt, hero = self.withdrawn(hero=True)
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            other_account,
            other_generation,
            other,
        ) = values
        foreign = store.character(other_account, other["id"])
        acknowledge(store, owner, fight.id)
        for identity in (character["id"], hero["id"]):
            saved = store.character(account, identity)
            self.assertEqual(saved["hp"], 1)
            self.assertFalse(saved["health_dead"])
            self.assertEqual(shared.fight.actors[identity].hp, 0)
        self.assertEqual(store.character(other_account, other["id"]), foreign)
        self.assertEqual(shared.fight.phase, "active")

    def test_health_recovery_failure_rolls_back_receipt_and_hp_together(self):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        real = health_policy.apply_damage

        def fail_after_write(*args, **kwargs):
            real(*args, **kwargs)
            raise RuntimeError("after owned recovery")

        with patch.object(health_policy, "apply_damage", side_effect=fail_after_write):
            with self.assertRaisesRegex(RuntimeError, "after owned recovery"):
                acknowledge(store, owner, fight.id)
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        with store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["returned_at"]
            )
            self.assertIsNone(
                db.execute(
                    "SELECT return_acknowledged_at FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["return_acknowledged_at"]
            )
            self.assertIsNone(
                db.execute(
                    "SELECT health_returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["health_returned_at"]
            )

    def test_foreign_or_replaced_lease_cannot_complete_health_return(self):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with self.assertRaises(ValueError):
            acknowledge(store, replace(owner, account_id=999), fight.id)
        store.begin_session(account)
        with self.assertRaises(ValueError):
            acknowledge(store, owner, fight.id)
        self.assertEqual(store.character(account, character["id"])["hp"], 0)

    def test_obsolete_historical_receipt_does_not_block_new_death_or_live_fight(self):
        # Each subcase needs its own isolated schema/owner because the earlier
        # fixture registers fixed usernames. Separate transactions below reuse
        # one historical receipt while adding/removing only the later guard.
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=%s WHERE fight_id=%s",
                (store.now(), fight.id),
            )
            other_fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                (other_fight, character["id"], account, generation),
            )
            # Deliberately retain the old matching regeneration baseline so
            # this tests the newer durable-exit exclusion itself.
            db.execute(
                "INSERT INTO fight_health_exits(fight_id,character_id,generation,reason,created_at) VALUES(%s,%s,%s,'abort',%s)",
                (other_fight, character["id"], generation, store.now()),
            )
        self.assertIsNone(recover_pending(store, owner))
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        with store.connection() as db:
            db.execute(
                "DELETE FROM fight_health_exits WHERE fight_id=%s", (other_fight,)
            )
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (other_fight,)
            )
        self.assertIsNone(recover_pending(store, owner))
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        with store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT return_acknowledged_at FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["return_acknowledged_at"]
            )
            self.assertIsNone(
                db.execute(
                    "SELECT health_returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["health_returned_at"]
            )

    def test_original_abort_ack_constraint_and_withdrawal_return_constraint_remain_enforced(
        self,
    ):
        from psycopg.errors import CheckViolation

        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with self.assertRaises(CheckViolation), store.connection() as db:
            db.execute(
                "UPDATE fight_health_exits SET return_acknowledged_at=%s WHERE fight_id=%s AND character_id=%s",
                (store.now(), fight.id, character["id"]),
            )
        with self.assertRaises(CheckViolation), store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET health_returned_at=%s WHERE fight_id=%s AND character_id=%s",
                (store.now(), fight.id, character["id"]),
            )
        self.assertEqual(store.character(account, character["id"])["hp"], 0)

    def test_pre190_historical_returned_dead_row_upgrades_without_backfill_then_recovers_owned(
        self,
    ):
        from pathlib import Path
        from wakfu_server.paths import PROJECT_ROOT

        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with store.connection() as db:
            # Remove only the new additive schema while all prior migrations,
            # original abort receipt and actual dead-exit data remain intact.
            db.execute(
                "ALTER TABLE combat_pve_withdrawals DROP CONSTRAINT pve_withdrawal_health_requires_return"
            )
            db.execute(
                "ALTER TABLE combat_pve_withdrawals DROP COLUMN health_returned_at"
            )
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=%s WHERE fight_id=%s",
                (store.now(), fight.id),
            )
            db.execute(
                (
                    PROJECT_ROOT
                    / "server/migrations/190_pve_withdrawal_health_returns.sql"
                ).read_text()
            )
            row = db.execute(
                "SELECT returned_at,health_returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                (fight.id, character["id"]),
            ).fetchone()
            self.assertIsNotNone(row["returned_at"])
            self.assertIsNone(row["health_returned_at"])
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        self.assertEqual(recover_pending(store, owner)["hp"], 1)
        self.assertIsNone(recover_pending(store, owner))
        with store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT return_acknowledged_at FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["return_acknowledged_at"]
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT health_returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["health_returned_at"]
            )
