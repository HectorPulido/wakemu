"""Five genuine company characters share one durable entry and selected wakeup.

This isolated PostgreSQL component covers admission, position buffering and
pending transport; it does not claim native map hydration, Ready or combat.
"""
import struct

from postgres_case import PostgresCase
from wakfu_server import heroes, player_parties, rift_transition_delivery as delivery
from wakfu_server.position_buffer import Positions
from wakfu_server.player_action_feedback import failure_message
from wakfu_server.rift_entry_feedback import RiftEntryError


class RiftFiveMemberEntryPostgresTests(PostgresCase):
    def test_named_refusals_leave_all_five_outside_then_entry_moves_complete_company(
        self,
    ):
        owners = []
        names = ("RiftLeader", "ELLECHERO", "RiftThird")
        for index, name in enumerate(names):
            account = self.store.register(f"rift-five-{index}", "test-password")["id"]
            main = self.store.create_character(account, name)["id"]
            generation = self.store.begin_session(account, ttl=10000)
            self.store.select_character(account, generation, main)
            owners.append((account, generation, main))
        leader = owners[0]
        hero_ids = []
        for name in ("AniSebasFixture", "OsaSebasFixture"):
            hero = self.store.create_character(leader[0], name)["id"]
            heroes.add(self.store, *leader, hero)
            hero_ids.append(hero)
        for owner in owners[1:]:
            token = player_parties.invite(self.store, *leader, owner[2])
            player_parties.answer(self.store, *owner, token, True)
        ids = [owner[2] for owner in owners] + hero_ids
        with self.store.connection() as db:
            catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]["3"]
            source = catalog["entrances"][0]
            db.execute(
                "UPDATE characters SET level=33,map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                (source["map_id"], source["x"], source["y"], source["z"], ids),
            )
        positions = Positions(self.store, lease_active=lambda *key: key in owners)
        for account, generation, main in owners:
            positions.attach(account, generation, self.store.character(account, main))
        body = struct.pack(">qHH", source["object_id"], 11, 0)
        destination = dict(map_id=catalog["map_id"], x=0, y=1, z=0)

        def nearby(actor, portal):
            return (
                actor["map_id"] == portal["map_id"]
                and max(abs(actor["x"] - portal["x"]), abs(actor["y"] - portal["y"]))
                <= 3
                and abs(actor["z"] - portal["z"]) <= 2
            )

        def enter(owner):
            return delivery.enter(
                self.store,
                positions,
                *owner,
                source["map_id"],
                body,
                source_allowed=nearby,
                resolve_destination=lambda *_: destination,
                seed="five-member-entry",
            )

        def no_entry():
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM rift_instances").fetchone()[
                        "n"
                    ],
                    0,
                )
                saved = db.execute(
                    "SELECT id,map_id,instance_id FROM characters WHERE id=ANY(%s)",
                    (ids,),
                ).fetchall()
            self.assertEqual({row["id"] for row in saved}, set(ids))
            self.assertTrue(
                all(
                    row["map_id"] == source["map_id"] and row["instance_id"] == 0
                    for row in saved
                )
            )
            self.assertEqual(set(positions.entries), set(owners))
            self.assertTrue(all(delivery.pending(*owner) is None for owner in owners))

        far = owners[1]
        current = self.store.character(far[0], far[2])
        moved = positions.move(
            *far,
            current,
            {
                **{axis: current[axis] for axis in ("x", "y", "z")},
                "x": current["x"] + 4,
            },
        )
        with self.assertRaises(RiftEntryError) as refused:
            enter(leader)
        self.assertEqual(refused.exception.reason, "proximity")
        self.assertIn("ELLECHERO", failure_message("rift_entry", refused.exception))
        no_entry()
        positions.move(*far, moved, {axis: current[axis] for axis in ("x", "y", "z")})
        with self.assertRaises(RiftEntryError) as refused:
            enter(far)
        self.assertEqual(refused.exception.reason, "leader")
        no_entry()
        result = enter(leader)
        expected = dict(destination, instance_id=result["run"]["instance_id"])
        self.assertEqual(set(result["run"]["members"]), set(ids))
        self.assertEqual({row["id"] for row in result["members"]}, set(ids))
        self.assertFalse(positions.entries)
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT id,map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s)",
                (ids,),
            ).fetchall()
            self.assertTrue(
                all({key: row[key] for key in expected} == expected for row in saved)
            )
            roster = heroes.load_roster(db, self.store, leader[0], leader[2])
            self.assertEqual({hero["id"] for hero in roster["heroes"]}, set(hero_ids))
        for owner in owners:
            self.assertEqual(delivery.pending(*owner), expected)
            self.addCleanup(delivery.acknowledge, *owner, expected)
        for hero in hero_ids:
            self.assertIsNone(delivery.pending(leader[0], leader[1], hero))


