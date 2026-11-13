"""Character selection resets expired weekly journal entries before projection."""
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.achievements import storage, service
from wakfu_server.objectives import environmental_recurring_storage as recurring
from wakfu_server.characters import heroes


class RecurringLoginReconciliationTests(PostgresCase):
    def test_selection_resets_four_expired_cycles_and_keeps_current_weekly_cycle(self):
        from test_guild_service_postgres import GuildServicePostgresTests

        owner = GuildServicePostgresTests._player(self, "Recurring Login Owner")
        with self.store.connection() as db:
            # This login regression does not depend on the unrelated item
            # catalog; keep the fixture's generated starter item out of scope.
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (owner["item"],))
            now_ms = db.execute(
                "SELECT floor(EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)*1000)::bigint AS now_ms"
            ).fetchone()["now_ms"]
            rules = list(
                db.execute(
                    "SELECT DISTINCT ON (definition_id) definition_id,version,anchor_ms,period_ms,objective_id "
                    "FROM recurring_hunter_contracts WHERE period_ms=604800000 "
                    "ORDER BY definition_id,version DESC LIMIT 5"
                )
            )
            self.assertEqual(len(rules), 5)
            old, active = rules[:4], rules[4]
            active_period = (now_ms - active["anchor_ms"]) // active["period_ms"]
            self.assertGreaterEqual(active_period, 1)
            state = storage.load_locked(db, owner["character"])
            identities = [row["definition_id"] for row in rules]
            objectives = [row["objective_id"] for row in rules]
            state["running"] = sorted(set(state["running"]) | set(identities))
            state["tracking"] = sorted(set(state["tracking"]) | set(identities))
            state["objectives"] = sorted(set(state["objectives"]) | set(objectives))
            storage.store(db, owner["character"], state)

            for row, period in [
                (rule, (now_ms - rule["anchor_ms"]) // rule["period_ms"] - 1)
                for rule in old
            ] + [(active, active_period)]:
                event_key = "reconnect-fixture:" + str(row["definition_id"])
                storage.record_event(
                    db, owner["character"], event_key, {"fixture": True}
                )
                db.execute(
                    "INSERT INTO recurring_hunter_acceptances "
                    "(character_id,definition_id,version,period_index,account_id,accepted_at_ms,real_level,acceptance_event_key) "
                    "VALUES(%s,%s,%s,%s,%s,%s,100,%s)",
                    (
                        owner["character"],
                        row["definition_id"],
                        row["version"],
                        period,
                        owner["account"],
                        row["anchor_ms"] + period * row["period_ms"],
                        event_key,
                    ),
                )

        generation = self.store.begin_session(
            owner["account"], previous_generation=owner["generation"]
        )
        with patch.object(
            recurring,
            "_load",
            side_effect=AssertionError("login must not revalidate rewards/catalog"),
        ):
            selected = self.store.select_character(
                owner["account"], generation, owner["character"]
            )
        with self.store.connection() as db:
            after = storage.load_locked(db, owner["character"])
            for row in old:
                identity = row["definition_id"]
                self.assertNotIn(identity, after["running"])
                self.assertNotIn(identity, after["tracking"])
                self.assertNotIn(row["objective_id"], after["objectives"])
                receipt = db.execute(
                    "SELECT expired_at_ms FROM recurring_hunter_acceptances "
                    "WHERE character_id=%s AND definition_id=%s",
                    (owner["character"], identity),
                ).fetchone()
                self.assertIsNotNone(receipt["expired_at_ms"])
            self.assertIn(active["definition_id"], after["running"])
            self.assertIn(active["definition_id"], after["tracking"])
            self.assertIsNone(
                db.execute(
                    "SELECT expired_at_ms FROM recurring_hunter_acceptances "
                    "WHERE character_id=%s AND definition_id=%s AND period_index=%s",
                    (owner["character"], active["definition_id"], active_period),
                ).fetchone()["expired_at_ms"]
            )
            projected = selected["achievement_section"]
            accepted_at = active["anchor_ms"] + active_period * active["period_ms"]
            self.assertIn(
                struct.pack(
                    ">iBBBBqB", active["definition_id"], 1, 0, 0, 1, accepted_at, 0
                ),
                projected,
            )
        self.assertTrue(selected)

    def test_owned_checkpoint_reconciles_main_and_active_hero_only_for_expired_cycles(
        self,
    ):
        from test_guild_service_postgres import GuildServicePostgresTests

        owner = GuildServicePostgresTests._player(self, "Recurring Company Owner")
        with self.store.connection() as db:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (owner["item"],))
        hero = self.store.create_character(owner["account"], "Recurring Company Hero")
        heroes.add(
            self.store,
            owner["account"],
            owner["generation"],
            owner["character"],
            hero["id"],
        )
        with self.store.connection() as db:
            now_ms = db.execute(
                "SELECT floor(EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)*1000)::bigint AS now_ms"
            ).fetchone()["now_ms"]
            contracts = list(
                db.execute(
                    "SELECT DISTINCT ON (definition_id) definition_id,version,anchor_ms,period_ms,objective_id "
                    "FROM recurring_hunter_contracts WHERE period_ms=604800000 "
                    "ORDER BY definition_id,version DESC LIMIT 6"
                )
            )
            self.assertEqual(len(contracts), 6)

            def seed(character_id, expired_contracts, current_contract):
                state = storage.load_locked(db, character_id)
                identities = [
                    row["definition_id"]
                    for row in expired_contracts + [current_contract]
                ]
                state["running"] = sorted(set(state["running"]) | set(identities))
                state["tracking"] = sorted(set(state["tracking"]) | set(identities))
                objectives = [
                    row["objective_id"]
                    for row in expired_contracts + [current_contract]
                ]
                state["objectives"] = sorted(set(state["objectives"]) | set(objectives))
                storage.store(db, character_id, state)
                entries = [
                    (row, (now_ms - row["anchor_ms"]) // row["period_ms"] - 1)
                    for row in expired_contracts
                ]
                entries.append(
                    (
                        current_contract,
                        (now_ms - current_contract["anchor_ms"])
                        // current_contract["period_ms"],
                    )
                )
                for row, period in entries:
                    event_key = (
                        f"company-reconnect:{character_id}:{row['definition_id']}"
                    )
                    storage.record_event(db, character_id, event_key, {"fixture": True})
                    db.execute(
                        "INSERT INTO recurring_hunter_acceptances "
                        "(character_id,definition_id,version,period_index,account_id,accepted_at_ms,real_level,acceptance_event_key) "
                        "VALUES(%s,%s,%s,%s,%s,%s,100,%s)",
                        (
                            character_id,
                            row["definition_id"],
                            row["version"],
                            period,
                            owner["account"],
                            row["anchor_ms"] + period * row["period_ms"],
                            event_key,
                        ),
                    )

            seed(owner["character"], contracts[:4], contracts[4])
            seed(hero["id"], contracts[:2], contracts[5])

        with patch.object(
            recurring,
            "_load",
            side_effect=AssertionError("expiry must not reload reward catalog"),
        ):
            boundary, packets = recurring.synchronize_owned(
                self.store,
                owner["account"],
                owner["generation"],
                owner["character"],
                include_company=True,
            )
        self.assertGreater(boundary, now_ms)
        expired = [(owner["character"], row) for row in contracts[:4]]
        expired += [(hero["id"], row) for row in contracts[:2]]
        resets = {
            (struct.unpack(">qi", body)[0], struct.unpack(">qi", body)[1])
            for opcode, body in packets
            if opcode == 13205
        }
        self.assertEqual(
            resets,
            {(character_id, row["definition_id"]) for character_id, row in expired},
        )
        untracks = {
            (struct.unpack(">qiB", body)[0], struct.unpack(">qiB", body)[1])
            for opcode, body in packets
            if opcode == 13371 and body[-1] == 0
        }
        self.assertEqual(
            untracks,
            {(character_id, row["definition_id"]) for character_id, row in expired},
        )
        for character_id, expired_rows, current in (
            (owner["character"], contracts[:4], contracts[4]),
            (hero["id"], contracts[:2], contracts[5]),
        ):
            with self.store.connection() as db:
                state = storage.load_locked(db, character_id)
                for row in expired_rows:
                    self.assertNotIn(row["definition_id"], state["running"])
                    self.assertNotIn(row["definition_id"], state["tracking"])
                    receipt = db.execute(
                        "SELECT expired_at_ms FROM recurring_hunter_acceptances "
                        "WHERE character_id=%s AND definition_id=%s",
                        (character_id, row["definition_id"]),
                    ).fetchone()
                    self.assertIsNotNone(receipt["expired_at_ms"])
                self.assertIn(current["definition_id"], state["running"])
                self.assertIn(current["definition_id"], state["tracking"])
                projected = service.snapshot(db, character_id)
                period = (now_ms - current["anchor_ms"]) // current["period_ms"]
                accepted_at = current["anchor_ms"] + period * current["period_ms"]
                self.assertIn(
                    struct.pack(
                        ">iBBBBqB", current["definition_id"], 1, 0, 0, 1, accepted_at, 0
                    ),
                    projected,
                )


if __name__ == "__main__":
    unittest.main()
