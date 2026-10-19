"""Durable reward ownership for disconnected shared-fight participants."""

from concurrent.futures import ThreadPoolExecutor

from postgres_case import PostgresCase


class OfflineSettlementOwnershipTests(PostgresCase):
    def _fixture(self, *, offline_peer=True):
        from tests.test_combat_rewards import setup_reward_state
        from wakfu_server.combat_state import Actor
        from wakfu_server.characters import heroes

        store, account, main, generation, fight = setup_reward_state(self.store)
        peer_account = store.register("offline-peer", "local-password")["id"]
        peer = store.create_character(peer_account, "Offline Peer")
        peer_generation = store.begin_session(peer_account)
        store.select_character(peer_account, peer_generation, peer["id"])
        hero = store.create_character(account, "Settlement Hero")
        heroes.add(store, account, generation, main["id"], hero["id"])

        for character, owner, level, cell in (
            (main, account, 1, (0, 0, 0)),
            (peer, peer_account, 1, (2, 0, 0)),
            (hero, account, 1, (3, 0, 0)),
        ):
            if character["id"] != main["id"]:
                fight.actors[character["id"]] = Actor(
                    character["id"],
                    0,
                    cell,
                    character["hp"],
                    6,
                    3,
                    80,
                    level,
                    owner,
                    True,
                    max_hp=character["max_hp"],
                )
            else:
                fight.actors[character["id"]].owner_id = owner

        with store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=%s AND character_id=%s",
                (generation, fight.id, main["id"]),
            )
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s),(%s,%s,%s,0,%s)",
                (
                    fight.id,
                    peer["id"],
                    peer_account,
                    peer_generation,
                    fight.id,
                    hero["id"],
                    account,
                    generation,
                ),
            )
            # Keep the durable lease generation while making this owner's
            # socket genuinely offline before finalization.
            if offline_peer:
                db.execute("DELETE FROM sessions WHERE account_id=%s", (peer_account,))
        fight.phase, fight.winner = "finished", 0
        fight.actors[-200].effective_level = 23
        return (
            store,
            account,
            main,
            generation,
            peer_account,
            peer,
            peer_generation,
            hero,
            fight,
        )

    def _install_stats(self, store, actors):
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.equipment_stats import effective_character

        for actor, account in actors:
            if isinstance(getattr(actor, "effect_stats", None), dict):
                continue
            character = effective_character(store.character(account, actor.id))
            build_player_snapshot(
                character, actor, wp_current=6, wp_maximum=6, running_effects=()
            ).install(actor)

    def _settle_real_pipeline(
        self,
        fixture,
        *,
        fail_after_peer=False,
        finalizer=None,
        storage_modules=False,
        storage_drop_resolver=False,
    ):
        from wakfu_server.combat_rewards import award_shared_member
        from wakfu_server.combat_reward_context import settlement_contexts

        if storage_modules:
            from wakfu_server.storage.reward_policy import resolve as resolve_policy
        else:
            from wakfu_server.reward_policy import resolve as resolve_policy
        if storage_drop_resolver:
            from wakfu_server.storage.combat_drops import resolve as resolve_drops
        else:
            from wakfu_server.combat_drops import resolve as resolve_drops
        from wakfu_server.combat_drop_delivery import apply as apply_delivery
        from tests.test_combat_drop_delivery import GuaranteedDraw
        from wakfu_server.fight_store import settle_shared

        (
            store,
            account,
            main,
            generation,
            peer_account,
            peer,
            peer_generation,
            hero,
            fight,
        ) = fixture
        members_awarded = []
        actor_accounts = [
            (fight.actors[main["id"]], account),
            (fight.actors[peer["id"]], peer_account),
            (fight.actors[hero["id"]], account),
        ]
        self._install_stats(store, actor_accounts)
        monsters = [{"id": -200, "ref": 44, "level": 23}]

        def settle(db, members, source):
            for member in members:
                identity = member["character_id"]
                character = store.character(member["account_id"], identity, db)
                context, drop_context = settlement_contexts(
                    db, source, character, monsters
                )
                decision = resolve_policy(
                    store,
                    db,
                    account_id=member["account_id"],
                    generation=member["session_generation"],
                    character_id=identity,
                    fight_id=source.id,
                    context=context,
                    kamas_roll_index=0,
                )
                award = award_shared_member(
                    store,
                    db,
                    member["account_id"],
                    member["session_generation"],
                    identity,
                    source,
                    decision.policy,
                )
                batch = resolve_drops(
                    store,
                    db,
                    account_id=member["account_id"],
                    generation=member["session_generation"],
                    character_id=identity,
                    fight_id=source.id,
                    monsters=[{"actor_id": -200, "reference": 44}],
                    prospecting_bonus=source.actors[identity].effect_stats[33],
                    can_loot=True,
                    fight_context=drop_context,
                    rng=GuaranteedDraw(),
                )
                apply_delivery(store, db, batch)
                members_awarded.append((identity, award, batch))
                if fail_after_peer and identity == peer["id"]:
                    raise RuntimeError("injected settlement rollback")
            return members_awarded

        if finalizer is None:
            finalizer = (account, generation, main["id"])
        return settle_shared(store, *finalizer, fight, settle), members_awarded

    def test_storage_pipeline_settles_offline_roster_with_reconnected_old_generation(
        self,
    ):
        """The package imports used by the router share fight_store's capability."""
        fixture = self._fixture(offline_peer=False)
        (
            store,
            account,
            main,
            generation,
            peer_account,
            peer,
            peer_generation,
            hero,
            fight,
        ) = fixture
        # Disconnect the account that owns the main and hero, then reconnect it
        # with a new lease. Settlement must use the generations frozen in the
        # participant rows rather than adopting this newer session generation.
        with store.connection() as db:
            db.execute("DELETE FROM sessions WHERE account_id=%s", (account,))
        reconnected_generation = store.begin_session(account)
        self.assertNotEqual(reconnected_generation, generation)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT session_generation FROM combat_fight_participants "
                    "WHERE fight_id=%s AND character_id=%s",
                    (fight.id, main["id"]),
                ).fetchone()["session_generation"],
                generation,
            )
            self.assertEqual(
                db.execute(
                    "SELECT session_generation FROM combat_fight_participants "
                    "WHERE fight_id=%s AND character_id=%s",
                    (fight.id, hero["id"]),
                ).fetchone()["session_generation"],
                generation,
            )

        finalizer = (peer_account, peer_generation, peer["id"])
        with self.assertRaisesRegex(RuntimeError, "injected settlement rollback"):
            self._settle_real_pipeline(
                fixture,
                fail_after_peer=True,
                finalizer=finalizer,
                storage_modules=True,
                storage_drop_resolver=True,
            )
        with store.connection() as db:
            for character in (main, peer, hero):
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM fight_rewards "
                        "WHERE fight_id=%s AND character_id=%s",
                        (fight.id, character["id"]),
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM fight_drop_delivery_receipts "
                        "WHERE fight_id=%s AND character_id=%s",
                        (fight.id, character["id"]),
                    ).fetchone()["n"],
                    0,
                )

        _, awarded = self._settle_real_pipeline(
            fixture,
            finalizer=finalizer,
            storage_modules=True,
            storage_drop_resolver=True,
        )
        self.assertEqual(
            {identity for identity, _, _ in awarded},
            {main["id"], peer["id"], hero["id"]},
        )
        self.assertTrue(all(result["awarded"] for _, result, _ in awarded))
        self.assertTrue(all(not batch.replayed for _, _, batch in awarded))
        with store.connection() as db:
            for character in (main, peer, hero):
                identity = character["id"]
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM fight_rewards "
                        "WHERE fight_id=%s AND character_id=%s",
                        (fight.id, identity),
                    ).fetchone()["n"],
                    1,
                )
                receipts = db.execute(
                    "SELECT COALESCE(sum(awarded_quantity),0) AS awarded,"
                    "COALESCE(sum(inventory_quantity+temporary_quantity),0) AS delivered "
                    "FROM fight_drop_delivery_receipts WHERE fight_id=%s AND character_id=%s",
                    (fight.id, identity),
                ).fetchone()
                self.assertGreater(receipts["awarded"], 0)
                self.assertEqual(receipts["awarded"], receipts["delivered"])

        _, replayed = self._settle_real_pipeline(
            fixture,
            finalizer=finalizer,
            storage_modules=True,
            storage_drop_resolver=True,
        )
        self.assertTrue(all(not result["awarded"] for _, result, _ in replayed))
        self.assertTrue(all(batch.replayed for _, _, batch in replayed))

    def test_offline_peer_and_owned_hero_settle_rewards_and_drops_once(self):
        fixture = self._fixture()
        (
            store,
            account,
            main,
            generation,
            peer_account,
            peer,
            peer_generation,
            hero,
            fight,
        ) = fixture
        with self.assertRaisesRegex(RuntimeError, "injected settlement rollback"):
            self._settle_real_pipeline(fixture, fail_after_peer=True)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "finished",
            )
            for character in (main, peer, hero):
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                        (fight.id, character["id"]),
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM fight_drop_delivery_receipts WHERE fight_id=%s AND character_id=%s",
                        (fight.id, character["id"]),
                    ).fetchone()["n"],
                    0,
                )

        _, awarded = self._settle_real_pipeline(fixture)
        self.assertEqual(
            {identity for identity, _, _ in awarded},
            {main["id"], peer["id"], hero["id"]},
        )
        self.assertTrue(all(result["awarded"] for _, result, _ in awarded))
        self.assertTrue(all(not batch.replayed for _, _, batch in awarded))
        with store.connection() as db:
            for character in (main, peer, hero):
                identity = character["id"]
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                        (fight.id, identity),
                    ).fetchone()["n"],
                    1,
                    f"delivery receipt for character {identity}",
                )
                self.assertGreater(
                    db.execute(
                        "SELECT count(*) AS n FROM fight_drop_delivery_receipts WHERE fight_id=%s AND character_id=%s",
                        (fight.id, identity),
                    ).fetchone()["n"],
                    0,
                    f"delivery receipts for character {identity}",
                )
                receipt = db.execute(
                    "SELECT COALESCE(sum(awarded_quantity),0) AS awarded,"
                    "COALESCE(sum(inventory_quantity+temporary_quantity),0) AS delivered "
                    "FROM fight_drop_delivery_receipts WHERE fight_id=%s AND character_id=%s",
                    (fight.id, identity),
                ).fetchone()
                self.assertGreater(receipt["awarded"], 0)
                self.assertEqual(receipt["awarded"], receipt["delivered"])
            before_replay = {}
            for character in (main, peer, hero):
                identity = character["id"]
                before_replay[identity] = (
                    db.execute(
                        "SELECT uid,reference,quantity FROM inventory_items "
                        "WHERE character_id=%s ORDER BY uid",
                        (identity,),
                    ).fetchall(),
                    db.execute(
                        "SELECT uid,reference,quantity FROM temporary_combat_items "
                        "WHERE fight_id=%s AND character_id=%s ORDER BY uid",
                        (fight.id, identity),
                    ).fetchall(),
                    db.execute(
                        "SELECT xp,kamas FROM fight_rewards "
                        "WHERE fight_id=%s AND character_id=%s",
                        (fight.id, identity),
                    ).fetchone(),
                )
        _, replayed = self._settle_real_pipeline(fixture)
        self.assertTrue(all(not result["awarded"] for _, result, _ in replayed))
        self.assertTrue(all(batch.replayed for _, _, batch in replayed))
        with store.connection() as db:
            for identity, expected in before_replay.items():
                actual = (
                    db.execute(
                        "SELECT uid,reference,quantity FROM inventory_items "
                        "WHERE character_id=%s ORDER BY uid",
                        (identity,),
                    ).fetchall(),
                    db.execute(
                        "SELECT uid,reference,quantity FROM temporary_combat_items "
                        "WHERE fight_id=%s AND character_id=%s ORDER BY uid",
                        (fight.id, identity),
                    ).fetchall(),
                    db.execute(
                        "SELECT xp,kamas FROM fight_rewards "
                        "WHERE fight_id=%s AND character_id=%s",
                        (fight.id, identity),
                    ).fetchone(),
                )
                self.assertEqual(actual, expected)

    def test_offline_main_and_hero_are_paid_by_other_live_finalizer(self):
        fixture = self._fixture(offline_peer=False)
        (
            store,
            account,
            main,
            generation,
            peer_account,
            peer,
            peer_generation,
            hero,
            fight,
        ) = fixture
        with store.connection() as db:
            db.execute("DELETE FROM sessions WHERE account_id=%s", (account,))
        _, awarded = self._settle_real_pipeline(
            fixture, finalizer=(peer_account, peer_generation, peer["id"])
        )
        self.assertEqual(
            {identity for identity, _, _ in awarded},
            {main["id"], peer["id"], hero["id"]},
        )
        for identity in (main["id"], hero["id"]):
            self.assertTrue(
                next(result for item_id, result, _ in awarded if item_id == identity)[
                    "awarded"
                ]
            )

    def test_offline_recipient_requires_exact_durable_scope_and_transaction(self):
        from wakfu_server.combat_reward_ownership import (
            _SETTLEMENT,
            _durable_settlement_scope,
            lock_recipient,
        )
        from dataclasses import replace

        fixture = self._fixture()
        (
            store,
            account,
            main,
            generation,
            peer_account,
            peer,
            peer_generation,
            hero,
            fight,
        ) = fixture
        with store.connection() as db:
            with self.assertRaisesRegex(ValueError, "no current account lease"):
                lock_recipient(
                    store, db, peer_account, peer_generation, peer["id"], fight.id
                )

        rows = []
        with store.connection() as db:
            rows = list(
                db.execute(
                    "SELECT p.account_id,p.character_id,p.session_generation,p.team,"
                    "false AS withdrawn FROM combat_fight_participants p WHERE p.fight_id=%s",
                    (fight.id,),
                )
            )
            with _durable_settlement_scope(db, fight, rows):
                lock_recipient(
                    store, db, peer_account, peer_generation, peer["id"], fight.id
                )
                token = _SETTLEMENT.set(
                    replace(_SETTLEMENT.get(), transaction_id="wrong-transaction")
                )
                try:
                    with self.assertRaisesRegex(
                        ValueError, "settlement transaction changed"
                    ):
                        lock_recipient(
                            store,
                            db,
                            peer_account,
                            peer_generation,
                            peer["id"],
                            fight.id,
                        )
                finally:
                    _SETTLEMENT.reset(token)
                for wrong in (
                    (account + 100000, peer_generation, peer["id"], fight.id),
                    (peer_account, peer_generation, main["id"], fight.id),
                    (peer_account, "wrong-generation", peer["id"], fight.id),
                    (peer_account, peer_generation, peer["id"], fight.id + 1),
                ):
                    with self.subTest(wrong=wrong), self.assertRaisesRegex(
                        ValueError, "locked settlement roster"
                    ):
                        lock_recipient(store, db, *wrong)
                with store.connection() as other_db:
                    with self.assertRaisesRegex(ValueError, "locked settlement roster"):
                        lock_recipient(
                            store,
                            other_db,
                            peer_account,
                            peer_generation,
                            peer["id"],
                            fight.id,
                        )

                def worker():
                    with store.connection() as worker_db:
                        return lock_recipient(
                            store,
                            worker_db,
                            peer_account,
                            peer_generation,
                            peer["id"],
                            fight.id,
                        )

                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(worker)
                    with self.assertRaisesRegex(ValueError, "no current account lease"):
                        future.result()

        peer_row = next(dict(row) for row in rows if row["character_id"] == peer["id"])
        for altered in (
            {**peer_row, "team": 1},
            {**peer_row, "withdrawn": True},
        ):
            with store.connection() as db:
                altered_rows = [
                    dict(row) for row in rows if row["character_id"] != peer["id"]
                ]
                altered_rows.append(altered)
                with _durable_settlement_scope(db, fight, altered_rows):
                    with self.assertRaisesRegex(ValueError, "locked settlement roster"):
                        lock_recipient(
                            store,
                            db,
                            peer_account,
                            peer_generation,
                            peer["id"],
                            fight.id,
                        )

        from psycopg import connect

        idle_db = connect(
            store.database.conninfo,
            **store.database.connection_kwargs,
            autocommit=True,
        )
        try:
            with self.assertRaisesRegex(
                ValueError, "locked durable settlement transaction"
            ):
                with _durable_settlement_scope(idle_db, fight, rows):
                    self.fail("scope opened without an active transaction")
        finally:
            idle_db.close()
