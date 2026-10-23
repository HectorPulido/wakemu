"""Custom national policy through durable actions and native hourly settlement."""
from unittest.mock import patch
import struct

from wakfu_server import national_earnings as earnings, personal_ecology, nation_state
from wakfu_server import national_progression as national
from test_national_progression_postgres import NationalProgressionPostgresTests
from test_objectives_hourly_pvp_postgres import ObjectivesHourlyPvpPostgresTests


class NationalEcologyEarningsTests(NationalProgressionPostgresTests):
    def test_live_ecological_receipts_earn_signed_citizenship_and_unlock_equipment(
        self,
    ):
        account, generation, owner = self._owner(245)
        owner = nation_state.enroll(
            self.store,
            account,
            generation,
            owner["id"],
            struct.pack(">i", 30) + bytes(2),
        )
        with self.store.connection() as db:
            # A legacy character has no invented native constructor history.
            db.execute(
                "DELETE FROM character_national_authority WHERE character_id=%s",
                (owner["id"],),
            )
            db.execute(
                "UPDATE characters SET ecology_value=9900 WHERE id=%s", (owner["id"],)
            )
        evidence = dict(
            managed_equilibrium=True,
            kind="plant",
            action="plant",
            distance_before=1,
            distance_after=0,
            map_id=527,
            region_id=17,
        )
        for index in range(50):
            with self.store.connection() as db:
                self.store.lock_character(db, account, generation, owner["id"])
                result = personal_ecology.apply(
                    db,
                    owner["id"],
                    operation="actual-plant:" + str(index),
                    delta=1,
                    evidence=evidence,
                    national_action=True,
                )
                self.assertFalse(result["duplicate"])
        loaded = self.reopen().character(account, owner["id"])
        current = national.owned_snapshot(loaded)
        self.assertEqual(
            (current.provenance, dict(current.crime_scores)[30]),
            ("wakemu_policy_epoch", 500),
        )
        # The ecological gauge is already saturated, but confirmed improvement
        # still earns the separate custom currency. It is never copied to CP.
        self.assertEqual(loaded["ecology_value"], 9900)
        item = self._grant(account, generation, loaded, 9728, 0)
        saved = self._save(account, generation, loaded, item)
        self._save(account, generation, saved)
        with self.store.connection() as db:
            repeat = personal_ecology.apply(
                db,
                owner["id"],
                operation="actual-plant:0",
                delta=1,
                evidence=evidence,
                national_action=True,
            )
            self.assertTrue(repeat["duplicate"])
            # Administrative reconciliation and renewable harvest give no CP.
            personal_ecology.apply(
                db, owner["id"], operation="repair", delta=1, evidence=evidence
            )
            personal_ecology.apply(
                db,
                owner["id"],
                operation="renewable",
                delta=0,
                evidence=dict(evidence, action="harvest"),
                national_action=True,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_national_earning_receipts"
                ).fetchone()["n"],
                50,
            )
        harmful = dict(evidence, distance_before=0, distance_after=1, action="remove")
        for index in range(57):
            with self.store.connection() as db:
                personal_ecology.apply(
                    db,
                    owner["id"],
                    operation="actual-remove:" + str(index),
                    delta=-1,
                    evidence=harmful,
                    national_action=True,
                )
        loaded = self.reopen().character(account, owner["id"])
        self.assertEqual(dict(national.owned_snapshot(loaded).crime_scores)[30], -70)
        item = self._grant(account, generation, loaded, 10040, 1)
        self._save(account, generation, loaded, item)
        with self.assertRaisesRegex(Exception, "append-only"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE wakemu_national_earning_policies SET ecology_gain=1000"
                )
        # A rolled-back ecological action must leave both ledgers untouched.
        with self.assertRaisesRegex(ValueError, "rollback fixture"):
            with self.store.connection() as db:
                personal_ecology.apply(
                    db,
                    owner["id"],
                    operation="rollback",
                    delta=1,
                    evidence=evidence,
                    national_action=True,
                )
                raise ValueError("rollback fixture")
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM personal_ecology_receipts WHERE operation='rollback'"
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_national_earning_receipts"
                ).fetchone()["n"],
                107,
            )

    def test_neutral_history_is_not_backfilled_and_custom_caps_preserve_imported_values(
        self,
    ):
        account, generation, owner = self._owner(100)
        evidence = dict(
            managed_equilibrium=True,
            kind="plant",
            action="plant",
            distance_before=1,
            distance_after=0,
        )
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM character_national_authority WHERE character_id=%s",
                (owner["id"],),
            )
            personal_ecology.apply(
                db,
                owner["id"],
                operation="before-enrollment",
                delta=1,
                evidence=evidence,
                national_action=True,
            )
            self.assertIsNone(
                db.execute("SELECT 1 FROM character_national_authority").fetchone()
            )
        owner = nation_state.enroll(
            self.store,
            account,
            generation,
            owner["id"],
            struct.pack(">i", 30) + bytes(2),
        )
        with self.store.connection() as db:
            self.assertTrue(
                personal_ecology.apply(
                    db,
                    owner["id"],
                    operation="before-enrollment",
                    delta=1,
                    evidence=evidence,
                    national_action=True,
                )["duplicate"]
            )
            self.assertIsNone(
                db.execute("SELECT 1 FROM character_national_authority").fetchone()
            )
        imported = self.imported(account, owner, score=5000)
        self.restore(account, generation, owner, imported, "real-import")
        with self.store.connection() as db:
            personal_ecology.apply(
                db,
                owner["id"],
                operation="capped-improve",
                delta=1,
                evidence=evidence,
                national_action=True,
            )
            self.assertEqual(
                db.execute(
                    "SELECT score FROM character_national_crime_scores WHERE nation_id=30"
                ).fetchone()["score"],
                5000,
            )
            personal_ecology.apply(
                db,
                owner["id"],
                operation="damaging-action",
                delta=-1,
                evidence=dict(evidence, distance_before=0, distance_after=1),
                national_action=True,
            )
            self.assertEqual(
                db.execute(
                    "SELECT score FROM character_national_crime_scores WHERE nation_id=30"
                ).fetchone()["score"],
                4990,
            )
            db.execute(
                "INSERT INTO character_national_merit VALUES(%s,%s,%s,15000,7)",
                (owner["id"], account, earnings.POLICY),
            )
        self.assertTrue(
            self.restore(
                account,
                generation,
                owner,
                self.imported(account, owner, score=500, rank=3),
                "later-native-import",
            )
        )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute("SELECT 1 FROM character_national_merit").fetchone()
            )
        self.assertEqual(
            national.owned_snapshot(self.store.character(account, owner["id"])).rank_id,
            3,
        )


