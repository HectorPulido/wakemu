"""Synthetic isolated binding tests; no live chest or original quest activation."""
from pathlib import Path
import json
import struct
import unittest
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import catalog, engine, rewards, storage

STAGE = Path(__file__).resolve().parents[2]
SOURCE = dict(
    payload="02000000000b010000000d00000104b7ffffff8bffffffe3000000010101010001000000033335330000007bc60101",
    state="01020000000602000101010001010000000000",
    geometry="c9d3ff205de8473a28184ce63a36c545c9ed9c0a8ccf4df3e3e9642e252a3a7d",
)


def rule_document(*, gate=""):
    return dict(
        schema_version=1,
        policy="reviewed_local_native_identity_v1",
        variable_bindings=[],
        definitions=[
            dict(
                definition_id=1853,
                objectives=[dict(objective_id=3857, chest_binding_id=1)],
                event_policy="authenticated_native_chest_open_v1",
                prerequisites=[],
                authority="proposed_explicit_local_policy_not_activated",
                source_criteria={"aHe": gate, "cjI": ""},
                native_repeatable=False,
                native_period=0,
                mission_dependency=bool(gate),
                rewards=[
                    dict(d=3249, aeV=6, ckk=False, ckl=[1350000]),
                    dict(d=3270, aeV=11, ckk=True, ckl=[15000]),
                ],
            )
        ],
    )


class ChestSelectorTests(unittest.TestCase):
    def test_only_qualified_binding_and_eligible_definition_select_objective(self):
        rule = catalog.validate(rule_document())
        before = dict(
            variables={},
            objectives=[],
            completed=[],
            running=[],
            tracking=[],
            recent=[],
            completion_dates={},
        )
        for event in (
            {},
            dict(kind="chest_open", binding_id=1),
            dict(
                kind="authenticated_native_chest_open_v1",
                binding_id=2,
                objective_id=3857,
                eligible_definition_ids=[1853],
            ),
        ):
            after, grants, _, _ = engine.advance(before, event, rule, now_ms=1)
            self.assertEqual(after["objectives"], [])
            self.assertEqual(grants, [])
        event = dict(
            kind="authenticated_native_chest_open_v1",
            binding_id=1,
            objective_id=3857,
            eligible_definition_ids=[1853],
        )
        after, grants, objectives, completed = engine.advance(
            before, event, rule, now_ms=1
        )
        self.assertEqual((objectives, completed, len(grants)), ([3857], [1853], 2))
        self.assertEqual(engine.advance(after, event, rule, now_ms=2)[1], [])
        already_latched = dict(before, objectives=[3857])
        self.assertEqual(
            engine.advance(already_latched, {"original_breeds": [39]}, rule, now_ms=2)[
                1
            ],
            [],
        )
        mixed = rule_document()
        mixed["definitions"][0]["objectives"].append(
            dict(objective_id=3858, breed_id=39, required_kills=1)
        )
        with self.assertRaises(ValueError):
            catalog.validate(mixed)
        for malformed in (
            dict(aeV=11, d=1, ckk=1, ckl=[15]),
            dict(aeV=11, d=True, ckk=True, ckl=[15]),
            dict(aeV=11, d=1, ckk=True, ckl=[True]),
        ):
            with self.assertRaises(ValueError):
                rewards.validate(malformed)


