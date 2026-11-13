"""Final Airyna lesson settles child and parent rewards atomically."""
from types import SimpleNamespace

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import rii_owned_lesson, rii_states_contract, storage


class StateLessonSettlementTests(PostgresCase):
    def test_final_lesson_claims_both_rewards_and_is_idempotent(self):
        account = self.store.register("states-owner", "test-password")["id"]
        character = self.store.create_character(account, "States Flow")
        owner = character["id"]
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, owner)
        child_reward = {"d": 90001, "aeV": 3, "ckl": [20016]}
        parent_reward = {"d": 90002, "aeV": 2, "ckl": [755]}
        child = {
            "d": 5143,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjK": [child_reward],
            "cjJ": [
                {
                    "d": oid,
                    "ckc": "IsAchievementObjectiveComplete(10610)"
                    if oid == 10611
                    else "",
                    "cke": "",
                }
                for oid in (10574, 10575, 10576, 10608, 10609, 10610, 10611)
            ],
        }
        parent = {
            "d": 5160,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjK": [parent_reward],
            "cjJ": [{"d": 10616, "ckc": "", "cke": ""}],
        }
        actor = -30
        monster = {"id": actor, "ref": 5466}
        # Exercise the exposed dialogue, then all four server-owned reactions
        # before feeding their resulting contract to the transactional finisher.
        from wakfu_server import rii_airyna_dialogue
        from test_npc_observed_dialogue import captured_row

        npc = captured_row(-1706442046308339, 5460, 1388, 0, -19, 3, 3, 5755, 1390)
        current = dict(
            id=owner,
            account_id=account,
            map_id=1388,
            instance_id=0,
            x=0,
            y=-18,
            z=3,
            level=10,
        )
        session, _ = rii_airyna_dialogue.begin(
            lambda: current,
            lambda: [npc],
            lambda: {10606: True, 10610: True},
            npc["actor_id"],
            1389,
        )
        session.choose(5787, 13328)
        player = SimpleNamespace(id=owner, team=0, hp=100, position=(6, 0, 0))
        sack = SimpleNamespace(id=actor, team=1, hp=100, position=(0, 0, 0))
        fight = SimpleNamespace(
            id=777,
            phase="active",
            winner=None,
            actors={owner: player, actor: sack},
            native_active_spell_id=7967,
            rii_states_lesson_contract={
                "owner": owner,
                "target": actor,
                "hits": 0,
                "initialized": True,
                "green": [1, 0, 0],
                "red": [0, 1, 0],
            },
        )
        fight.apply_effect_damage = lambda _source, _target, amount: setattr(
            sack, "hp", sack.hp - amount
        )
        for position in ((1, 0, 0), (0, 1, 0)):
            player.position = position
            damage = rii_states_contract.hit(
                fight,
                source_id=owner,
                target_id=actor,
                effect_reference=rii_states_contract.SPELL_EFFECT,
                damage=1,
            )
            self.assertEqual(damage, 25)
            fight.apply_effect_damage(owner, actor, damage)
        player.position = (1, 0, 0)
        self.assertTrue(rii_states_contract.turn_end(fight, owner))
        player.position = (6, 0, 0)
        self.assertTrue(rii_states_contract.turn_end(fight, owner))
        self.assertEqual((fight.rii_states_lesson_contract["hits"], sack.hp), (4, 0))
        fight.phase, fight.winner = "finished", 0
        member = {
            "character_id": owner,
            "account_id": account,
            "session_generation": generation,
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,2)",
                ("b" * 64, Jsonb({}), b"fixture"),
            )
            for identity, definition in ((5143, child), (5160, parent)):
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,%s,%s)",
                    ("b" * 64, identity, Jsonb({"native": definition})),
                )
            state = storage.load_locked(db, owner)
            state["running"] = [5143, 5160]
            state["objectives"] = [10574, 10575, 10576, 10608, 10609, 10610]
            storage.store(db, owner, state)
            storage.record_event(
                db,
                owner,
                rii_owned_lesson.STATES.key + "30",
                rii_owned_lesson.payload(rii_owned_lesson.STATES, owner, actor),
            )
            db.execute(
                "INSERT INTO combat_fights(id,status,fight_kind) OVERRIDING SYSTEM VALUE VALUES(777,'finished','pve')"
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(777,%s,%s,0)",
                (owner, account),
            )
            result = rii_owned_lesson.settle_participants(
                db,
                self.store,
                rii_owned_lesson.STATES,
                fight,
                [member],
                [monster],
                contract_name="rii_states_lesson_contract",
            )
            self.assertIn(account, result)
            rows = db.execute(
                "SELECT achievement_id,reward_key,delivered_at FROM character_achievement_reward_outbox WHERE character_id=%s ORDER BY achievement_id",
                (owner,),
            ).fetchall()
            self.assertEqual(
                [(row["achievement_id"], row["reward_key"]) for row in rows],
                [(5143, "90001"), (5160, "90002")],
            )
            self.assertTrue(all(row["delivered_at"] is not None for row in rows))
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM account_emote_knowledge WHERE account_id=%s AND emote_id=20016",
                    (account,),
                ).fetchone()
            )
            from wakfu_server.cosmetic_store import load

            self.assertTrue(any(row[:2] == (7, 755) for row in load(db, account).items))
        with self.reopen().connection() as db:
            state = storage.load_locked(db, owner)
            self.assertTrue({5143, 5160} <= set(state["completed"]))
            self.assertTrue({10611, 10616} <= set(state["objectives"]))
            self.assertEqual(
                rii_owned_lesson.settle_participants(
                    db,
                    self.store,
                    rii_owned_lesson.STATES,
                    fight,
                    [member],
                    [monster],
                    contract_name="rii_states_lesson_contract",
                ),
                {},
            )