class NationalHourlyEarningsTests(ObjectivesHourlyPvpPostgresTests):
    def test_real_hourly_settlement_changes_merit_and_rank_once(self):
        original = earnings.hourly_pvp
        observed = []

        def qualify(db, event_id, *, fight=None):
            event = db.execute(
                "SELECT * FROM objectives_pvp_events WHERE id=%s", (event_id,)
            ).fetchone()
            winner, loser = event["winner_character_id"], next(
                cid
                for cid in (event["first_character_id"], event["second_character_id"])
                if cid != event["winner_character_id"]
            )
            for cid in (winner, loser):
                db.execute("INSERT INTO character_chat_nations VALUES(%s,30)", (cid,))
                account = db.execute(
                    "SELECT account_id FROM characters WHERE id=%s", (cid,)
                ).fetchone()["account_id"]
                db.execute(
                    "INSERT INTO character_national_merit VALUES(%s,%s,%s,%s,0)",
                    (cid, account, earnings.POLICY, 1990 if cid == winner else 2000),
                )
                db.execute(
                    "UPDATE character_national_authority SET rank_id=%s WHERE character_id=%s",
                    (0 if cid == winner else 1, cid),
                )
            self.assertEqual(set(original(db, event_id, fight=fight)), {winner, loser})
            self.assertEqual(original(db, event_id, fight=fight), ())
            with patch.object(
                __import__("wakfu_server.objectives.pvp", fromlist=["_native_roster"]),
                "_native_roster",
                return_value=[],
            ):
                with self.assertRaisesRegex(ValueError, "roster/outcome"):
                    original(db, event_id, fight=fight)
            observed.append((winner, loser))

        with patch.object(earnings, "hourly_pvp", side_effect=qualify):
            super().test_only_durable_defeat_outcome_binds_and_awards_both_accounts_once()
        self.assertEqual(len(observed), 1)
        winner, loser = observed[0]
        with self.context.store.connection() as db:
            merits = {
                row["character_id"]: row["merit"]
                for row in db.execute(
                    "SELECT * FROM character_national_merit"
                ).fetchall()
            }
            ranks = {
                row["character_id"]: row["rank_id"]
                for row in db.execute(
                    "SELECT * FROM character_national_authority"
                ).fetchall()
            }
            self.assertEqual((merits[winner], merits[loser]), (2090, 1950))
            self.assertEqual((ranks[winner], ranks[loser]), (1, 0))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_national_earning_receipts"
                ).fetchone()["n"],
                2,
            )

    def test_absolute_publication_retries_and_fences_replaced_selected_session(self):
        from wakfu_server.national_publication import SelectedNationalProgression

        context = self.context
        publisher = SelectedNationalProgression()
        deliveries = []
        publish = lambda saved: deliveries.append(saved) or True
        self.assertFalse(
            publisher.refresh(
                context.store,
                context.account_a,
                context.generation_a,
                context.char_a["id"],
                publish=lambda saved: False,
            )
        )
        self.assertTrue(
            publisher.refresh(
                context.store,
                context.account_a,
                context.generation_a,
                context.char_a["id"],
                publish=publish,
            )
        )
        self.assertFalse(
            publisher.refresh(
                context.store,
                context.account_a,
                context.generation_a,
                context.char_a["id"],
                publish=publish,
            )
        )
        with context.store.connection() as db:
            db.execute(
                "UPDATE character_national_authority SET revision=revision+1 WHERE character_id=%s",
                (context.char_a["id"],),
            )
        self.assertTrue(
            publisher.refresh(
                context.store,
                context.account_a,
                context.generation_a,
                context.char_a["id"],
                publish=publish,
            )
        )
        self.assertEqual(len(deliveries), 2)
        with self.assertRaisesRegex(ValueError, "replaced session"):
            publisher.refresh(
                context.store,
                context.account_a,
                "stale-session",
                context.char_a["id"],
                publish=publish,
            )
        self.assertEqual(len(deliveries), 2)


