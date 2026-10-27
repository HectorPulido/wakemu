"""Earned Rift settlement component: real durable actors, no replayed battle."""
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import combat_rewards, reward_policy, rift_runtime
from wakfu_server import rift_currency_rewards as currency
from wakfu_server import rift_rewards
from wakfu_server.characters import heroes
from wakfu_server.combat_lifecycle import prepare_finish_shared
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.monsters import reference
from wakfu_server.progression import level_xp
from wakfu_server.rift_encounter_roles import roles_for_catalog
from wakfu_server.rift_policy import select_wave


class RiftEarnedRewardTests(PostgresCase):
    def _assert_loot(self, db, fight_id, eligible_ids, multiplier):
        from wakfu_server import combat_drops
        from decimal import Decimal

        expected_calls = 0
        for identity in eligible_ids:
            batch = combat_drops._stored_batch(db, fight_id, identity)
            self.assertIsNotNone(batch)
            snapshot = batch.snapshot
            common = snapshot["rift_common_quantity"]
            self.assertEqual(common["factor"]["multiplier"], multiplier)
            self.assertEqual(common["factor"]["reached_wave"], 4)
            self.assertFalse(common["probability_draws_multiplied"])
            self.assertEqual(len(snapshot["monsters"]), 13)
            ledger = common["original_successes"]
            self.assertTrue(ledger)
            keys = [
                (row.defeated_actor_id, row.drop_row_index, row.attempt_index)
                for row in batch.decisions
            ]
            self.assertEqual(len(keys), len(set(keys)))
            stored = dict(zip(keys, batch.decisions))
            for entry in ledger:
                original = entry["original"]
                self.assertEqual(entry["multiplier"], multiplier)
                self.assertEqual(
                    sum(row["quantity"] for row in entry["segments"]),
                    original["quantity"] * multiplier,
                )
                for row in entry["segments"]:
                    decision = stored[
                        (
                            original["defeated_actor_id"],
                            row["drop_row_index"],
                            row["attempt_index"],
                        )
                    ]
                    self.assertEqual(decision.quantity, row["quantity"])
                    self.assertTrue(1 <= decision.quantity <= 32767)
                    self.assertEqual(
                        decision.base_probability, Decimal(original["base_probability"])
                    )
                    self.assertEqual(
                        decision.draw_numerator, original["draw_numerator"]
                    )
            extra = snapshot["rift_additional_items"]
            self.assertEqual(extra["policy"]["losses"], "earned_native_kills")
            self.assertTrue(extra["draws"])
            for draw in extra["draws"]:
                key = (
                    min(row["actor_id"] for row in snapshot["monsters"]),
                    draw["receipt_identity"]["drop_row_index"],
                    draw["receipt_identity"]["attempt_index"],
                )
                decision = stored[key]
                self.assertEqual(decision.success, draw["success"])
                if draw["success"]:
                    self.assertEqual(decision.quantity, draw["quantity"])
            counter = [0]

            def native_draw(limit):
                counter[0] += 1
                return 0

            modifiers = snapshot["modifiers"]
            native = combat_drops.plan_player_drops(
                monsters=snapshot["monsters"],
                character_id=identity,
                prospecting_bonus=snapshot["prospection_bonus"],
                can_loot=snapshot["can_loot"],
                fight_context=snapshot["fight_context"],
                shop_consumable_factor=snapshot["shop_consumable_drop_factor"],
                rng=native_draw,
                **modifiers
            )
            # Receipt splitting/quantity scaling adds no probability draws.
            self.assertEqual(len(snapshot["allocation"]["decisions"]), len(native))
            expected_calls += counter[0] + len(extra["draws"]) * 3
        self.assertEqual(self._loot_calls, expected_calls)

    def _company(self):
        self.account = self.store.register("rift-earned", "earned-password")["id"]
        self.ids = [
            self.store.create_character(self.account, name)["id"]
            for name in ("Riftearnedmain", "Riftearnedhero", "Riftearnedthird")
        ]
        self.generation = self.store.begin_session(self.account, ttl=10000)
        self.store.select_character(self.account, self.generation, self.ids[0])
        for identity in self.ids[1:]:
            heroes.add(self.store, self.account, self.generation, self.ids[0], identity)
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=30 WHERE id=ANY(%s)", (self.ids,))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=ANY(%s)",
                (level_xp(30), self.ids),
            )

    def _fixture(self, *, won=False, withdrawn=False, no_kills=False, terminal=True):
        characters = {
            identity: self.store.character(self.account, identity)
            for identity in self.ids
        }
        with self.store.connection() as db:
            run = rift_runtime.enter(
                db,
                3,
                self.ids[0],
                self.ids,
                seed="earned-four-waves",
                authorize=lambda catalog, members: True,
            )
            first = select_wave(run["catalog"], run["policy"], run["seed"], 1)
            roles = roles_for_catalog(
                run["catalog"], run["policy"], monster_references=first
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            for identity in self.ids:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                    "VALUES(%s,%s,%s,%s,%s)",
                    (
                        fight_id,
                        identity,
                        self.account,
                        roles.player_team,
                        self.generation,
                    ),
                )
            rift_runtime.start(db, run["instance_id"], self.ids[0], fight_id)
            wave_rows = []
            for wave in range(1, 2 if no_kills else 5):
                refs = select_wave(run["catalog"], run["policy"], run["seed"], wave)
                ids = [-(wave * 100 + index + 1) for index in range(len(refs))]
                rift_runtime.bind_wave(
                    db, run["instance_id"], wave, tuple(zip(ids, refs))
                )
                wave_rows.append((wave, ids, refs))
                if wave < 4 and not no_kills:
                    rift_runtime.record_wave(
                        db, run["instance_id"], wave, ids, turn=wave + 1
                    )
            run = rift_runtime._run(db, run["instance_id"])
            if withdrawn:
                db.execute(
                    "INSERT INTO combat_pve_withdrawals(fight_id,character_id,account_id,session_generation,created_at) "
                    "VALUES(%s,%s,%s,%s,%s)",
                    (
                        fight_id,
                        self.ids[2],
                        self.account,
                        self.generation,
                        self.store.now(),
                    ),
                )
        actors = []
        for index, (identity, character) in enumerate(characters.items()):
            actor = Actor(
                identity,
                roles.player_team,
                (index, 0, 0),
                character["hp"],
                6,
                3,
                100,
                character["level"],
                self.account,
                True,
            )
            actor.effect_stats = {33: 0, 36: 20, 119: 100}
            if terminal and not won:
                actor.hp = 0
            if withdrawn and identity == self.ids[2]:
                actor.pve_withdrawn = True
            actors.append(actor)
        sources = {}
        for wave, ids, refs in wave_rows:
            for index, (identity, ref) in enumerate(zip(ids, refs)):
                level = reference(ref)["min_level"]
                actor = Actor(
                    identity,
                    roles.npc_team,
                    (len(actors), 0, 0),
                    20,
                    4,
                    2,
                    1 if terminal else 500,
                    level,
                )
                if not no_kills and (wave < 4 or index == 0):
                    actor.hp = 0
                actors.append(actor)
                sources[identity] = dict(
                    id=identity, ref=ref, level=level, instance_id=run["instance_id"]
                )
        cells = {actor.position for actor in actors}
        fight = Fight(
            fight_id,
            actors,
            cells,
            {
                roles.player_team: {
                    actor.position for actor in actors if actor.controlled
                },
                roles.npc_team: {
                    actor.position for actor in actors if not actor.controlled
                },
            },
        )
        fight.native_encounter_roles = roles.record()
        if terminal:
            fight.phase = "finished"
            fight.winner = roles.player_team if won else roles.npc_team
            fight.native_timeline_round = 40 if won else 7
        fight.rift_wave_state = {"instance_id": run["instance_id"]}
        if not terminal:
            fight.rift_wave_state.update(
                wave=run["wave"],
                turn_budget=run["policy"]["turn_budget"],
                wave_actor_ids=wave_rows[-1][1],
            )
        fight.rift_monsters = sources
        return run, fight, characters

    def _settle(self, run, fight, characters, *, fail=False):
        roles = roles_for_catalog(run["catalog"], run["policy"])
        eligible = tuple(
            identity
            for identity in self.ids
            if not getattr(fight.actors[identity], "pve_withdrawn", False)
        )
        self._loot_calls = 0

        def loot_rng(limit):
            self.assertGreater(limit, 0)
            self._loot_calls += 1
            return 0

        def terminal(db):
            return rift_runtime.settle(
                db,
                run["instance_id"],
                fight.id,
                outcome="won" if fight.winner == roles.player_team else "lost",
                turn=fight.native_timeline_round,
                reconcile_earned_rewards=True,
                apply_rewards=lambda connection, canonical, result: rift_rewards.apply(
                    connection,
                    canonical,
                    result,
                    store=self.store,
                    eligible_character_ids=eligible,
                    rng=loot_rng,
                    fight=fight,
                ),
            )

        def policy(db, member, character):
            terminal(db)
            value = currency.resolve(
                self.store,
                db,
                account_id=member["account_id"],
                generation=member["session_generation"],
                character_id=member["character_id"],
                fight=fight,
                character=character,
                eligible_character_ids=eligible,
            )
            if fail:
                raise RuntimeError("after earned Rift policy")
            return value

        def group(db, *unused):
            terminal(db)
            return {"applied": True, "packets": []}

        def loot(db, member, reward):
            return rift_rewards.delivery(
                db, self.store, run["instance_id"], member["character_id"]
            )

        metadata = {
            identity: dict(
                kind="player",
                account_id=self.account,
                name=character["name"],
                breed=character["breed"],
                is_male=character["sex"] == 0,
            )
            for identity, character in characters.items()
        }
        metadata.update(
            {
                identity: dict(kind="monster", ref=source["ref"])
                for identity, source in fight.rift_monsters.items()
            }
        )
        metadata.update(
            {
                int(identity): dict(kind="monster", ref=source["ref"])
                for identity, source in getattr(
                    fight, "native_companion_sources", {}
                ).items()
            }
        )
        return prepare_finish_shared(
            self.store,
            self.account,
            self.generation,
            self.ids[0],
            RuntimeMessages(fight),
            metadata,
            duration_ms=1000,
            fight_instance_id=fight.id,
            policy_resolver=policy,
            loot_resolver=loot,
            group_settlement=group,
            expected_accounts={self.account},
            owner_character_ids={self.account: self.ids[0]},
        )

    def test_actual_mutual_ko_producer_pays_loss_once_and_returns_owned_heroes(self):
        """Registry/FSM integration, not an official-client or native-class Ready claim."""
        import struct
        from wakfu_server.combat_shared import Registry, Session
        from wakfu_server.combat_lifecycle import return_to_world
        from wakfu_server.rift_dispatch_combat import finish_accepted_action

        self._company()
        run, fight, characters = self._fixture(no_kills=True, terminal=False)
        roles = roles_for_catalog(run["catalog"], run["policy"])
        session = Session(
            self.account,
            self.ids[0],
            self.generation,
            run["catalog"]["map_id"],
            run["instance_id"],
        )
        registry = Registry(lambda candidate: candidate == session)
        shared = registry.register(fight, session, runtime=RuntimeMessages(fight))

        def unexpected_birth(*args, **kwargs):
            raise AssertionError(
                "A mutually defeated party must not create another wave"
            )

        shared.join_context = dict(
            rift_accepted_action=lambda view, candidate, runtime, packets: finish_accepted_action(
                candidate, runtime, packets, initialize_actor=unexpected_birth
            )
        )
        registry.ready(
            fight.id,
            session,
            True,
            packets=lambda candidate, runtime: [runtime._flush()],
        )
        current = shared.fight.current
        self.assertIsNotNone(current)
        self.assertFalse(current.controlled)
        source = shared.fight

        def mutual(candidate, runtime):
            with candidate.effect_resolution():
                for identity in tuple(candidate.actors):
                    candidate.apply_effect_damage(
                        current.id, identity, candidate.actors[identity].hp
                    )
            return [runtime._flush()]

        registry.execute_server(
            fight.id, current.id, mutual, expected_sequence=shared.sequence
        )
        actual = shared.fight
        self.assertIsNot(actual, source)
        self.assertTrue(all(actor.hp > 0 for actor in source.actors.values()))
        self.assertTrue(all(actor.hp == 0 for actor in actual.actors.values()))
        self.assertEqual((actual.phase, actual.winner), ("finished", roles.npc_team))
        self.assertEqual(actual.rift_wave_state["outcome"], "defeated")
        self.assertIsNone(actual.rift_wave_state.get("pending_wave"))
        with patch.object(reward_policy.secrets, "randbelow", return_value=0):
            self._settle(run, actual, characters)
        with self.store.connection() as db:
            terminal = db.execute(
                "SELECT outcome,result FROM rift_settlement_receipts WHERE fight_id=%s",
                (actual.id,),
            ).fetchone()
            self.assertEqual(terminal["outcome"], "lost")
            self.assertEqual(terminal["result"]["completed_waves"], 0)
            rows = db.execute(
                "SELECT character_id,xp,kamas,snapshot FROM fight_reward_policy_receipts "
                "WHERE fight_id=%s",
                (actual.id,),
            ).fetchall()
            self.assertEqual({row["character_id"] for row in rows}, set(self.ids))
            for row in rows:
                self.assertEqual(row["snapshot"]["multiplier"], 10)
                self.assertEqual(
                    row["xp"], row["snapshot"]["ordinary_baseline"]["xp"] * 10
                )
                self.assertEqual(
                    row["kamas"], row["snapshot"]["ordinary_baseline"]["kamas"] * 10
                )
                self.assertEqual(len(row["snapshot"]["defeated_native_monsters"]), 4)
            deliveries = db.execute(
                "SELECT character_id,awarded_quantity,inventory_quantity,temporary_quantity "
                "FROM fight_drop_delivery_receipts WHERE fight_id=%s",
                (actual.id,),
            ).fetchall()
            self.assertEqual({row["character_id"] for row in deliveries}, set(self.ids))
            self.assertTrue(
                all(
                    row["awarded_quantity"] > 0
                    and row["inventory_quantity"] + row["temporary_quantity"]
                    == row["awarded_quantity"]
                    for row in deliveries
                )
            )
            before = {
                identity: combat_rewards.load(
                    db, self.store.character(self.account, identity, db)
                )
                for identity in self.ids
            }
        current_character = self.store.character(self.account, self.ids[0])
        returned = return_to_world(
            self.store,
            self.account,
            self.generation,
            current_character,
            RuntimeMessages(actual),
            struct.pack(">iB", actual.id, 1),
            wp=6,
        )
        self.assertTrue(returned["applied"])
        again = return_to_world(
            self.store,
            self.account,
            self.generation,
            self.store.character(self.account, self.ids[0]),
            RuntimeMessages(actual),
            struct.pack(">iB", actual.id, 1),
            wp=6,
        )
        self.assertFalse(again["applied"])
        with self.store.connection() as db:
            for identity in self.ids:
                self.assertEqual(
                    combat_rewards.load(
                        db, self.store.character(self.account, identity, db)
                    ),
                    before[identity],
                )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_health_exits WHERE fight_id=%s",
                    (actual.id,),
                ).fetchone()["n"],
                3,
            )

    def _admitted_native_companion_and_hero_fixture(self):
        """Real sidekick admission and payout, with a declared native arena component."""
        import struct
        from wakfu_server.characters import companions
        from wakfu_server.inventory_items import grant
        from wakfu_server.combat_companions import (
            admit_owned_companions,
            registered_companion_ids,
        )
        from wakfu_server.combat_shared import Session
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.equipment_stats import combat_resources, effective_character
        from wakfu_server.monsters import owned_instance

        self._company()
        heroes.remove(
            self.store, self.account, self.generation, self.ids[0], self.ids[2]
        )
        self.ids = self.ids[:2]
        main = self.store.character(self.account, self.ids[0])
        descriptor = next(
            row for row in companions.descriptors().values() if row["item_ref"] == 17878
        )
        container = next(
            row["uid"] for row in main["inventory_containers"] if row["kind"] == 0
        )
        item = grant(
            self.store,
            self.account,
            self.generation,
            main["id"],
            reference=17878,
            quantity=1,
            container=container,
            slot=0,
            allowed_references={17878},
        )
        activated = companions.use(
            self.store,
            self.account,
            self.generation,
            main["id"],
            struct.pack(">iq", descriptor["action_id"], item["uid"]),
            in_fight=False,
        )
        companion_id = activated["companion"]["id"]
        companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            main["id"],
            struct.pack(">q", companion_id),
        )
        run, base, characters = self._fixture(no_kills=True, terminal=False)
        characters = {
            identity: effective_character(character)
            for identity, character in characters.items()
        }
        roles = roles_for_catalog(run["catalog"], run["policy"])
        arena = local_arena(
            1134, 0, (-4, -18, 0), (-4, -17, 0), relocate_monsters=False
        )
        placement = roles.placement_cells(
            arena["placement_cells"][0], arena["placement_cells"][1]
        )
        for team in (roles.player_team, roles.npc_team):
            for actor, position in zip(
                (a for a in base.actors.values() if a.team == team),
                sorted(placement[team]),
            ):
                actor.position = position
        resources = {
            identity: combat_resources(character)
            for identity, character in characters.items()
        }
        monsters = {
            identity: owned_instance(
                source["ref"],
                source["level"],
                identity,
                map_id=1134,
                x=base.actors[identity].position[0],
                y=base.actors[identity].position[1],
                z=base.actors[identity].position[2],
                team=1,
            )
            for identity, source in base.rift_monsters.items()
        }
        fresh = [
            Actor(
                identity,
                roles.player_team,
                base.actors[identity].position,
                character["hp"],
                resources[identity]["ap"],
                resources[identity]["mp"],
                resources[identity]["initiative"],
                base.actors[identity].effective_level,
                self.account,
                True,
                max_hp=character["max_hp"],
            )
            for identity, character in characters.items()
        ]
        fresh.extend(
            Actor(
                identity,
                roles.npc_team,
                base.actors[identity].position,
                source["hp"],
                source["ap"],
                source["mp"],
                source["initiative"],
                source["level"],
                max_hp=source["max_hp"],
            )
            for identity, source in monsters.items()
        )
        fight = Fight(
            base.id, fresh, arena["validated_cells"], placement, arena["valid_edges"]
        )
        fight.native_encounter_roles = base.native_encounter_roles
        fight.rift_wave_state, fight.rift_monsters = (
            base.rift_wave_state,
            base.rift_monsters,
        )
        fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        freeze_terrain(fight)
        initialize_global_pv_collections(
            fight, tuple(fight.actors), controller_registration=True
        )
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters=monsters,
            wp_resources={
                **{
                    identity: (row["wp"], row["wp"])
                    for identity, row in resources.items()
                },
                **{
                    identity: (row["wp"], row["wp"])
                    for identity, row in monsters.items()
                },
            },
            running_effects={identity: () for identity in fight.actors},
            initial_effect_uid=1,
        )
        session = Session(
            self.account, main["id"], self.generation, 1134, run["instance_id"]
        )
        with self.store.connection() as db:
            admitted = admit_owned_companions(
                db, self.store, session, fight, owner_character=characters[main["id"]]
            )
        fight = admitted["fight"]
        self.assertEqual(registered_companion_ids(fight), {companion_id})
        self.assertTrue(fight.actors[companion_id].controlled)
        return run, fight, characters, companion_id

    def test_admitted_native_companion_and_hero_receive_owned_earned_settlement(self):
        (
            run,
            fight,
            characters,
            companion_id,
        ) = self._admitted_native_companion_and_hero_fixture()
        main = characters[self.ids[0]]
        roles = roles_for_catalog(run["catalog"], run["policy"])
        fight.ready(self.account, True)
        with fight.effect_resolution():
            for identity in tuple(fight.actors):
                fight.apply_effect_damage(
                    next(iter(fight.rift_monsters)), identity, fight.actors[identity].hp
                )
        self.assertEqual((fight.phase, fight.winner), ("finished", roles.npc_team))
        with patch.object(reward_policy.secrets, "randbelow", return_value=0):
            packets = self._settle(run, fight, characters)
        self.assertTrue(packets[self.account])
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT character_id,snapshot,xp FROM fight_reward_policy_receipts WHERE fight_id=%s",
                (fight.id,),
            ).fetchall()
            self.assertEqual({row["character_id"] for row in rows}, set(self.ids))
            for row in rows:
                context = row["snapshot"]["ordinary_baseline"]["context"]
                players = [actor for actor in context["winners"] if actor["player"]]
                self.assertEqual(
                    {actor["character_id"] for actor in players}, set(self.ids)
                )
                sidekicks = [
                    actor for actor in context["winners"] if not actor["player"]
                ]
                self.assertEqual(len(sidekicks), 1)
                self.assertFalse(sidekicks[0]["eligible"])
                self.assertIsNone(sidekicks[0]["character_id"])
                self.assertEqual(row["snapshot"]["multiplier"], 10)
            member = db.execute(
                "SELECT owner_experience_award,experience_settled_at,health_settled_at "
                "FROM combat_fight_companions WHERE fight_id=%s AND companion_id=%s",
                (fight.id, companion_id),
            ).fetchone()
            self.assertEqual(
                member["owner_experience_award"],
                next(row["xp"] for row in rows if row["character_id"] == main["id"]),
            )
            self.assertIsNotNone(member["experience_settled_at"])
            self.assertIsNotNone(member["health_settled_at"])
        with patch.object(
            reward_policy,
            "resolve",
            side_effect=AssertionError("companion payout reroll"),
        ):
            self._settle(run, fight, characters)
        self.assertEqual(self._loot_calls, 0)

    def test_registered_companion_withdrawal_keeps_human_receipts_and_retires_owned_company(
        self,
    ):
        """Ordinary placement-exit component; this does not prove Rift late admission."""
        import struct
        from wakfu_server import fight_store
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.equipment_stats import combat_resources, effective_character

        (
            run,
            fight,
            characters,
            companion_id,
        ) = self._admitted_native_companion_and_hero_fixture()
        main = self.store.character(self.account, self.ids[0])
        peer_account = self.store.register("rift-withdraw-peer", "peer-password")["id"]
        peer = self.store.create_character(peer_account, "Riftwithdrawpeer")
        peer_generation = self.store.begin_session(peer_account)
        self.store.select_character(peer_account, peer_generation, peer["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s WHERE id=%s",
                (main["map_id"], main.get("instance_id", 0), peer["id"]),
            )
            db.execute(
                "UPDATE combat_fights SET status='placement' WHERE id=%s", (fight.id,)
            )
        peer = self.store.character(peer_account, peer["id"])
        adapter = CombatSessionAdapter(self.store)
        owner = adapter.session(self.account, self.generation, main)
        teammate = adapter.session(peer_account, peer_generation, peer)
        shared = adapter.register(owner, fight, runtime=RuntimeMessages(fight))
        team = fight.actors[main["id"]].team
        occupied = {actor.position for actor in fight.actors.values()}
        position = next(
            cell for cell in sorted(fight.placement[team]) if cell not in occupied
        )
        projected = effective_character(peer)
        resources = combat_resources(projected)
        actor = Actor(
            peer["id"],
            team,
            position,
            projected["hp"],
            resources["ap"],
            resources["mp"],
            resources["initiative"],
            projected["level"],
            peer_account,
            True,
            max_hp=projected["max_hp"],
        )
        build_player_snapshot(
            projected,
            actor,
            wp_current=resources["wp"],
            wp_maximum=resources["wp"],
            running_effects=(),
        ).install(actor)

        def persist_member(candidate, newcomer, original, session):
            with self.store.connection() as db:
                fight_store.join_participant(
                    self.store,
                    db,
                    peer_account,
                    peer_generation,
                    peer["id"],
                    fight.id,
                    target_character_id=main["id"],
                    team=team,
                )

        adapter.registry.join(
            teammate,
            struct.pack(">qB", main["id"], team),
            actor,
            actor_payload=lambda *args: (b"stats", b"effects"),
            bootstrap_packets=lambda *args: [(12847, b"placement")],
            persist_member=persist_member,
        )
        receipt = adapter.withdraw_pve(owner, main, b"")
        for identity in (*self.ids, companion_id):
            self.assertTrue(shared.fight.actors[identity].pve_withdrawn)
            self.assertEqual(shared.fight.actors[identity].hp, 0)
        self.assertGreater(shared.fight.actors[peer["id"]].hp, 0)
        self.assertEqual(shared.fight.phase, "placement")
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT character_id FROM combat_pve_withdrawals WHERE fight_id=%s",
                (fight.id,),
            ).fetchall()
            self.assertEqual({row["character_id"] for row in rows}, set(self.ids))
            companion = db.execute(
                "SELECT experience_award,experience_settled_at,health_settled_at "
                "FROM combat_fight_companions WHERE fight_id=%s AND companion_id=%s",
                (fight.id, companion_id),
            ).fetchone()
            self.assertEqual(companion["experience_award"], 0)
            self.assertIsNotNone(companion["experience_settled_at"])
            self.assertIsNotNone(companion["health_settled_at"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
                0,
            )
        self.assertIs(adapter.withdraw_pve(owner, receipt["character"], b""), receipt)
        returned = adapter.return_withdrawn_pve(
            owner, fight.id, receipt["character"], struct.pack(">iB", fight.id, 1), wp=6
        )
        self.assertIsNotNone(returned["character"])
        for identity in (*self.ids, companion_id):
            self.assertNotIn(identity, adapter.registry.by_actor)
        self.assertEqual(adapter.registry.by_character[peer["id"]], fight.id)

    def test_win_loss_earned_wave_factor_heroes_withdrawal_replay_and_rollback(self):
        # Pure amount oracle is independent of the configured normal XP formula.
        example = currency.scaled_policy(
            combat_rewards.Policy(xp=100, kamas=100), {"xp": 0, "kamas": 0}, 4 * 10
        )
        self.assertEqual((example.xp, example.kamas), (4000, 4000))
        self._company()
        for won in (False, True):
            run, fight, characters = self._fixture(won=won, withdrawn=True)
            original_winner, original_hp = fight.winner, {
                key: actor.hp for key, actor in fight.actors.items()
            }
            with self.store.connection() as db:
                before_totals = {
                    identity: combat_rewards.load(db, character)
                    for identity, character in characters.items()
                }
            with patch.object(reward_policy.secrets, "randbelow", return_value=0):
                with self.assertRaisesRegex(RuntimeError, "after earned Rift policy"):
                    self._settle(run, fight, characters, fail=True)
            with self.store.connection() as db:
                for table in (
                    "fight_rewards",
                    "fight_reward_policy_receipts",
                    "fight_drop_awards",
                    "rift_item_reward_receipts",
                ):
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) AS n FROM " + table + " WHERE fight_id=%s",
                            (fight.id,),
                        ).fetchone()["n"],
                        0,
                    )
                self.assertEqual(
                    rift_runtime._run(db, run["instance_id"])["status"], "running"
                )
                for identity, character in characters.items():
                    self.assertEqual(
                        combat_rewards.load(db, character), before_totals[identity]
                    )
            with patch.object(reward_policy.secrets, "randbelow", return_value=0):
                packets = self._settle(run, fight, characters)
            self.assertTrue(packets[self.account])
            with self.store.connection() as db:
                rows = db.execute(
                    "SELECT character_id,xp,kamas,snapshot FROM fight_reward_policy_receipts "
                    "WHERE fight_id=%s ORDER BY character_id",
                    (fight.id,),
                ).fetchall()
                self.assertEqual(
                    {row["character_id"] for row in rows}, set(self.ids[:2])
                )
                for row in rows:
                    baseline = row["snapshot"]["ordinary_baseline"]
                    self.assertEqual(row["xp"], baseline["xp"] * 40)
                    self.assertEqual(row["kamas"], baseline["kamas"] * 40)
                    self.assertEqual(
                        row["snapshot"]["factor_policy"]["reached_wave"], 4
                    )
                    self.assertEqual(
                        row["snapshot"]["outcome"], "won" if won else "lost"
                    )
                    self.assertEqual(
                        len(row["snapshot"]["defeated_native_monsters"]), 13
                    )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM rift_item_reward_receipts WHERE fight_id=%s",
                        (fight.id,),
                    ).fetchone()["n"],
                    2,
                )
                self._assert_loot(db, fight.id, self.ids[:2], 40)
                saved = {
                    identity: combat_rewards.load(
                        db, self.store.character(self.account, identity, db)
                    )
                    for identity in self.ids
                }
            with patch.object(
                reward_policy, "resolve", side_effect=AssertionError("currency reroll")
            ), patch.object(
                rift_rewards, "plan", side_effect=AssertionError("rare reroll")
            ):
                self._settle(run, fight, characters)
            self.assertEqual(self._loot_calls, 0)
            with self.reopen().connection() as db:
                for identity in self.ids:
                    self.assertEqual(
                        combat_rewards.load(
                            db, self.store.character(self.account, identity, db)
                        ),
                        saved[identity],
                    )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                        (fight.id,),
                    ).fetchone()["n"],
                    2,
                )
            self.assertEqual(fight.winner, original_winner)
            self.assertEqual(
                {key: actor.hp for key, actor in fight.actors.items()}, original_hp
            )
        run, fight, characters = self._fixture(no_kills=True)
        self._settle(run, fight, characters)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_drop_awards WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
                0,
            )