class RiftTwoOwnerBufferedProximityTests(PostgresCase):
    def test_native_adjacent_two_owner_five_company_flushes_stale_positions_after_leadership_transfer(
        self,
    ):
        """All five are native-adjacent despite distant SQL and hero baselines."""
        import ast
        from pathlib import Path
        from wakfu_server import rift_transition_delivery, rift_entry_adapter

        tree = ast.parse(
            Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("local_game_server.py")
            .read_text()
        )
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "rift_transition_delivery.enter"
        ]
        self.assertEqual(len(calls), 1)
        approach = next(
            keyword.value
            for keyword in calls[0].keywords
            if keyword.arg == "source_allowed"
        )
        production_approach = eval(
            compile(ast.Expression(approach), "<rift-native-dispatch>", "eval")
        )
        owners = []
        all_ids = []
        for index, count in enumerate((2, 1)):
            account = self.store.register(
                f"rift-buffer-owner-{index}", "test-password"
            )["id"]
            main = self.store.create_character(account, f"RiftOwner{chr(65 + index)}")[
                "id"
            ]
            generation = self.store.begin_session(account, ttl=10000)
            self.store.select_character(account, generation, main)
            owner = (account, generation, main)
            owners.append(owner)
            all_ids.append(main)
        token = player_parties.invite(self.store, *owners[0], owners[1][2])
        party_id = player_parties.answer(self.store, *owners[1], token, True)
        for index, (owner, count) in enumerate(zip(owners, (2, 1))):
            for hero_index in range(count):
                hero = self.store.create_character(
                    owner[0], f"RiftHero{chr(65 + index)}{chr(65 + hero_index)}"
                )["id"]
                heroes.add(self.store, *owner, hero)
                all_ids.append(hero)
        with self.store.connection() as db:
            catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]["3"]
            source = catalog["entrances"][0]
            # Exported installed bCy33010/bEG mask49 orientation3, native VA floors.
            self.assertEqual(
                (
                    source["map_id"],
                    source["object_id"],
                    source["x"],
                    source["y"],
                    source["z"],
                ),
                (527, 33010, -192, -30, 0),
            )
            db.execute(
                "UPDATE characters SET level=33,map_id=527,instance_id=0,x=-182,y=-29,z=0 WHERE id=ANY(%s)",
                (all_ids,),
            )
        transferred = player_parties.change_member(
            self.store, *owners[0], party_id, owners[1][2], transfer=True
        )
        self.assertEqual(transferred["party_id"], party_id)
        old_selected = owners[1][2]
        with self.store.connection() as db:
            next_selected = db.execute(
                "SELECT character_id FROM account_hero_slots WHERE account_id=%s ORDER BY slot LIMIT 1",
                (owners[1][0],),
            ).fetchone()["character_id"]
        heroes.switch_main(self.store, *owners[1], next_selected)
        owners[1] = (owners[1][0], owners[1][1], next_selected)
        with self.store.connection() as db:
            heads = db.execute(
                "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY character_id",
                (party_id,),
            ).fetchall()
            self.assertNotIn(old_selected, [row["character_id"] for row in heads])
            self.assertIn(next_selected, [row["character_id"] for row in heads])
            self.assertEqual(
                db.execute(
                    "SELECT leader_id FROM player_parties WHERE id=%s", (party_id,)
                ).fetchone()["leader_id"],
                next_selected,
            )
        positions = Positions(self.store, lease_active=lambda *key: key in owners)
        current = []
        for index, owner in enumerate(owners):
            baseline = self.store.character(owner[0], owner[2])
            positions.attach(owner[0], owner[1], baseline)
            current.append(
                positions.move(*owner, baseline, dict(x=-192 + index, y=-29, z=0))
            )
        # The selected characters are beside the portal in the real authority;
        # neither SQL nor the three inactive heroes has checkpointed that move.
        with self.store.connection() as db:
            self.assertTrue(
                all(
                    row["x"] == -182
                    for row in db.execute(
                        "SELECT x FROM characters WHERE id=ANY(%s)", (all_ids,)
                    ).fetchall()
                )
            )
        for row in current:
            self.assertTrue(production_approach(row, source))
        body = struct.pack(">qHH", source["object_id"], 11, 0)
        # A direct stale SQL read refuses; normal production entry must fence
        # and flush both owners before consulting the identical admission rule.
        with self.assertRaises(RiftEntryError) as stale:
            rift_entry_adapter.enter(
                self.store,
                *owners[1],
                527,
                body,
                source_allowed=production_approach,
                resolve_destination=lambda *_: dict(
                    map_id=catalog["map_id"], x=0, y=1, z=0
                ),
            )
        self.assertEqual(stale.exception.reason, "proximity")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM rift_instances").fetchone()["n"],
                0,
            )
        result = rift_transition_delivery.enter(
            self.store,
            positions,
            *owners[1],
            527,
            body,
            source_allowed=production_approach,
            resolve_destination=lambda *_: dict(
                map_id=catalog["map_id"], x=0, y=1, z=0
            ),
            seed="native-adjacent-buffered-company",
        )
        self.assertEqual(set(result["run"]["members"]), set(all_ids))
        self.assertEqual(len(result["members"]), 5)
        self.assertEqual(positions.entries, {})
        destination = result["destination"]
        with self.store.connection() as db:
            stored = db.execute(
                "SELECT id,map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s)",
                (all_ids,),
            ).fetchall()
            self.assertEqual({row["id"] for row in stored}, set(all_ids))
            self.assertTrue(
                all(
                    {key: row[key] for key in destination} == destination
                    for row in stored
                )
            )
            self.assertEqual(
                db.execute(
                    "SELECT leader_id FROM player_parties WHERE id=%s", (party_id,)
                ).fetchone()["leader_id"],
                owners[1][2],
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM account_hero_slots").fetchone()[
                    "n"
                ],
                3,
            )
        for owner in owners:
            self.assertEqual(rift_transition_delivery.pending(*owner), destination)
            self.addCleanup(rift_transition_delivery.acknowledge, *owner, destination)
        for member in result["members"]:
            if member.get("hero_main_id") is not None:
                self.assertIsNone(
                    rift_transition_delivery.pending(
                        member["account_id"], member["generation"], member["id"]
                    )
                )