class ChestRewardTransactionTests(PostgresCase):
    def setUp(self):
        super().setUp()
        with self.store.connection() as db:
            if (
                db.execute(
                    "SELECT to_regclass('achievement_chest_bindings') AS name"
                ).fetchone()["name"]
                is None
            ):
                db.execute((STAGE / "schema.sql").read_text())
            # Synthetic reward relation on a positively attested original
            # Gemlockitup object. This is not its original reward/period claim.
            db.execute(
                "INSERT INTO treasure_chest_rules VALUES "
                "(1207,31733,'unit.synthetic-chest-custom',-117,-29,0,353,'not IsHero()',22,"
                "'CHALLENGE_ACTIVATE',0,NULL,0,0,0,%s,%s,%s,"
                "'wakemu.same-floor-cardinal-native-surface.v1','unit-original-positive-object',"
                "'wakemu.once-per-account.v1','unit-synthetic-custom-reward')",
                (SOURCE["payload"], SOURCE["state"], SOURCE["geometry"]),
            )
            db.execute(
                "INSERT INTO treasure_chest_approaches VALUES(1207,31733,-116,-29,0)"
            )
            db.execute("INSERT INTO treasure_chest_rewards VALUES(1207,31733,0,1752,5)")

    def owner(self, suffix, *, account=None):
        if account is None:
            account = self.store.register(
                "staged-chest-" + suffix, "local-test-password"
            )["id"]
        character = self.store.create_character(account, "Chest " + suffix)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1207,instance_id=0,x=-116,y=-29,z=0 WHERE id=%s",
                (character["id"],),
            )
        return account, generation, self.store.character(account, character["id"])

    def configure(self, *, gate=""):
        from wakfu_server import treasure_chests

        original = treasure_chests.definition(self.store, 1207, 31733)
        with self.store.connection() as db:
            # The production selector requires a separately attested original
            # object. Keep the synthetic binding fixture connected to that
            # positive identity even when this isolated schema omitted the seed.
            db.execute(
                "INSERT INTO achievement_chest_source_attestations "
                "(map_id,object_id,native_definition,original_name_en,object_kind,"
                "object_family,native_action,native_parameter,native_payload_hex,"
                "catalog_revision,source_sha256,native_direction,native_approach_mask,"
                "native_center_blocked,native_physical_sha256) VALUES "
                "(1207,31733,353,'Gemlockitup','gemlock','LootChest',22,0,%s,%s,%s,"
                "0,0,FALSE,%s) ON CONFLICT(map_id,object_id,native_definition) DO NOTHING",
                (
                    original["native_payload_hex"],
                    "b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450",
                    "ef6d7a2986f5c69c57a928c6854ecf8a7775ad20b539af63e4d989216ee63553",
                    "b" * 64,
                ),
            )
            db.execute(
                "INSERT INTO achievement_chest_bindings "
                "(binding_id,map_id,object_id,definition_id,objective_id,native_definition,native_action,"
                "native_criterion,activation_criterion,completion_criterion,artifact_reference,x,y,z,"
                "native_payload_hex,native_state_payload_hex,native_geometry_sha256,source_sha256,binding_authority) VALUES "
                "(1,1207,31733,1853,3857,353,22,'not IsHero()',%s,'',NULL,-117,-29,0,%s,%s,%s,%s,"
                "'reviewed_reconstructed_chest_objective_v1')",
                (
                    gate,
                    original["native_payload_hex"],
                    original["native_state_payload_hex"],
                    original["native_geometry_sha256"],
                    "a" * 64,
                ),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM achievement_chest_bindings b "
                    "JOIN achievement_chest_source_attestations s "
                    "USING(map_id,object_id,native_definition) "
                    "WHERE b.map_id=1207 AND b.object_id=31733"
                ).fetchone()["n"],
                1,
            )
            db.execute("INSERT INTO achievement_chest_approaches VALUES(1,-116,-29,0)")
            db.execute(
                "UPDATE settings SET value=%s WHERE name='achievement_qualified_rules'",
                (Jsonb(rule_document(gate=gate)),),
            )

    def claim(self, account, generation, character, **extra):
        from wakfu_server import treasure_chests

        return treasure_chests.claim(
            self.store,
            account,
            generation,
            character,
            struct.pack(">qHH", 31733, 22, 0),
            loaded=True,
            is_hero=False,
            **extra
        )

    def snapshot(self, account, character_id):
        with self.store.connection() as db:
            return dict(
                wallet=db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
                ).fetchone()["kamas"],
                xp=db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (character_id,),
                ).fetchone()["xp"],
                opens=db.execute(
                    "SELECT count(*) n FROM character_achievement_chest_opens WHERE character_id=%s",
                    (character_id,),
                ).fetchone()["n"],
                rewards=db.execute(
                    "SELECT count(*) n FROM character_achievement_reward_outbox WHERE character_id=%s",
                    (character_id,),
                ).fetchone()["n"],
                claims=db.execute(
                    "SELECT count(*) n FROM account_achievement_reward_claims WHERE account_id=%s",
                    (account,),
                ).fetchone()["n"],
            )

    def test_two_characters_get_xp_but_one_account_currency_despite_custom_prior_claim_and_reconnect(
        self,
    ):
        from wakfu_server import treasure_chests

        account, generation, first = self.owner("First")
        # Existing once-account custom inventory reward is already consumed.
        self.claim(account, generation, first)
        self.configure()
        initial = self.snapshot(account, first["id"])
        result = self.claim(
            account, generation, self.store.character(account, first["id"])
        )
        self.assertTrue(result["replay"])  # Custom replay did not skip native XP.
        actual = self.snapshot(account, first["id"])
        self.assertEqual(
            (
                actual["wallet"] - initial["wallet"],
                actual["xp"] - initial["xp"],
                actual["claims"],
            ),
            (15000, 1350000, 1),
        )
        self.assertEqual((actual["opens"], actual["rewards"]), (1, 2))
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, first["id"])
        self.claim(account, generation, self.store.character(account, first["id"]))
        self.assertEqual(actual, self.snapshot(account, first["id"]))
        _, second_generation, second = self.owner("Second", account=account)
        second_initial = self.snapshot(account, second["id"])
        with self.assertRaises(ValueError):
            self.claim(account, generation, second)
        self.claim(account, second_generation, second)
        second_after = self.snapshot(account, second["id"])
        self.assertEqual(second_after["xp"] - second_initial["xp"], 1350000)
        self.assertEqual(second_after["wallet"], actual["wallet"])
        self.assertEqual(second_after["claims"], 1)
        self.assertEqual(second_after["opens"], 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND delivered_at IS NULL",
                    (second["id"],),
                ).fetchone()["n"],
                0,
            )

    def test_all_projected_artifacts_pass_real_open_and_current_policy_still_fences(
        self,
    ):
        from wakfu_server.achievements import chest_open
        from wakfu_server.exploration_secrets import ITEM_REFS, SETTING

        account, generation, character = self.owner("Artifacts")
        self.configure()
        initial = self.snapshot(account, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (Jsonb(dict(version=1, unlock_all=True)), SETTING),
            )
            for reference in ITEM_REFS:
                with self.subTest(reference=reference), db.transaction(
                    force_rollback=True
                ):
                    db.execute(
                        "UPDATE achievement_chest_bindings SET artifact_reference=%s WHERE binding_id=1",
                        (reference,),
                    )
                    result = chest_open.claim(
                        db,
                        self.store,
                        account,
                        generation,
                        character,
                        struct.pack(">qHH", 31733, 22, 0),
                        loaded=True,
                        is_hero=False,
                    )
                    self.assertIsNotNone(result)
                    receipt = db.execute(
                        "SELECT event_payload FROM character_achievement_chest_opens "
                        "WHERE character_id=%s AND binding_id=1",
                        (character["id"],),
                    ).fetchone()
                    self.assertEqual(receipt["event_payload"]["artifacts"], [reference])
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) n FROM account_quest_items "
                            "WHERE account_id=%s AND reference=ANY(%s)",
                            (account, list(ITEM_REFS)),
                        ).fetchone()["n"],
                        0,
                    )
            stale = self.store.character(account, character["id"], db)
            self.assertEqual(
                stale["exploration_secrets"]["account_item_refs"], ITEM_REFS
            )
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (Jsonb(dict(version=1, unlock_all=False)), SETTING),
            )
            db.execute(
                "UPDATE achievement_chest_bindings SET artifact_reference=%s WHERE binding_id=1",
                (ITEM_REFS[0],),
            )
        with self.store.connection() as db:
            with self.assertRaisesRegex(ValueError, "owned artifact"):
                chest_open.claim(
                    db,
                    self.store,
                    account,
                    generation,
                    stale,
                    struct.pack(">qHH", 31733, 22, 0),
                    loaded=True,
                    is_hero=False,
                )
        self.assertEqual(initial, self.snapshot(account, character["id"]))

    def test_gate_and_authenticated_facts_fail_closed_and_mutation_failure_rolls_back_whole_open(
        self,
    ):
        from wakfu_server import harvest_inventory

        account, generation, character = self.owner("Rollback")
        self.configure(gate="GetRealLevel() >= 25 and IsAchievementComplete(2192)")
        initial = self.snapshot(account, character["id"])
        with self.assertRaisesRegex(ValueError, "eligibility"):
            self.claim(account, generation, character)
        self.assertEqual(initial, self.snapshot(account, character["id"]))
        # A PG fixture supplies prior journal authority to test the gate's
        # positive branch; it is not an earned allegiance/quest claim.
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=25 WHERE id=%s", (character["id"],))
            state = storage.load_locked(db, character["id"])
            state["completed"] = [2192]
            storage.store(db, character["id"], state)
        character = self.store.character(account, character["id"])
        for changed in (
            dict(character, x=500),
            dict(character, map_id=528),
            dict(character, instance_id=7),
        ):
            with self.assertRaises(ValueError):
                self.claim(account, generation, changed)
        with self.store.connection() as db:
            db.execute(
                "UPDATE achievement_chest_bindings SET artifact_reference=29431 WHERE binding_id=1"
            )
        with self.assertRaisesRegex(ValueError, "artifact"):
            self.claim(account, generation, character)
        with self.store.connection() as db:
            db.execute(
                "UPDATE achievement_chest_bindings SET artifact_reference=NULL WHERE binding_id=1"
            )
        original = harvest_inventory.grant

        def mutate_then_fail(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("Failure after custom mutation")

        with patch.object(
            harvest_inventory, "grant", side_effect=mutate_then_fail
        ), self.assertRaisesRegex(ValueError, "custom mutation"):
            self.claim(account, generation, character)
        self.assertEqual(initial, self.snapshot(account, character["id"]))
        self.claim(account, generation, character)
        committed = self.snapshot(account, character["id"])
        self.assertEqual((committed["opens"], committed["claims"]), (1, 1))

    def test_original_generic_emote_action_zero_learns_directly_without_fake_achievement_or_item(
        self,
    ):
        from wakfu_server import treasure_chests

        account, generation, character = self.owner("Yawn")
        payload = "02000000000b010000000d000001020fffffffe7000000a30000000101010100010000000332303000000017380101"
        geometry = "0bfbbc314349dd929561c9a93dd65fed6c3d52a78a886cbabb28515893394cb0"
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{unlock_all}','false') WHERE name='emote_policy'"
            )
            # Migration265 activates the actual original program. Reuse it
            # instead of inserting a competing fixture-only world binding.
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM achievement_chest_bindings WHERE binding_id=20358"
                ).fetchone()
            )
            db.execute(
                "UPDATE characters SET map_id=527,x=-24,y=163,z=0 WHERE id=%s",
                (character["id"],),
            )
            before = storage.load_locked(db, character["id"])
        character = self.store.character(account, character["id"])
        self.assertIsNotNone(treasure_chests.definition(self.store, 527, 20358))
        body = struct.pack(">qHH", 20358, 0, 0)
        with self.assertRaisesRegex(ValueError, "attested original action"):
            treasure_chests.claim(
                self.store,
                account,
                generation,
                character,
                struct.pack(">qHH", 20358, 22, 0),
                loaded=True,
                is_hero=False,
            )
        # A congruent but invented target still disagrees with native effect441.
        with self.store.connection() as db:
            db.execute(
                "UPDATE achievement_chest_bindings SET emote_id=20008,"
                "effect_criterion='not HasEmote(20008)' WHERE binding_id=20358"
            )
        with self.assertRaisesRegex(ValueError, "original descriptor/action/effect"):
            treasure_chests.claim(
                self.store,
                account,
                generation,
                character,
                body,
                loaded=True,
                is_hero=False,
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM character_achievement_chest_opens "
                    "WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )
            db.execute(
                "UPDATE achievement_chest_bindings SET emote_id=20007,"
                "effect_criterion='not HasEmote(20007)' WHERE binding_id=20358"
            )
        result = treasure_chests.claim(
            self.store, account, generation, character, body, loaded=True, is_hero=False
        )
        self.assertFalse(result["replay"])
        self.assertIn(12266, [p[0] for p in result["packets"]])
        replay = treasure_chests.claim(
            self.store, account, generation, character, body, loaded=True, is_hero=False
        )
        self.assertTrue(replay["replay"])
        self.assertNotIn(12266, [p[0] for p in replay["packets"]])
        self.assertIn(13873, [p[0] for p in replay["packets"]])
        with self.store.connection() as db:
            self.assertEqual(storage.load_locked(db, character["id"]), before)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM account_emote_knowledge "
                    "WHERE account_id=%s AND emote_id=20007",
                    (account,),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM inventory_items WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )
