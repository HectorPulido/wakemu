from concurrent.futures import ThreadPoolExecutor
import threading
import uuid
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.errors import RaiseException
from psycopg.types.json import Jsonb

from wakfu_server import player_exchanges
from wakfu_server.inventory_items import grant
from wakfu_server.wire import proto_field


class PlayerExchangeInvitationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = 2_000_000_000.0
        self.store.clock = lambda: self.now

    def player(self, label):
        account = self.store.register(
            f"x{uuid.uuid4().hex[:12]}", "exchange-test-password"
        )["id"]
        letters = str.maketrans("0123456789", "abcdefghij")
        name = "Hero" + uuid.uuid4().hex[:8].translate(letters)
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        return {"account": account, "generation": generation, "character": character}

    def durable_fight(self, participant, status):
        from wakfu_server.combat import fight_store

        fight_id = fight_store.create(
            self.store,
            participant["account"],
            participant["generation"],
            participant["character"]["id"],
        )
        if status == "active":
            fight_store.activate(
                self.store,
                participant["account"],
                participant["generation"],
                participant["character"]["id"],
                fight_id,
            )
        elif status != "placement":
            raise ValueError("Test helper expects a live fight status")
        return fight_id

    def invite(self, inviter, invitee):
        return player_exchanges.invite(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            invitee["character"]["id"],
        )

    def active_exchange(self, inviter, invitee):
        exchange = self.invite(inviter, invitee)
        return player_exchanges.answer(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            exchange["id"],
            True,
        )

    def publish_current(self, exchange, *participants):
        revision = self.fetchone(
            "SELECT revision FROM player_exchanges WHERE id=%s", (exchange["id"],)
        )["revision"]
        for participant in participants:
            player_exchanges.published(
                self.store,
                participant["account"],
                participant["generation"],
                participant["character"]["id"],
                exchange["id"],
                revision,
            )
        return revision

    def inventory_rows(self, *participants):
        identities = tuple(sorted(p["character"]["id"] for p in participants))
        return self.fetchall(
            "SELECT uid,character_id,reference,quantity,container,slot "
            "FROM inventory_items WHERE character_id=ANY(%s) ORDER BY uid",
            (list(identities),),
        )

    def set_wallets(self, *values):
        with self.store.connection() as db:
            for participant, amount in values:
                db.execute(
                    "UPDATE account_wallets SET kamas=%s WHERE account_id=%s",
                    (amount, participant["account"]),
                )

    def grant_item(self, owner, reference, quantity=1, slot=0, kind=0):
        container = self.fetchone(
            "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=%s",
            (owner["character"]["id"], kind),
        )["uid"]
        return grant(
            self.store,
            owner["account"],
            owner["generation"],
            owner["character"]["id"],
            reference=reference,
            quantity=quantity,
            container=container,
            slot=slot,
            allowed_references={reference},
        )

    def fetchone(self, statement, params=()):
        with self.store.connection() as db:
            return db.execute(statement, params).fetchone()

    def fetchall(self, statement, params=()):
        with self.store.connection() as db:
            return db.execute(statement, params).fetchall()

    def test_invitation_owns_both_current_sessions_and_publishes_pair_snapshots(self):
        inviter, invitee = self.player("inviter"), self.player("invitee")

        exchange = self.invite(inviter, invitee)

        self.assertEqual("invitation", exchange["state"])
        self.assertEqual(1, exchange["revision"])
        self.assertEqual(self.store.now(60), exchange["expires_at"])
        members = self.fetchall(
            "SELECT character_id FROM player_exchange_members WHERE exchange_id=%s "
            "ORDER BY character_id",
            (exchange["id"],),
        )
        self.assertEqual(
            sorted((inviter["character"]["id"], invitee["character"]["id"])),
            [row["character_id"] for row in members],
        )
        notices = self.fetchall(
            "SELECT character_id,generation,event,payload FROM player_exchange_outbox "
            "WHERE exchange_id=%s ORDER BY character_id",
            (exchange["id"],),
        )
        self.assertEqual(2, len(notices))
        self.assertEqual({"snapshot"}, {row["event"] for row in notices})
        self.assertEqual(
            {inviter["generation"], invitee["generation"]},
            {row["generation"] for row in notices},
        )
        self.assertTrue(all(row["payload"]["state"] == "invitation" for row in notices))

    def test_accept_and_decline_are_owned_and_stale_or_replayed_answers_do_not_mutate(
        self,
    ):
        inviter, invitee = self.player("acceptor"), self.player("recipient")
        exchange = self.invite(inviter, invitee)

        with self.assertRaisesRegex(ValueError, "owned"):
            player_exchanges.answer(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                True,
            )
        with self.assertRaisesRegex(ValueError, "owned"):
            player_exchanges.answer(
                self.store,
                invitee["account"],
                "stale-generation",
                invitee["character"]["id"],
                exchange["id"],
                True,
            )
        accepted = player_exchanges.answer(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            exchange["id"],
            True,
        )
        self.assertEqual(("active", 2), (accepted["state"], accepted["revision"]))
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_members WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        with self.assertRaisesRegex(ValueError, "already answered"):
            player_exchanges.answer(
                self.store,
                invitee["account"],
                invitee["generation"],
                invitee["character"]["id"],
                exchange["id"],
                False,
            )
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_outbox "
                "WHERE exchange_id=%s AND revision=2 AND event='snapshot'",
                (exchange["id"],),
            )["n"],
        )

        inviter2, invitee2 = self.player("decliner"), self.player("target")
        canceled = self.invite(inviter2, invitee2)
        result = player_exchanges.answer(
            self.store,
            invitee2["account"],
            invitee2["generation"],
            invitee2["character"]["id"],
            canceled["id"],
            False,
        )
        self.assertEqual(("canceled", 2), (result["state"], result["revision"]))
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_members WHERE exchange_id=%s",
                (canceled["id"],),
            )["n"],
        )
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_outbox "
                "WHERE exchange_id=%s AND revision=2 AND event='canceled'",
                (canceled["id"],),
            )["n"],
        )

    def test_stale_or_busy_inviter_target_and_invalid_policy_do_not_create_exchange(
        self,
    ):
        inviter, target, other = (
            self.player("staleleader"),
            self.player("target"),
            self.player("other"),
        )
        with self.assertRaisesRegex(ValueError, "stale or offline"):
            player_exchanges.invite(
                self.store,
                inviter["account"],
                "old-generation",
                inviter["character"]["id"],
                target["character"]["id"],
            )
        with self.assertRaisesRegex(ValueError, "target is offline"):
            player_exchanges.invite(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                9223372036854770000,
            )

        existing = self.invite(inviter, target)
        with self.assertRaisesRegex(ValueError, "busy"):
            player_exchanges.invite(
                self.store,
                other["account"],
                other["generation"],
                other["character"]["id"],
                target["character"]["id"],
            )
        self.assertEqual(
            1, self.fetchone("SELECT count(*) AS n FROM player_exchanges")["n"]
        )
        self.assertEqual(
            "invitation",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (existing["id"],)
            )["state"],
        )

        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='player_exchange_policy'",
                (
                    Jsonb(
                        {
                            "version": True,
                            "invitation_seconds": 60,
                            "maximum_offer_items": 128,
                        }
                    ),
                ),
            )
        free = self.player("free")
        with self.assertRaisesRegex(ValueError, "policy"):
            player_exchanges.invite(
                self.store,
                other["account"],
                other["generation"],
                other["character"]["id"],
                free["character"]["id"],
            )
        self.assertEqual(
            1, self.fetchone("SELECT count(*) AS n FROM player_exchanges")["n"]
        )

    def test_invitation_rejects_either_participant_with_durable_live_fight(self):
        for status in ("placement", "active"):
            for fighting_side in ("inviter", "invitee"):
                with self.subTest(status=status, fighting_side=fighting_side):
                    inviter = self.player(f"fight-invite-a-{status}-{fighting_side}")
                    invitee = self.player(f"fight-invite-b-{status}-{fighting_side}")
                    fighter = inviter if fighting_side == "inviter" else invitee
                    fight_id = self.durable_fight(fighter, status)

                    with self.assertRaises(ValueError):
                        self.invite(inviter, invitee)

                    self.assertEqual(
                        0,
                        self.fetchone("SELECT count(*) AS n FROM player_exchanges")[
                            "n"
                        ],
                    )
                    self.assertEqual(
                        0,
                        self.fetchone(
                            "SELECT count(*) AS n FROM player_exchange_members"
                        )["n"],
                    )
                    self.assertEqual(
                        status,
                        self.fetchone(
                            "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
                        )["status"],
                    )

    def test_confirmation_rejects_live_fight_without_mutating_offer_or_receipt(self):
        for status in ("placement", "active"):
            for fighting_side in ("inviter", "invitee"):
                with self.subTest(status=status, fighting_side=fighting_side):
                    inviter = self.player(f"fight-confirm-a-{status}-{fighting_side}")
                    invitee = self.player(f"fight-confirm-b-{status}-{fighting_side}")
                    exchange = self.active_exchange(inviter, invitee)
                    item = self.grant_item(inviter, 12)
                    player_exchanges.offer_item(
                        self.store,
                        inviter["account"],
                        inviter["generation"],
                        inviter["character"]["id"],
                        exchange["id"],
                        item["uid"],
                        1,
                    )
                    self.publish_current(exchange, inviter, invitee)
                    fighter = inviter if fighting_side == "inviter" else invitee
                    self.durable_fight(fighter, status)
                    inventory_before = self.inventory_rows(inviter, invitee)
                    revision = self.fetchone(
                        "SELECT revision FROM player_exchanges WHERE id=%s",
                        (exchange["id"],),
                    )["revision"]
                    confirmer = invitee if fighting_side == "inviter" else inviter

                    with self.assertRaises(ValueError):
                        player_exchanges.confirm(
                            self.store,
                            confirmer["account"],
                            confirmer["generation"],
                            confirmer["character"]["id"],
                            exchange["id"],
                        )

                    row = self.fetchone(
                        "SELECT state,revision FROM player_exchanges WHERE id=%s",
                        (exchange["id"],),
                    )
                    self.assertEqual(
                        ("active", revision), (row["state"], row["revision"])
                    )
                    self.assertEqual(
                        [None, None],
                        [
                            member["confirmed_revision"]
                            for member in self.fetchall(
                                "SELECT confirmed_revision FROM player_exchange_members "
                                "WHERE exchange_id=%s ORDER BY character_id",
                                (exchange["id"],),
                            )
                        ],
                    )
                    self.assertEqual(
                        0,
                        self.fetchone(
                            "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                            (exchange["id"],),
                        )["n"],
                    )
                    self.assertEqual(
                        inventory_before, self.inventory_rows(inviter, invitee)
                    )

    def test_terminal_durable_fights_do_not_block_exchange_invitation(self):
        from wakfu_server.combat import fight_store

        for status in ("finished", "aborted"):
            with self.subTest(status=status):
                inviter, invitee = self.player(
                    f"terminal-fight-a-{status}"
                ), self.player(f"terminal-fight-b-{status}")
                fight_id = self.durable_fight(inviter, "placement")
                with self.store.connection() as db:
                    if status == "finished":
                        fight_store.finish(
                            self.store,
                            db,
                            inviter["account"],
                            inviter["generation"],
                            inviter["character"]["id"],
                            fight_id,
                        )
                    else:
                        fight_store.abort(
                            self.store,
                            inviter["account"],
                            inviter["character"]["id"],
                            fight_id,
                            db=db,
                        )

                exchange = self.invite(inviter, invitee)

                self.assertEqual("invitation", exchange["state"])
                self.assertEqual(
                    status,
                    self.fetchone(
                        "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
                    )["status"],
                )

    def test_opposing_concurrent_invitations_cannot_create_two_exchanges(self):
        left, right = self.player("leftpeer"), self.player("rightpeer")
        barrier = threading.Barrier(2)

        def attempt(source, target):
            barrier.wait(timeout=5)
            try:
                player_exchanges.invite(
                    self.store,
                    source["account"],
                    source["generation"],
                    source["character"]["id"],
                    target["character"]["id"],
                )
                return "created"
            except ValueError:
                return "busy"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(lambda pair: attempt(*pair), ((left, right), (right, left)))
            )

        self.assertCountEqual(["created", "busy"], results)
        self.assertEqual(
            1, self.fetchone("SELECT count(*) AS n FROM player_exchanges")["n"]
        )
        self.assertEqual(
            2, self.fetchone("SELECT count(*) AS n FROM player_exchange_members")["n"]
        )

    def test_outbox_failure_rolls_back_decline_state_and_membership(self):
        inviter, invitee = self.player("rollbackfrom"), self.player("rollbackto")
        with self.store.connection() as db:
            db.execute(
                """
                CREATE FUNCTION fail_exchange_outbox() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                  IF NEW.event='canceled' THEN
                    RAISE EXCEPTION 'injected exchange outbox failure';
                  END IF;
                  RETURN NEW;
                END $$
            """
            )
            db.execute(
                """
                CREATE TRIGGER fail_exchange_outbox_insert BEFORE INSERT ON player_exchange_outbox
                FOR EACH ROW EXECUTE FUNCTION fail_exchange_outbox()
            """
            )
        exchange = self.invite(inviter, invitee)
        with self.assertRaisesRegex(RaiseException, "injected exchange outbox failure"):
            player_exchanges.answer(
                self.store,
                invitee["account"],
                invitee["generation"],
                invitee["character"]["id"],
                exchange["id"],
                False,
            )
        self.assertEqual(
            "invitation",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_members WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_outbox "
                "WHERE exchange_id=%s AND event='snapshot'",
                (exchange["id"],),
            )["n"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_outbox "
                "WHERE exchange_id=%s AND event='canceled'",
                (exchange["id"],),
            )["n"],
        )

    def test_kamas_offers_are_reserved_not_debited_and_changed_revision_needs_republication(
        self,
    ):
        inviter, invitee = self.player("offerfrom"), self.player("offerto")
        exchange = self.invite(inviter, invitee)
        exchange = player_exchanges.answer(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            exchange["id"],
            True,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=100 WHERE account_id IN (%s,%s)",
                (inviter["account"], invitee["account"]),
            )

        changed = player_exchanges.offer_kamas(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            25,
        )
        self.assertEqual(3, changed["revision"])
        self.assertEqual(
            25,
            self.fetchone(
                "SELECT offered_kamas FROM player_exchange_members "
                "WHERE exchange_id=%s AND character_id=%s",
                (exchange["id"], inviter["character"]["id"]),
            )["offered_kamas"],
        )
        self.assertEqual(
            [100, 100],
            [
                row["kamas"]
                for row in self.fetchall(
                    "SELECT kamas FROM account_wallets WHERE account_id IN (%s,%s) ORDER BY account_id",
                    tuple(sorted((inviter["account"], invitee["account"]))),
                )
            ],
        )
        before_outbox = self.fetchone(
            "SELECT count(*) AS n FROM player_exchange_outbox WHERE exchange_id=%s",
            (exchange["id"],),
        )["n"]
        unchanged = player_exchanges.offer_kamas(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            25,
        )
        self.assertEqual(3, unchanged["revision"])
        self.assertEqual(
            before_outbox,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_outbox WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            player_exchanges.offer_kamas(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                101,
            )
        self.assertEqual(
            3,
            self.fetchone(
                "SELECT revision FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["revision"],
        )

        changed = player_exchanges.offer_kamas(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            exchange["id"],
            15,
        )
        self.assertEqual(4, changed["revision"])
        self.assertEqual(
            [None, None],
            [
                row["confirmed_revision"]
                for row in self.fetchall(
                    "SELECT confirmed_revision FROM player_exchange_members "
                    "WHERE exchange_id=%s ORDER BY character_id",
                    (exchange["id"],),
                )
            ],
        )
        with self.assertRaisesRegex(ValueError, "stale"):
            player_exchanges.published(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                3,
            )
        player_exchanges.published(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            4,
        )
        self.assertEqual(
            4,
            self.fetchone(
                "SELECT published_revision FROM player_exchange_members "
                "WHERE exchange_id=%s AND character_id=%s",
                (exchange["id"], inviter["character"]["id"]),
            )["published_revision"],
        )

    def test_participant_can_cancel_after_peer_goes_offline_and_cancel_is_idempotent(
        self,
    ):
        inviter, invitee, outsider = (
            self.player("cancelowner"),
            self.player("offlinepeer"),
            self.player("cancelother"),
        )
        exchange = self.invite(inviter, invitee)
        self.store.begin_session(invitee["account"], ttl=10_000)
        with self.assertRaisesRegex(ValueError, "owned"):
            player_exchanges.cancel(
                self.store,
                outsider["account"],
                outsider["generation"],
                outsider["character"]["id"],
                exchange["id"],
            )
        canceled = player_exchanges.cancel(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        self.assertEqual(("canceled", 2), (canceled["state"], canceled["revision"]))
        count_before = self.fetchone(
            "SELECT count(*) AS n FROM player_exchange_outbox WHERE exchange_id=%s",
            (exchange["id"],),
        )["n"]
        repeated = player_exchanges.cancel(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        self.assertEqual(("canceled", 2), (repeated["state"], repeated["revision"]))
        self.assertEqual(
            count_before,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_outbox WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_members WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )

    def test_invitation_cancel_expected_state_rejects_after_acceptance(self):
        inviter, invitee = self.player("expected-cancel-inviter"), self.player(
            "expected-cancel-invitee"
        )
        exchange = self.active_exchange(inviter, invitee)
        with self.assertRaisesRegex(ValueError, "state changed"):
            player_exchanges.cancel(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                expected_state="invitation",
            )
        self.assertEqual(
            "active",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_outbox "
                "WHERE exchange_id=%s AND event='canceled'",
                (exchange["id"],),
            )["n"],
        )

    def test_expiration_is_bounded_replay_safe_and_races_answer_to_one_terminal_state(
        self,
    ):
        first_a, first_b = self.player("expirefirsta"), self.player("expirefirstb")
        second_a, second_b = self.player("expireseconda"), self.player("expiresecondb")
        first = self.invite(first_a, first_b)
        second = self.invite(second_a, second_b)
        self.now += 60
        with self.assertRaisesRegex(ValueError, "limit"):
            player_exchanges.expire(self.store, limit=True)

        first_result = player_exchanges.expire(self.store, limit=1)
        self.assertEqual([first["id"]], first_result)
        self.assertEqual(
            "expired",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (first["id"],)
            )["state"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_members WHERE exchange_id=%s",
                (first["id"],),
            )["n"],
        )
        self.assertEqual(
            "invitation",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (second["id"],)
            )["state"],
        )
        self.assertEqual([second["id"]], player_exchanges.expire(self.store, limit=1))
        self.assertEqual([], player_exchanges.expire(self.store, limit=1))

        race_a, race_b = self.player("expiresa"), self.player("expiresb")
        race = self.invite(race_a, race_b)
        # Put this invitation at the same expiration boundary while preserving
        # its durable identities and membership. Whichever transaction locks
        # first must leave a single terminal result.
        self.now += 60
        barrier = threading.Barrier(2)

        def answer():
            barrier.wait(timeout=5)
            try:
                return player_exchanges.answer(
                    self.store,
                    race_b["account"],
                    race_b["generation"],
                    race_b["character"]["id"],
                    race["id"],
                    True,
                )["state"]
            except ValueError:
                return "rejected"

        def expire_one():
            barrier.wait(timeout=5)
            return player_exchanges.expire(self.store, limit=1)

        with ThreadPoolExecutor(max_workers=2) as pool:
            answer_future = pool.submit(answer)
            expire_future = pool.submit(expire_one)
            answer_result = answer_future.result(timeout=10)
            expired_ids = expire_future.result(timeout=10)
        state = self.fetchone(
            "SELECT state FROM player_exchanges WHERE id=%s", (race["id"],)
        )["state"]
        self.assertEqual("expired", state)
        self.assertEqual("rejected", answer_result)
        self.assertEqual([race["id"]], expired_ids)

    def test_expire_cancels_active_exchange_when_selected_session_is_replaced(self):
        inviter, invitee = self.player("staleactivea"), self.player("staleactiveb")
        exchange = self.active_exchange(inviter, invitee)
        item = self.grant_item(inviter, 12, quantity=3)
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            2,
        )
        inventory_before = self.inventory_rows(inviter, invitee)
        wallets_before = self.fetchall(
            "SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s) ORDER BY account_id",
            ([inviter["account"], invitee["account"]],),
        )
        prior_revision = self.fetchone(
            "SELECT revision FROM player_exchanges WHERE id=%s", (exchange["id"],)
        )["revision"]

        # Replacing the selected character invalidates the exchange's captured
        # generation and character, even though the account has a new session.
        self.store.begin_session(invitee["account"], ttl=10_000)
        self.assertEqual([exchange["id"]], player_exchanges.expire(self.store))

        row = self.fetchone(
            "SELECT state,revision FROM player_exchanges WHERE id=%s", (exchange["id"],)
        )
        self.assertEqual(
            ("canceled", prior_revision + 1), (row["state"], row["revision"])
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_members WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_items WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        events = self.fetchall(
            "SELECT character_id,generation,event,payload FROM player_exchange_outbox "
            "WHERE exchange_id=%s AND revision=%s ORDER BY character_id",
            (exchange["id"], row["revision"]),
        )
        self.assertEqual(2, len(events))
        self.assertEqual({"canceled"}, {event["event"] for event in events})
        self.assertTrue(
            all(event["payload"]["state"] == "canceled" for event in events)
        )
        self.assertEqual(inventory_before, self.inventory_rows(inviter, invitee))
        self.assertEqual(
            wallets_before,
            self.fetchall(
                "SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s) ORDER BY account_id",
                ([inviter["account"], invitee["account"]],),
            ),
        )
        self.assertEqual([], player_exchanges.expire(self.store))

    def test_expire_never_cancels_committed_exchange_or_reverses_transfer(self):
        inviter, invitee = self.player("expirecommitteda"), self.player(
            "expirecommittedb"
        )
        exchange = self.active_exchange(inviter, invitee)
        offered = self.grant_item(inviter, 12, quantity=1)
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            offered["uid"],
            1,
        )
        revision = self.publish_current(exchange, inviter, invitee)
        for participant in (inviter, invitee):
            player_exchanges.confirm(
                self.store,
                participant["account"],
                participant["generation"],
                participant["character"]["id"],
                exchange["id"],
            )
        receipt_before = self.fetchone(
            "SELECT revision,transfers FROM player_exchange_receipts WHERE exchange_id=%s",
            (exchange["id"],),
        )
        inventory_before = self.inventory_rows(inviter, invitee)
        members_before = self.fetchall(
            "SELECT character_id,exchange_id FROM player_exchange_members WHERE exchange_id=%s "
            "ORDER BY character_id",
            (exchange["id"],),
        )
        # Make both old session generations stale, then run the bounded cleanup.
        self.store.begin_session(inviter["account"], ttl=10_000)
        self.store.begin_session(invitee["account"], ttl=10_000)
        self.now += 400

        self.assertEqual([], player_exchanges.expire(self.store))

        state = self.fetchone(
            "SELECT state,revision FROM player_exchanges WHERE id=%s", (exchange["id"],)
        )
        self.assertEqual(("committed", revision), (state["state"], state["revision"]))
        self.assertEqual(
            receipt_before,
            self.fetchone(
                "SELECT revision,transfers FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange["id"],),
            ),
        )
        self.assertEqual(inventory_before, self.inventory_rows(inviter, invitee))
        self.assertEqual(
            members_before,
            self.fetchall(
                "SELECT character_id,exchange_id FROM player_exchange_members WHERE exchange_id=%s "
                "ORDER BY character_id",
                (exchange["id"],),
            ),
        )

    def test_item_offer_preserves_inventory_and_zero_withdraws_without_transfer(self):
        inviter, invitee = self.player("itemofferfrom"), self.player("itemofferto")
        exchange = self.active_exchange(inviter, invitee)
        item = self.grant_item(inviter, 12, quantity=3)
        before = self.fetchone(
            "SELECT uid,character_id,reference,quantity,container,slot FROM inventory_items WHERE uid=%s",
            (item["uid"],),
        )

        changed = player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            2,
        )
        self.assertEqual(3, changed["revision"])
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT quantity FROM player_exchange_items WHERE exchange_id=%s AND uid=%s",
                (exchange["id"], item["uid"]),
            )["quantity"],
        )
        self.assertEqual(
            before,
            self.fetchone(
                "SELECT uid,character_id,reference,quantity,container,slot FROM inventory_items WHERE uid=%s",
                (item["uid"],),
            ),
        )
        self.assertEqual(
            {
                "bound": False,
                "template_reference": 12,
            },
            self.fetchone(
                "SELECT bound,template_reference FROM inventory_item_bindings WHERE uid=%s",
                (item["uid"],),
            ),
        )
        captured = self.fetchall(
            "SELECT payload FROM player_exchange_outbox WHERE exchange_id=%s AND revision=3",
            (exchange["id"],),
        )
        self.assertEqual(2, len(captured))
        for row in captured:
            self.assertEqual(1, len(row["payload"]["items"]))
            offer = row["payload"]["items"][0]
            self.assertEqual(
                (inviter["character"]["id"], item["uid"], 2),
                (offer["character_id"], offer["uid"], offer["quantity"]),
            )
            self.assertEqual(
                (item["uid"], inviter["character"]["id"], 12, 2),
                (
                    offer["unit"]["uid"],
                    offer["unit"]["character_id"],
                    offer["unit"]["reference"],
                    offer["unit"]["quantity"],
                ),
            )
            self.assertIn("container", offer["unit"])
            self.assertIn("slot", offer["unit"])

        prior_outbox = self.fetchone(
            "SELECT count(*) AS n FROM player_exchange_outbox WHERE exchange_id=%s",
            (exchange["id"],),
        )["n"]
        same = player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            2,
        )
        self.assertEqual(3, same["revision"])
        self.assertEqual(
            prior_outbox,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_outbox WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                item["uid"],
                4,
            )

        removed = player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            0,
        )
        self.assertEqual(4, removed["revision"])
        self.assertIsNone(
            self.fetchone(
                "SELECT uid FROM player_exchange_items WHERE exchange_id=%s AND uid=%s",
                (exchange["id"], item["uid"]),
            )
        )
        self.assertEqual(
            before,
            self.fetchone(
                "SELECT uid,character_id,reference,quantity,container,slot FROM inventory_items WHERE uid=%s",
                (item["uid"],),
            ),
        )
        with self.assertRaisesRegex(ValueError, "not offered"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                item["uid"],
                0,
            )

    def test_offer_snapshot_rolls_back_if_an_offered_unit_disappeared(self):
        inviter, invitee = self.player("vanishedofferfrom"), self.player(
            "vanishedofferto"
        )
        exchange = self.active_exchange(inviter, invitee)
        item = self.grant_item(inviter, 12, quantity=2)
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            1,
        )
        before = self.fetchone(
            "SELECT revision,delivery_sequence FROM player_exchanges WHERE id=%s",
            (exchange["id"],),
        )
        outbox_before = self.fetchone(
            "SELECT count(*) AS n FROM player_exchange_outbox WHERE exchange_id=%s",
            (exchange["id"],),
        )["n"]
        self.set_wallets((inviter, 5), (invitee, 0))
        with self.store.connection() as db:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (item["uid"],))

        with self.assertRaisesRegex(ValueError, "disappeared before publication"):
            player_exchanges.offer_kamas(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                1,
            )

        self.assertEqual(
            before,
            self.fetchone(
                "SELECT revision,delivery_sequence FROM player_exchanges WHERE id=%s",
                (exchange["id"],),
            ),
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT offered_kamas FROM player_exchange_members "
                "WHERE exchange_id=%s AND character_id=%s",
                (exchange["id"], inviter["character"]["id"]),
            )["offered_kamas"],
        )
        self.assertEqual(
            outbox_before,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_outbox WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )

    def test_item_offer_rejects_foreign_forged_oversized_and_inactive_equipped_units(
        self,
    ):
        inviter, invitee = self.player("itemguardfrom"), self.player("itemguardto")
        exchange = self.active_exchange(inviter, invitee)
        own = self.grant_item(inviter, 12, quantity=3)
        foreign = self.grant_item(invitee, 12, quantity=1)
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                foreign["uid"],
                1,
            )
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                9876543210123,
                1,
            )
        with self.assertRaisesRegex(ValueError, "Invalid exchange item offer"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                own["uid"],
                32768,
            )

        # An inactive saved build still reserves its equipped UID from trade.
        equipment = proto_field(10, proto_field(8, own["uid"]) + proto_field(16, 0))
        sheet = b"".join(
            proto_field(tag, value)
            for tag, value in (
                (8, 2),
                (18, b"Inactive gear"),
                (24, 1),
                (56, 0),
            )
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) "
                "VALUES(%s,2,%s,%s,%s,%s)",
                (inviter["character"]["id"], sheet, equipment, b"", b""),
            )
        with self.assertRaisesRegex(ValueError, "every build"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                own["uid"],
                1,
            )
        self.assertIsNone(
            self.fetchone(
                "SELECT uid FROM inventory_item_bindings WHERE uid=%s", (own["uid"],)
            )
        )
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM character_builds WHERE character_id=%s AND build_index=2",
                (inviter["character"]["id"],),
            )
        result = player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            own["uid"],
            1,
        )
        self.assertEqual(3, result["revision"])

    def test_item_offer_fails_closed_for_native_binding_no_trade_and_binding_mismatch(
        self,
    ):
        inviter, invitee = self.player("bindingfrom"), self.player("bindingto")
        exchange = self.active_exchange(inviter, invitee)
        pickup = self.grant_item(inviter, 2603, quantity=1)
        with self.assertRaisesRegex(ValueError, "binding or criterion"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                pickup["uid"],
                1,
            )
        prohibited = self.grant_item(inviter, 2337, quantity=1, slot=1)
        with self.assertRaisesRegex(ValueError, "binding or criterion"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                prohibited["uid"],
                1,
            )

        item = self.grant_item(inviter, 12, quantity=2, slot=2)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) "
                "VALUES(%s,false,12)",
                (item["uid"],),
            )
        result = player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            1,
        )
        self.assertEqual(3, result["revision"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_item_bindings SET template_reference=2603 WHERE uid=%s",
                (item["uid"],),
            )
        with self.assertRaisesRegex(ValueError, "reference differs"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                item["uid"],
                2,
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_item_bindings SET template_reference=12,bound=true WHERE uid=%s",
                (item["uid"],),
            )
        with self.assertRaisesRegex(ValueError, "binding or criterion"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                item["uid"],
                2,
            )

    def test_item_offer_limit_is_database_policy_and_rejection_is_atomic(self):
        inviter, invitee = self.player("limitfrom"), self.player("limittarget")
        exchange = self.active_exchange(inviter, invitee)
        first = self.grant_item(inviter, 12, slot=0)
        second = self.grant_item(inviter, 12, slot=1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='player_exchange_policy'",
                (
                    Jsonb(
                        {
                            "version": 1,
                            "invitation_seconds": 60,
                            "maximum_offer_items": 1,
                        }
                    ),
                ),
            )
        changed = player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            first["uid"],
            1,
        )
        self.assertEqual(3, changed["revision"])
        with self.assertRaisesRegex(ValueError, "offer is full"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                second["uid"],
                1,
            )
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_items WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        self.assertEqual(
            3,
            self.fetchone(
                "SELECT revision FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["revision"],
        )
        self.assertIsNone(
            self.fetchone(
                "SELECT uid FROM inventory_item_bindings WHERE uid=%s", (second["uid"],)
            )
        )

    def test_bulk_withdrawal_validates_every_uid_before_removing_any_offer(self):
        inviter, invitee = self.player("withdrawfrom"), self.player("withdrawto")
        exchange = self.active_exchange(inviter, invitee)
        first = self.grant_item(inviter, 12, slot=0)
        second = self.grant_item(inviter, 12, slot=1)
        foreign = self.grant_item(invitee, 12, slot=0)
        for owner, item in ((inviter, first), (inviter, second), (invitee, foreign)):
            player_exchanges.offer_item(
                self.store,
                owner["account"],
                owner["generation"],
                owner["character"]["id"],
                exchange["id"],
                item["uid"],
                1,
            )
        revision = self.fetchone(
            "SELECT revision FROM player_exchanges WHERE id=%s", (exchange["id"],)
        )["revision"]
        before = self.fetchall(
            "SELECT character_id,uid,quantity FROM player_exchange_items "
            "WHERE exchange_id=%s ORDER BY uid",
            (exchange["id"],),
        )
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            player_exchanges.withdraw_items(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                [first["uid"], second["uid"], foreign["uid"]],
            )
        self.assertEqual(
            before,
            self.fetchall(
                "SELECT character_id,uid,quantity FROM player_exchange_items "
                "WHERE exchange_id=%s ORDER BY uid",
                (exchange["id"],),
            ),
        )
        self.assertEqual(
            revision,
            self.fetchone(
                "SELECT revision FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["revision"],
        )
        for invalid in ([], [first["uid"], first["uid"]], [True]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                player_exchanges.withdraw_items(
                    self.store,
                    inviter["account"],
                    inviter["generation"],
                    inviter["character"]["id"],
                    exchange["id"],
                    invalid,
                )
        result = player_exchanges.withdraw_items(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            [first["uid"], second["uid"]],
        )
        self.assertEqual(revision + 1, result["revision"])
        self.assertEqual(
            [foreign["uid"]],
            [
                row["uid"]
                for row in self.fetchall(
                    "SELECT uid FROM player_exchange_items WHERE exchange_id=%s",
                    (exchange["id"],),
                )
            ],
        )

    def test_two_current_confirmations_transfer_whole_uids_and_conserve_cash_once(self):
        inviter, invitee = self.player("commitfrom"), self.player("committo")
        exchange = self.active_exchange(inviter, invitee)
        left_item = self.grant_item(inviter, 12, quantity=1)
        right_item = self.grant_item(invitee, 12, quantity=1)
        self.set_wallets((inviter, 100), (invitee, 50))
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            left_item["uid"],
            1,
        )
        player_exchanges.offer_item(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            exchange["id"],
            right_item["uid"],
            1,
        )
        player_exchanges.offer_kamas(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            25,
        )
        player_exchanges.offer_kamas(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            exchange["id"],
            10,
        )
        revision = self.publish_current(exchange, inviter, invitee)
        before = self.inventory_rows(inviter, invitee)

        first = player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        self.assertFalse(first["applied"])
        self.assertEqual(before, self.inventory_rows(inviter, invitee))
        self.assertEqual(
            "active",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )
        done = player_exchanges.confirm(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            exchange["id"],
        )
        self.assertTrue(done["applied"])
        self.assertEqual("committed", done["state"])
        rows = {row["uid"]: row for row in self.inventory_rows(inviter, invitee)}
        self.assertEqual(
            invitee["character"]["id"], rows[left_item["uid"]]["character_id"]
        )
        self.assertEqual(
            inviter["character"]["id"], rows[right_item["uid"]]["character_id"]
        )
        self.assertEqual(1, rows[left_item["uid"]]["quantity"])
        self.assertEqual(1, rows[right_item["uid"]]["quantity"])
        wallets = {
            row["account_id"]: row["kamas"]
            for row in self.fetchall(
                "SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s)",
                (sorted((inviter["account"], invitee["account"])),),
            )
        }
        self.assertEqual({inviter["account"]: 85, invitee["account"]: 65}, wallets)
        self.assertEqual(150, sum(wallets.values()))
        receipt = self.fetchone(
            "SELECT revision,transfers FROM player_exchange_receipts WHERE exchange_id=%s",
            (exchange["id"],),
        )
        self.assertEqual(revision, receipt["revision"])
        self.assertEqual(2, len(receipt["transfers"]["items"]))
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        self.assertFalse(
            player_exchanges.confirm(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
            )["applied"]
        )
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_outbox "
                "WHERE exchange_id=%s AND event='committed'",
                (exchange["id"],),
            )["n"],
        )

    def test_confirmation_requires_current_publication_and_offer_change_clears_both_readies(
        self,
    ):
        inviter, invitee = self.player("readyfrom"), self.player("readyto")
        exchange = self.active_exchange(inviter, invitee)
        first = self.grant_item(inviter, 12)
        second = self.grant_item(invitee, 12)
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            first["uid"],
            1,
        )
        revision = self.publish_current(exchange, inviter)
        with self.assertRaisesRegex(ValueError, "precedes current offer publication"):
            player_exchanges.confirm(
                self.store,
                invitee["account"],
                invitee["generation"],
                invitee["character"]["id"],
                exchange["id"],
            )
        player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        self.assertEqual(
            revision,
            self.fetchone(
                "SELECT confirmed_revision FROM player_exchange_members "
                "WHERE exchange_id=%s AND character_id=%s",
                (exchange["id"], inviter["character"]["id"]),
            )["confirmed_revision"],
        )

        player_exchanges.offer_item(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            exchange["id"],
            second["uid"],
            1,
        )
        changed_revision = revision + 1
        members = self.fetchall(
            "SELECT confirmed_revision,published_revision FROM player_exchange_members "
            "WHERE exchange_id=%s",
            (exchange["id"],),
        )
        self.assertEqual([None, None], [row["confirmed_revision"] for row in members])
        with self.assertRaisesRegex(ValueError, "precedes current offer publication"):
            player_exchanges.confirm(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
            )
        self.publish_current(exchange, inviter, invitee)
        first_ready = player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        self.assertFalse(first_ready["applied"])
        self.assertEqual(changed_revision, first_ready["revision"])
        self.assertEqual(
            "active",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )

    def test_inventory_capacity_failure_rolls_back_second_confirmation_and_everything_else(
        self,
    ):
        inviter, invitee = self.player("capacityfrom"), self.player("capacityto")
        exchange = self.active_exchange(inviter, invitee)
        outgoing = self.grant_item(inviter, 12)
        resident = self.grant_item(invitee, 1718)
        resident_bag = self.grant_item(invitee, 1718, slot=0, kind=1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_containers SET capacity=1 " "WHERE character_id=%s",
                (invitee["character"]["id"],),
            )
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            outgoing["uid"],
            1,
        )
        self.publish_current(exchange, inviter, invitee)
        first_ready = player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        self.assertFalse(first_ready["applied"])
        before = self.inventory_rows(inviter, invitee)
        before_wallets = self.fetchall(
            "SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s) ORDER BY account_id",
            (sorted((inviter["account"], invitee["account"])),),
        )
        with self.assertRaisesRegex(ValueError, "inventory is full"):
            player_exchanges.confirm(
                self.store,
                invitee["account"],
                invitee["generation"],
                invitee["character"]["id"],
                exchange["id"],
            )
        self.assertEqual(before, self.inventory_rows(inviter, invitee))
        self.assertEqual(
            before_wallets,
            self.fetchall(
                "SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s) ORDER BY account_id",
                (sorted((inviter["account"], invitee["account"])),),
            ),
        )
        self.assertEqual(
            "active",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        self.assertEqual(
            None,
            self.fetchone(
                "SELECT confirmed_revision FROM player_exchange_members "
                "WHERE exchange_id=%s AND character_id=%s",
                (exchange["id"], invitee["character"]["id"]),
            )["confirmed_revision"],
        )
        self.assertEqual(
            {resident["uid"], resident_bag["uid"]},
            {
                row["uid"]
                for row in self.fetchall(
                    "SELECT uid FROM inventory_items WHERE character_id=%s",
                    (invitee["character"]["id"],),
                )
            },
        )

    def test_cash_revalidation_and_overflow_fail_before_any_receipt_or_transfer(self):
        inviter, invitee = self.player("cashchangedfrom"), self.player("cashchangedto")
        exchange = self.active_exchange(inviter, invitee)
        item = self.grant_item(inviter, 12)
        self.set_wallets((inviter, 100), (invitee, 50))
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            1,
        )
        player_exchanges.offer_kamas(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            60,
        )
        self.publish_current(exchange, inviter, invitee)
        player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=40 WHERE account_id=%s",
                (inviter["account"],),
            )
        before = self.inventory_rows(inviter, invitee)
        with self.assertRaisesRegex(ValueError, "balance changed"):
            player_exchanges.confirm(
                self.store,
                invitee["account"],
                invitee["generation"],
                invitee["character"]["id"],
                exchange["id"],
            )
        self.assertEqual(before, self.inventory_rows(inviter, invitee))
        self.assertEqual(
            "active",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )

        left, right = self.player("overflowfrom"), self.player("overflowto")
        overflow = self.active_exchange(left, right)
        self.set_wallets((left, 5), (right, 2**63 - 1))
        player_exchanges.offer_kamas(
            self.store,
            left["account"],
            left["generation"],
            left["character"]["id"],
            overflow["id"],
            1,
        )
        self.publish_current(overflow, left, right)
        player_exchanges.confirm(
            self.store,
            left["account"],
            left["generation"],
            left["character"]["id"],
            overflow["id"],
        )
        with self.assertRaisesRegex(ValueError, "currency limit"):
            player_exchanges.confirm(
                self.store,
                right["account"],
                right["generation"],
                right["character"]["id"],
                overflow["id"],
            )
        balances = {
            row["account_id"]: row["kamas"]
            for row in self.fetchall(
                "SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s)",
                (sorted((left["account"], right["account"])),),
            )
        }
        self.assertEqual({left["account"]: 5, right["account"]: 2**63 - 1}, balances)
        self.assertEqual(
            "active",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (overflow["id"],)
            )["state"],
        )

    def test_receipt_failure_after_sql_mutations_rolls_back_inventory_wallet_and_readiness(
        self,
    ):
        inviter, invitee = self.player("receiptfrom"), self.player("receiptto")
        exchange = self.active_exchange(inviter, invitee)
        item = self.grant_item(inviter, 12)
        self.set_wallets((inviter, 90), (invitee, 25))
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            1,
        )
        player_exchanges.offer_kamas(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            15,
        )
        self.publish_current(exchange, inviter, invitee)
        player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        before_items = self.inventory_rows(inviter, invitee)
        before_wallets = {
            row["account_id"]: row["kamas"]
            for row in self.fetchall(
                "SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s)",
                (sorted((inviter["account"], invitee["account"])),),
            )
        }
        with self.store.connection() as db:
            db.execute(
                """
                CREATE FUNCTION fail_exchange_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'injected exchange receipt failure'; END $$
            """
            )
            db.execute(
                """
                CREATE TRIGGER fail_exchange_receipt_insert BEFORE INSERT ON player_exchange_receipts
                FOR EACH ROW EXECUTE FUNCTION fail_exchange_receipt()
            """
            )
        with self.assertRaisesRegex(
            RaiseException, "injected exchange receipt failure"
        ):
            player_exchanges.confirm(
                self.store,
                invitee["account"],
                invitee["generation"],
                invitee["character"]["id"],
                exchange["id"],
            )
        self.assertEqual(before_items, self.inventory_rows(inviter, invitee))
        self.assertEqual(
            before_wallets,
            {
                row["account_id"]: row["kamas"]
                for row in self.fetchall(
                    "SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s)",
                    (sorted((inviter["account"], invitee["account"])),),
                )
            },
        )
        self.assertEqual(
            "active",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        self.assertIsNone(
            self.fetchone(
                "SELECT confirmed_revision FROM player_exchange_members "
                "WHERE exchange_id=%s AND character_id=%s",
                (exchange["id"], invitee["character"]["id"]),
            )["confirmed_revision"]
        )
        with self.store.connection() as db:
            db.execute(
                "DROP TRIGGER fail_exchange_receipt_insert ON player_exchange_receipts"
            )
            db.execute("DROP FUNCTION fail_exchange_receipt()")
        retry = player_exchanges.confirm(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            exchange["id"],
        )
        self.assertTrue(retry["applied"])

    def test_committed_outbox_failure_rolls_back_receipt_status_wallet_and_inventory(
        self,
    ):
        inviter, invitee = self.player("outboxcommitfrom"), self.player(
            "outboxcommitto"
        )
        exchange = self.active_exchange(inviter, invitee)
        item = self.grant_item(inviter, 12)
        self.set_wallets((inviter, 80), (invitee, 20))
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            1,
        )
        player_exchanges.offer_kamas(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            12,
        )
        self.publish_current(exchange, inviter, invitee)
        player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        before_items = self.inventory_rows(inviter, invitee)
        before_wallets = {
            row["account_id"]: row["kamas"]
            for row in self.fetchall(
                "SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s)",
                (sorted((inviter["account"], invitee["account"])),),
            )
        }
        with self.store.connection() as db:
            db.execute(
                """
                CREATE FUNCTION fail_committed_exchange_outbox() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                  IF NEW.event='committed' THEN
                    RAISE EXCEPTION 'injected committed outbox failure';
                  END IF;
                  RETURN NEW;
                END $$
            """
            )
            db.execute(
                """
                CREATE TRIGGER fail_committed_exchange_outbox_insert
                BEFORE INSERT ON player_exchange_outbox FOR EACH ROW
                EXECUTE FUNCTION fail_committed_exchange_outbox()
            """
            )
        with self.assertRaisesRegex(
            RaiseException, "injected committed outbox failure"
        ):
            player_exchanges.confirm(
                self.store,
                invitee["account"],
                invitee["generation"],
                invitee["character"]["id"],
                exchange["id"],
            )
        self.assertEqual(before_items, self.inventory_rows(inviter, invitee))
        self.assertEqual(
            before_wallets,
            {
                row["account_id"]: row["kamas"]
                for row in self.fetchall(
                    "SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s)",
                    (sorted((inviter["account"], invitee["account"])),),
                )
            },
        )
        self.assertEqual(
            "active",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        self.assertEqual(
            0,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_outbox "
                "WHERE exchange_id=%s AND event='committed'",
                (exchange["id"],),
            )["n"],
        )
        self.assertEqual(
            2,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_members WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )

    def test_commit_revalidates_if_offered_item_becomes_equipped_in_inactive_build(
        self,
    ):
        inviter, invitee = self.player("equippedlatefrom"), self.player(
            "equippedlateto"
        )
        exchange = self.active_exchange(inviter, invitee)
        item = self.grant_item(inviter, 12)
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            1,
        )
        self.publish_current(exchange, inviter, invitee)
        player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        equipment = proto_field(10, proto_field(8, item["uid"]) + proto_field(16, 0))
        sheet = b"".join(
            proto_field(tag, value)
            for tag, value in (
                (8, 3),
                (18, b"Late inactive gear"),
                (24, 1),
                (56, 0),
            )
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) "
                "VALUES(%s,3,%s,%s,%s,%s)",
                (inviter["character"]["id"], sheet, equipment, b"", b""),
            )
        with self.assertRaisesRegex(ValueError, "every build"):
            player_exchanges.confirm(
                self.store,
                invitee["account"],
                invitee["generation"],
                invitee["character"]["id"],
                exchange["id"],
            )
        self.assertEqual(
            inviter["character"]["id"],
            self.fetchone(
                "SELECT character_id FROM inventory_items WHERE uid=%s", (item["uid"],)
            )["character_id"],
        )
        self.assertEqual(
            "active",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )

    def test_commit_revalidates_persisted_binding_changed_after_offer(self):
        inviter, invitee = self.player("bindinglatefrom"), self.player("bindinglateto")
        exchange = self.active_exchange(inviter, invitee)
        item = self.grant_item(inviter, 12)
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            1,
        )
        self.publish_current(exchange, inviter, invitee)
        player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_item_bindings SET bound=true WHERE uid=%s",
                (item["uid"],),
            )
        with self.assertRaisesRegex(ValueError, "binding or criterion"):
            player_exchanges.confirm(
                self.store,
                invitee["account"],
                invitee["generation"],
                invitee["character"]["id"],
                exchange["id"],
            )
        self.assertEqual(
            inviter["character"]["id"],
            self.fetchone(
                "SELECT character_id FROM inventory_items WHERE uid=%s", (item["uid"],)
            )["character_id"],
        )
        self.assertEqual(
            "active",
            self.fetchone(
                "SELECT state FROM player_exchanges WHERE id=%s", (exchange["id"],)
            )["state"],
        )

    def test_offer_change_racing_second_confirmation_cannot_commit_stale_snapshot(self):
        inviter, invitee = self.player("racingofferfrom"), self.player("racingofferto")
        exchange = self.active_exchange(inviter, invitee)
        item = self.grant_item(inviter, 12, quantity=2)
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            1,
        )
        self.publish_current(exchange, inviter, invitee)
        player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        barrier = threading.Barrier(2)

        def change_offer():
            barrier.wait(timeout=5)
            try:
                changed = player_exchanges.offer_item(
                    self.store,
                    inviter["account"],
                    inviter["generation"],
                    inviter["character"]["id"],
                    exchange["id"],
                    item["uid"],
                    2,
                )
                return ("changed", changed["revision"])
            except ValueError:
                return ("rejected", None)

        def second_ready():
            barrier.wait(timeout=5)
            try:
                result = player_exchanges.confirm(
                    self.store,
                    invitee["account"],
                    invitee["generation"],
                    invitee["character"]["id"],
                    exchange["id"],
                )
                return (
                    "committed" if result["applied"] else "pending",
                    result["revision"],
                )
            except ValueError:
                return ("stale", None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            changing = pool.submit(change_offer)
            confirming = pool.submit(second_ready)
            offer_result = changing.result(timeout=15)
            confirm_result = confirming.result(timeout=15)
        state = self.fetchone(
            "SELECT state,revision FROM player_exchanges WHERE id=%s", (exchange["id"],)
        )
        if state["state"] == "committed":
            self.assertEqual(("rejected", None), offer_result)
            self.assertEqual(("committed", 3), confirm_result)
            transfers = self.fetchone(
                "SELECT transfers FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange["id"],),
            )["transfers"]
            self.assertEqual(1, transfers["items"][0]["quantity"])
        else:
            self.assertEqual("active", state["state"])
            self.assertEqual(4, state["revision"])
            self.assertEqual(("changed", 4), offer_result)
            self.assertEqual(("stale", None), confirm_result)
            self.assertEqual(
                2,
                self.fetchone(
                    "SELECT quantity FROM player_exchange_items WHERE exchange_id=%s AND uid=%s",
                    (exchange["id"], item["uid"]),
                )["quantity"],
            )
            self.assertEqual(
                0,
                self.fetchone(
                    "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                    (exchange["id"],),
                )["n"],
            )
            self.assertEqual(
                [None, None],
                [
                    row["confirmed_revision"]
                    for row in self.fetchall(
                        "SELECT confirmed_revision FROM player_exchange_members WHERE exchange_id=%s",
                        (exchange["id"],),
                    )
                ],
            )

    def test_concurrent_duplicate_second_confirmation_applies_one_receipt(self):
        inviter, invitee = self.player("racingfrom"), self.player("racingto")
        exchange = self.active_exchange(inviter, invitee)
        item = self.grant_item(inviter, 12)
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            item["uid"],
            1,
        )
        self.publish_current(exchange, inviter, invitee)
        player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        barrier = threading.Barrier(2)

        def confirm_again():
            barrier.wait(timeout=5)
            return player_exchanges.confirm(
                self.store,
                invitee["account"],
                invitee["generation"],
                invitee["character"]["id"],
                exchange["id"],
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [
                future.result(timeout=15)
                for future in (
                    pool.submit(confirm_again),
                    pool.submit(confirm_again),
                )
            ]
        self.assertCountEqual([True, False], [result["applied"] for result in results])
        self.assertEqual(results[0]["receipt"], results[1]["receipt"])
        self.assertEqual(
            1,
            self.fetchone(
                "SELECT count(*) AS n FROM player_exchange_receipts WHERE exchange_id=%s",
                (exchange["id"],),
            )["n"],
        )
        self.assertEqual(
            invitee["character"]["id"],
            self.fetchone(
                "SELECT character_id FROM inventory_items WHERE uid=%s", (item["uid"],)
            )["character_id"],
        )

    def test_split_item_transfer_preserves_element_and_binding_metadata(self):
        inviter, invitee = self.player("splitfrom"), self.player("splitto")
        exchange = self.active_exchange(inviter, invitee)
        source = self.grant_item(inviter, 2297, quantity=3)
        original_elements = self.fetchone(
            "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s",
            (source["uid"],),
        )
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            source["uid"],
            1,
        )
        self.publish_current(exchange, inviter, invitee)
        player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        result = player_exchanges.confirm(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            exchange["id"],
        )
        self.assertTrue(result["applied"])
        original = self.fetchone(
            "SELECT character_id,quantity FROM inventory_items WHERE uid=%s",
            (source["uid"],),
        )
        self.assertEqual(
            (inviter["character"]["id"], 2),
            (original["character_id"], original["quantity"]),
        )
        split = self.fetchone(
            "SELECT uid,character_id,reference,quantity FROM inventory_items "
            "WHERE character_id=%s AND reference=2297",
            (invitee["character"]["id"],),
        )
        self.assertNotEqual(source["uid"], split["uid"])
        self.assertEqual((2297, 1), (split["reference"], split["quantity"]))
        self.assertIn(
            {
                "source_uid": source["uid"],
                "received_uid": split["uid"],
                "character_id": invitee["character"]["id"],
                "quantity": 1,
            },
            result["receipt"]["transfers"]["items"],
        )
        self.assertEqual(
            original_elements,
            self.fetchone(
                "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s",
                (split["uid"],),
            ),
        )
        self.assertEqual(
            {"bound": False, "template_reference": 2297},
            self.fetchone(
                "SELECT bound,template_reference FROM inventory_item_bindings WHERE uid=%s",
                (split["uid"],),
            ),
        )

    def test_transfer_apply_preserves_mount_state_rows_but_trade_still_rejects_bound_mounts(
        self,
    ):
        from wakfu_server.exchange_transfer import apply

        inviter, invitee = self.player("mountunitfrom"), self.player("mountunitto")
        exchange = self.active_exchange(inviter, invitee)
        mount = self.grant_item(inviter, 18682)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET name='Stateful mount',xp=1234,health=17,"
                "color_item_ref=104,equipped_item_ref=205,sleep_item_ref=0,sleep_date=0,"
                "last_meal_date=1999999000000,last_hungry_date=2000000000000,revision=7 "
                "WHERE uid=%s",
                (mount["uid"],),
            )
        with self.assertRaisesRegex(ValueError, "binding or criterion"):
            player_exchanges.offer_item(
                self.store,
                inviter["account"],
                inviter["generation"],
                inviter["character"]["id"],
                exchange["id"],
                mount["uid"],
                1,
            )
        # The native pickup binding rejects the offer before it can create a
        # per-instance row. Seed one only for the transfer-helper preservation
        # check below.
        self.assertIsNone(
            self.fetchone(
                "SELECT uid FROM inventory_item_bindings WHERE uid=%s", (mount["uid"],)
            )
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) "
                "VALUES(%s,true,18682)",
                (mount["uid"],),
            )
        state_before = self.fetchone(
            "SELECT * FROM inventory_mounts WHERE uid=%s", (mount["uid"],)
        )
        binding_before = self.fetchone(
            "SELECT * FROM inventory_item_bindings WHERE uid=%s", (mount["uid"],)
        )
        self.assertEqual(
            {"bound": True, "template_reference": 18682},
            {
                "bound": binding_before["bound"],
                "template_reference": binding_before["template_reference"],
            },
        )

        target_container = self.fetchone(
            "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
            (invitee["character"]["id"],),
        )["uid"]
        with self.store.connection() as db:
            original = dict(
                db.execute(
                    "SELECT * FROM inventory_items WHERE uid=%s", (mount["uid"],)
                ).fetchone()
            )
            relocated = dict(
                original,
                character_id=invitee["character"]["id"],
                container=target_container,
                slot=0,
            )
            apply(db, [original], {mount["uid"]: relocated})
        self.assertEqual(
            invitee["character"]["id"],
            self.fetchone(
                "SELECT character_id FROM inventory_items WHERE uid=%s", (mount["uid"],)
            )["character_id"],
        )
        self.assertEqual(
            state_before,
            self.fetchone(
                "SELECT * FROM inventory_mounts WHERE uid=%s", (mount["uid"],)
            ),
        )
        self.assertEqual(
            binding_before,
            self.fetchone(
                "SELECT * FROM inventory_item_bindings WHERE uid=%s", (mount["uid"],)
            ),
        )

    def test_identical_stack_merge_and_full_inventory_bilateral_swap(self):
        inviter, invitee = self.player("mergefrom"), self.player("mergeto")
        exchange = self.active_exchange(inviter, invitee)
        offered = self.grant_item(inviter, 12, quantity=1)
        target_stack = self.grant_item(invitee, 12, quantity=2)
        player_exchanges.offer_item(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
            offered["uid"],
            1,
        )
        self.publish_current(exchange, inviter, invitee)
        player_exchanges.confirm(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            exchange["id"],
        )
        result = player_exchanges.confirm(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            exchange["id"],
        )
        self.assertTrue(result["applied"])
        self.assertIsNone(
            self.fetchone(
                "SELECT uid FROM inventory_items WHERE uid=%s", (offered["uid"],)
            )
        )
        self.assertEqual(
            (3, invitee["character"]["id"]),
            tuple(
                self.fetchone(
                    "SELECT quantity,character_id FROM inventory_items WHERE uid=%s",
                    (target_stack["uid"],),
                ).values()
            ),
        )

        # A separate exchange with one-slot inventories proves outgoing units
        # are removed before destinations are assigned.
        left, right = self.player("swapfrom"), self.player("swapto")
        swap = self.active_exchange(left, right)
        left_unit = self.grant_item(left, 12, slot=0)
        right_unit = self.grant_item(right, 12, slot=0)
        for participant in (left, right):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE inventory_containers SET capacity=1 WHERE character_id=%s",
                    (participant["character"]["id"],),
                )
        player_exchanges.offer_item(
            self.store,
            left["account"],
            left["generation"],
            left["character"]["id"],
            swap["id"],
            left_unit["uid"],
            1,
        )
        player_exchanges.offer_item(
            self.store,
            right["account"],
            right["generation"],
            right["character"]["id"],
            swap["id"],
            right_unit["uid"],
            1,
        )
        self.publish_current(swap, left, right)
        player_exchanges.confirm(
            self.store,
            left["account"],
            left["generation"],
            left["character"]["id"],
            swap["id"],
        )
        final = player_exchanges.confirm(
            self.store,
            right["account"],
            right["generation"],
            right["character"]["id"],
            swap["id"],
        )
        self.assertTrue(final["applied"])
        self.assertEqual(
            {
                left_unit["uid"]: right["character"]["id"],
                right_unit["uid"]: left["character"]["id"],
            },
            {
                row["uid"]: row["character_id"]
                for row in self.inventory_rows(left, right)
            },
        )