from test_neutrality_item_actions import NeutralityItemPostgresTests
from test_flora_ecology_integration import FloraEcologyIntegrationTests
from test_monster_birth_ecology import MonsterBirthEcologyTests
from test_monster_removal_ecology import MonsterRemovalEcologyTests


class NationalNeutralityEarningsTests(NeutralityItemPostgresTests):
    def test_each_real_scroll_clears_scores_and_only_modern_scroll_resets_custom_merit(
        self,
    ):
        from wakfu_server import neutrality_item_actions as actions

        account, generation, owner = self.fixture()
        for slot, plan in enumerate(actions.descriptors()["items"]):
            nation_state.enroll(
                self.store,
                account,
                generation,
                owner["id"],
                struct.pack(">i", 30) + bytes(2),
            )
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO character_national_crime_scores VALUES(%s,%s,30,500)",
                    (owner["id"], account),
                )
                db.execute(
                    "UPDATE character_national_authority SET rank_id=7 WHERE character_id=%s",
                    (owner["id"],),
                )
                db.execute(
                    "INSERT INTO character_national_merit VALUES(%s,%s,%s,14000,7) "
                    "ON CONFLICT(character_id) DO UPDATE SET merit=14000",
                    (owner["id"], account, earnings.POLICY),
                )
            item = self.give(account, generation, owner, plan["item_ref"], slot)
            result = actions.use(
                self.store,
                account,
                generation,
                owner["id"],
                self.body(item),
                in_fight=False,
            )
            snapshot = national.owned_snapshot(result["character"])
            self.assertEqual((snapshot.nation_id, snapshot.crime_scores), (0, ()))
            self.assertEqual(snapshot.rank_id, 0 if plan["item_ref"] == 24836 else 7)
            with self.store.connection() as db:
                merit = db.execute(
                    "SELECT merit FROM character_national_merit WHERE character_id=%s",
                    (owner["id"],),
                ).fetchone()
                self.assertEqual(
                    None if merit is None else merit["merit"],
                    None if plan["item_ref"] == 24836 else 14000,
                )


class NationalFloraProducerTests(FloraEcologyIntegrationTests):
    def test_actual_flora_equilibrium_actions_award_once_without_changing_ecology_packets(
        self,
    ):
        nation_state.enroll(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">i", 30) + bytes(2),
        )
        super().test_plant_improving_population_balance_then_worsening_population_stasis()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT score FROM character_national_crime_scores"
                ).fetchone()["score"],
                0,
            )
            rows = db.execute(
                "SELECT requested_delta FROM character_national_earning_receipts ORDER BY source_key"
            ).fetchall()
            self.assertEqual(sorted(row["requested_delta"] for row in rows), [-10, 10])


class NationalBirthProducerTests(MonsterBirthEcologyTests):
    def _new_birth(self, *args, **kwargs):
        birth = super()._new_birth(*args, **kwargs)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_chat_nations VALUES(%s,30)",
                (birth["character_id"],),
            )
        return birth

    def test_actual_birth_is_credited_once_to_the_planter(self):
        super().test_birth_registers_group_and_ecology_in_callers_transaction_once()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT score FROM character_national_crime_scores"
                ).fetchone()["score"],
                10,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_national_earning_receipts"
                ).fetchone()["n"],
                1,
            )


class NationalRemovalProducerTests(MonsterRemovalEcologyTests):
    def test_actual_group_removal_uses_verified_population_and_lease(self):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_chat_nations VALUES(%s,30)",
                (self.character["id"],),
            )
        super().test_overpopulation_removal_awards_balance_with_owner_absolute_packet_and_info()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT score FROM character_national_crime_scores"
                ).fetchone()["score"],
                10,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_national_earning_receipts"
                ).fetchone()["n"],
                1,
            )
