"""One bulk native-source contract and one representative public claim lifecycle."""
import struct
from unittest.mock import patch

from postgres_case import PostgresCase


class NativeEmoteChestActivationTests(PostgresCase):
    def test_all_fifty_five_original_bindings_and_public_claim_rollback_replay_and_reconnect(
        self,
    ):
        from wakfu_server import treasure_chests, emotes, native_catalog
        from wakfu_server.achievements import chest_open, rewards, storage
        from wakfu_server.paths import DATA_ROOT

        # The isolated schema includes migration265. No fixture adds a world
        # reward relation or fabricates an objective/achievement/item identity.
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT map_id,object_id FROM achievement_chest_bindings ORDER BY map_id,object_id"
            ).fetchall()
            self.assertEqual(len(rows), 55)
            self.assertEqual(len({(r["map_id"], r["object_id"]) for r in rows}), 55)
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT emote_id) n FROM achievement_chest_bindings"
                ).fetchone()["n"],
                52,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM native_generic_chest_script_sources"
                ).fetchone()["n"],
                107,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM achievement_chest_approaches"
                ).fetchone()["n"],
                56,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM achievement_chest_bindings WHERE native_criterion<>%s",
                    ("",),
                ).fetchone()["n"],
                5,
            )
            maps = {}
            for row in rows:
                (binding,) = chest_open._bindings(db, row["map_id"], row["object_id"])
                self.assertTrue(chest_open._direct_emote(db, binding))
                self.assertIsNone(binding["definition_id"])
                self.assertIsNone(binding["objective_id"])
                self.assertEqual(
                    (binding["native_action"], binding["native_parameter"]), (0, 0)
                )
                self.assertTrue(
                    binding["native_criterion"] == ""
                    or "IsAchievementObjectiveComplete" in binding["native_criterion"]
                )
                self.assertTrue(binding["scripts"])
                chest_open._native_source(binding)
                if row["map_id"] not in maps:
                    maps[row["map_id"]] = {
                        tuple(c)
                        for c in native_catalog.load(
                            DATA_ROOT / f"combat-maps/{row['map_id']}.json"
                        )["cells"]
                    }
                self.assertTrue(binding["approaches"])
                for cell in binding["approaches"]:
                    self.assertIn(tuple(cell), maps[row["map_id"]])
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{unlock_all}','false') WHERE name='emote_policy'"
            )

        from wakfu_server.transport_criteria import evaluate

        for expression in (
            'False and HasEmote("20007")',
            "True or UnknownChestPredicate(1)",
        ):
            with self.assertRaises(ValueError):
                evaluate(expression, {"level": 1}, now_ms=1, emote_known=lambda _: True)
        with self.assertRaisesRegex(ValueError, "authority"):
            evaluate("HasEmote(20007)", {"level": 1}, now_ms=1)

        account = self.store.register(
            "native-chest-bulk-reader", "local-test-password"
        )["id"]
        character = self.store.create_character(account, "Native Chest Learner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,x=-24,y=163,z=0,instance_id=0 WHERE id=%s",
                (character["id"],),
            )
            before = storage.load_locked(db, character["id"])
        character = self.store.character(account, character["id"])
        body = struct.pack(">qHH", 20358, 0, 0)

        def claim(store=self.store, actor=character):
            return treasure_chests.claim(
                store, account, generation, actor, body, loaded=True, is_hero=False
            )

        original = rewards._emote

        def fail_after_actual_learning(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("Failure after actual native emote learning")

        with patch.object(
            rewards, "_emote", side_effect=fail_after_actual_learning
        ), self.assertRaisesRegex(ValueError, "after actual"):
            claim()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM account_emote_knowledge WHERE account_id=%s AND emote_id=20007",
                    (account,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM character_achievement_chest_opens WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )
        result = claim()
        self.assertFalse(result["replay"])
        self.assertIn((12266, struct.pack(">iB", 20007, 1)), result["packets"])
        (visual,) = result["visual_packets"]
        self.assertEqual(
            visual,
            (
                13270,
                struct.pack(">qiBi", character["id"], 440, 1, 1)
                + struct.pack(">i", 9)
                + b"elementId"
                + struct.pack(">q", 20358),
            ),
        )
        replay = claim()
        self.assertTrue(replay["replay"])
        self.assertEqual(
            struct.unpack_from(">i", replay["visual_packets"][0][1], 8)[0], 439
        )
        self.assertNotIn(12266, [p[0] for p in replay["packets"]])
        self.assertIn(13873, [p[0] for p in replay["packets"]])
        reopened = self.reopen()
        reconnected = claim(reopened, reopened.character(account, character["id"]))
        self.assertTrue(reconnected["replay"])
        with reopened.connection() as db:
            self.assertEqual(
                emotes.authorize(db, account, struct.pack(">iq", 20007, 0)), (20007, 0)
            )
            self.assertEqual(storage.load_locked(db, character["id"]), before)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM account_emote_knowledge WHERE account_id=%s AND emote_id=20007",
                    (account,),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM inventory_items WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM character_achievement_reward_outbox WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )

        # HasEmote must agree with the effective fbs snapshot, including the
        # configured unlock view. No global policy is changed outside this
        # isolated schema and a visible emote is not falsely learned again.
        viewer = self.store.register(
            "native-chest-default-view", "local-test-password"
        )["id"]
        viewing = self.store.create_character(viewer, "Default Viewer")
        viewing_session = self.store.begin_session(viewer)
        self.store.select_character(viewer, viewing_session, viewing["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{unlock_all}','true') WHERE name='emote_policy'"
            )
            self.assertTrue(
                db.execute(
                    "SELECT unlock_default FROM native_emote_definitions WHERE emote_id=20007"
                ).fetchone()["unlock_default"]
            )
            db.execute(
                "UPDATE characters SET map_id=527,x=-24,y=163,z=0 WHERE id=%s",
                (viewing["id"],),
            )
            self.assertIn(20007, emotes.available(db, viewer))
        viewing = self.store.character(viewer, viewing["id"])
        displayed = treasure_chests.claim(
            self.store,
            viewer,
            viewing_session,
            viewing,
            body,
            loaded=True,
            is_hero=False,
        )
        self.assertNotIn(12266, [p[0] for p in displayed["packets"]])
        self.assertEqual(
            struct.unpack_from(">i", displayed["visual_packets"][0][1], 8)[0], 439
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM account_emote_knowledge WHERE account_id=%s",
                    (viewer,),
                ).fetchone()["n"],
                0,
            )
            self.assertIn(emotes.snapshot(db, viewer), displayed["packets"])
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{unlock_all}','false') WHERE name='emote_policy'"
            )

        learned_later = treasure_chests.claim(
            self.store,
            viewer,
            viewing_session,
            viewing,
            body,
            loaded=True,
            is_hero=False,
        )
        self.assertTrue(learned_later["replay"])
        self.assertIn((12266, struct.pack(">iB", 20007, 1)), learned_later["packets"])
        self.assertEqual(
            struct.unpack_from(">i", learned_later["visual_packets"][0][1], 8)[0], 440
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM account_emote_knowledge WHERE account_id=%s AND emote_id=20007",
                    (viewer,),
                ).fetchone()["n"],
                1,
            )

        # Native Safe OR truth table. These fixtures represent pre-existing
        # durable USE-objective facts; opening never adds/removes them.
        for objective_complete, known in (
            (False, False),
            (True, False),
            (False, True),
            (True, True),
        ):
            with self.subTest(objective_complete=objective_complete, known=known):
                owner = self.store.register(
                    "safe-reader-" + str(int(objective_complete)) + str(int(known)),
                    "local-test-password",
                )["id"]
                hero = self.store.create_character(
                    owner,
                    ("Safe Learner", "Safe Known", "Safe Prior", "Safe Finished")[
                        int(objective_complete) * 2 + int(known)
                    ],
                )
                session = self.store.begin_session(owner)
                self.store.select_character(owner, session, hero["id"])
                with self.store.connection() as db:
                    (rule,) = chest_open._bindings(db, 1385, 26710)
                    cell = rule["approaches"][0]
                    db.execute(
                        "UPDATE characters SET map_id=1385,x=%s,y=%s,z=%s,instance_id=0 WHERE id=%s",
                        (*cell, hero["id"]),
                    )
                    state = storage.load_locked(db, hero["id"])
                    if objective_complete:
                        state["objectives"].append(6020)
                        storage.store(db, hero["id"], state)
                    if known:
                        rewards._emote(
                            db, self.store.character(owner, hero["id"], db), 20007
                        )
                    baseline = storage.load_locked(db, hero["id"])
                hero = self.store.character(owner, hero["id"])
                request = struct.pack(">qHH", 26710, 0, 0)
                if objective_complete and known:
                    with self.assertRaisesRegex(ValueError, "original criterion"):
                        treasure_chests.claim(
                            self.store,
                            owner,
                            session,
                            hero,
                            request,
                            loaded=True,
                            is_hero=known and not objective_complete,
                        )
                else:
                    opened = treasure_chests.claim(
                        self.store,
                        owner,
                        session,
                        hero,
                        request,
                        loaded=True,
                        is_hero=known and not objective_complete,
                    )
                    self.assertEqual(
                        12266 in [packet[0] for packet in opened["packets"]], not known
                    )
                    self.assertEqual(
                        struct.unpack_from(">i", opened["visual_packets"][0][1], 8)[0],
                        2584 if known else 2585,
                    )
                with self.store.connection() as db:
                    self.assertEqual(storage.load_locked(db, hero["id"]), baseline)
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) n FROM account_emote_knowledge WHERE account_id=%s AND emote_id=20007",
                            (owner,),
                        ).fetchone()["n"],
                        1,
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) n FROM character_achievement_reward_outbox WHERE character_id=%s",
                            (hero["id"],),
                        ).fetchone()["n"],
                        0,
                    )
                    # The visual does not survive in login/reward notifications.
                    for notice in db.execute(
                        "SELECT packets FROM character_achievement_notifications WHERE character_id=%s",
                        (hero["id"],),
                    ).fetchall():
                        self.assertNotIn(
                            13270, [packet["opcode"] for packet in notice["packets"]]
                        )