class RiftMissingPeerSessionFeedbackTests(PostgresCase):
    def test_missing_expired_or_different_selected_peer_is_named_without_partial_entry(
        self,
    ):
        from wakfu_server import rift_entry_adapter

        owners = []
        for index, name in enumerate(("RiftCaller", "RiftPeer")):
            account = self.store.register(
                f"rift-session-feedback-{index}", "test-password"
            )["id"]
            main = self.store.create_character(account, name)["id"]
            generation = self.store.begin_session(account, ttl=10000)
            self.store.select_character(account, generation, main)
            owners.append((account, generation, main))
        caller, peer = owners
        alternate = self.store.create_character(peer[0], "RiftOther")["id"]
        token = player_parties.invite(self.store, *caller, peer[2])
        party_id = player_parties.answer(self.store, *peer, token, True)
        ids = [owner[2] for owner in owners]
        with self.store.connection() as db:
            catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]["3"]
            source = catalog["entrances"][0]
            db.execute(
                "UPDATE characters SET level=33,map_id=527,instance_id=0,x=-193,y=-29,z=0 WHERE id=ANY(%s)",
                (ids,),
            )
            saved_session = db.execute(
                "SELECT * FROM sessions WHERE account_id=%s", (peer[0],)
            ).fetchone()
        positions = Positions(self.store, lease_active=lambda *key: key in owners)
        for owner in owners:
            positions.attach(
                owner[0], owner[1], self.store.character(owner[0], owner[2])
            )
        body = struct.pack(">qHH", source["object_id"], 11, 0)
        destination = dict(map_id=catalog["map_id"], x=0, y=1, z=0)

        def enter(owner=caller):
            return delivery.enter(
                self.store,
                positions,
                *owner,
                527,
                body,
                source_allowed=lambda actor, portal: (
                    actor["x"],
                    actor["y"],
                    actor["z"],
                )
                == (-193, -29, 0),
                resolve_destination=lambda *_: destination,
                seed="missing-peer-session-feedback",
            )

        def restore_peer():
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO sessions(account_id,generation,expires_at,character_id) VALUES(%s,%s,%s,%s) "
                    "ON CONFLICT(account_id) DO UPDATE SET generation=EXCLUDED.generation,expires_at=EXCLUDED.expires_at,character_id=EXCLUDED.character_id",
                    tuple(
                        saved_session[key]
                        for key in (
                            "account_id",
                            "generation",
                            "expires_at",
                            "character_id",
                        )
                    ),
                )

        def unchanged():
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM rift_instances").fetchone()[
                        "n"
                    ],
                    0,
                )
                self.assertEqual(
                    [
                        row["character_id"]
                        for row in db.execute(
                            "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY character_id",
                            (party_id,),
                        ).fetchall()
                    ],
                    sorted(ids),
                )
                rows = db.execute(
                    "SELECT map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s)",
                    (ids,),
                ).fetchall()
            self.assertTrue(
                all(
                    tuple(row[key] for key in ("map_id", "instance_id", "x", "y", "z"))
                    == (527, 0, -193, -29, 0)
                    for row in rows
                )
            )
            self.assertEqual(set(positions.entries), set(owners))
            self.assertTrue(all(delivery.pending(*owner) is None for owner in owners))

        for condition in ("missing", "expired", "different_selected"):
            with self.subTest(condition=condition):
                restore_peer()
                with self.store.connection() as db:
                    if condition == "missing":
                        db.execute(
                            "DELETE FROM sessions WHERE account_id=%s", (peer[0],)
                        )
                    elif condition == "expired":
                        db.execute(
                            "UPDATE sessions SET expires_at=%s WHERE account_id=%s",
                            (self.store.now(-1), peer[0]),
                        )
                    else:
                        db.execute(
                            "UPDATE sessions SET character_id=%s WHERE account_id=%s",
                            (alternate, peer[0]),
                        )
                with self.assertRaises(RiftEntryError) as refused:
                    enter()
                self.assertEqual(refused.exception.reason, "session")
                message = failure_message("rift_entry", refused.exception)
                self.assertIn("RiftPeer", message)
                self.assertIn("sesión activa", message)
                self.assertNotIn("lejos", message)
                unchanged()
        restore_peer()
        with self.assertRaisesRegex(
            ValueError, "Invalid rift character session"
        ) as invalid:
            enter((caller[0], "superseded-generation", caller[2]))
        self.assertNotIsInstance(invalid.exception, RiftEntryError)
        unchanged()
        result = enter()
        self.assertEqual(set(result["run"]["members"]), set(ids))
        self.assertEqual(set(positions.entries), set())
        expected = dict(destination, instance_id=result["run"]["instance_id"])
        for owner in owners:
            self.assertEqual(delivery.pending(*owner), expected)
            self.addCleanup(delivery.acknowledge, *owner, expected)
