"""Actual Store/MVCC admission and native Ready; no combat stat injection."""
from copy import deepcopy
from dataclasses import replace
import struct
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from test_equipment_null_carrier_pipeline import EquipmentNullCarrierPipelineTests
from wakfu_server.characters import nation_state
from wakfu_server.characters.guild_service import GuildService
from wakfu_server.characters.owned_social_context import (
    OwnedSocialContext,
    current,
    pin,
)
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
)
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_server.fight_checkpoint_store import snapshot


class EquipmentSocialContextPipelineTests(PostgresCase):
    _fixture = EquipmentNullCarrierPipelineTests._fixture
    _nulls = staticmethod(EquipmentNullCarrierPipelineTests._nulls)
    _assert_carrier = EquipmentNullCarrierPipelineTests._assert_carrier

    def test_actual_store_json_ai_context_and_unrelated_mvcc_write(self):
        import json
        import uuid
        from wakfu_server.combat_tactical_ai import NativeProvider, _context_json

        account = self.store.register(
            "social" + uuid.uuid4().hex[:10], "local-test-password"
        )["id"]
        char = self.store.create_character(account, "Social Source", breed=1, sex=0)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, char["id"])
        char = self.store.character(account, char["id"])
        # Normal selection materializes the native starter sheet/deck. Save
        # those exact legal blobs through the actual owned build boundary.
        starter = char["builds"][char["active_build_index"]]
        char = self.store.save_build(
            account,
            generation,
            char["id"],
            char["active_build_index"],
            {
                key: bytes.fromhex(starter[key])
                for key in ("sheet", "equipment", "deck", "aptitudes")
            },
        )
        char = self.store.character(account, char["id"])
        record = char["native_social_context"]
        self.assertIs(type(record), dict)
        receipt = OwnedSocialContext.from_record(record)
        receipt.require_owner(char["id"], account)
        encoded = json.dumps(
            char, default=_context_json, sort_keys=True, allow_nan=False
        )
        round_trip = json.loads(encoded)
        self.assertEqual(round_trip["native_social_context"], record)
        build = char["builds"][char["active_build_index"]]
        deck = bytes.fromhex(build["deck"])
        provider = NativeProvider(char, {}, deck)
        self.assertEqual(
            provider.context_key, NativeProvider(round_trip, {}, deck).context_key
        )
        # Real unrelated commit changes the global MVCC horizon, not this owned source.
        self.store.register("unrelated" + uuid.uuid4().hex[:10], "local-test-password")
        reloaded = self.store.character(account, char["id"])
        self.assertEqual(reloaded["native_social_context"], record)
        from types import SimpleNamespace

        fight = SimpleNamespace(actors={char["id"]: SimpleNamespace(controlled=True)})
        pin(fight, char)
        pin(fight, reloaded)
        self.assertEqual(current(fight, reloaded), receipt)

    def test_actual_nation_enrollment_ready_branch_and_typed_recovery(self):
        def setup(account, generation, actor):
            nation_state.enroll(
                self.store, account, generation, actor, struct.pack(">i", 30) + bytes(2)
            )

        rejected = []

        def reject_foreign_before_initialization(
            preview, action_id, char, monster, deck, rng
        ):
            from wakfu_server.combat_server_spell import prepare_server_initialization

            actual = OwnedSocialContext.from_record(char["native_social_context"])
            foreign = replace(
                actual, account_id=actual.account_id + 1, source_sha256=""
            )
            before = snapshot(preview)
            rng_before = rng.getstate()
            self.assertNotIn(
                str(char["id"]), getattr(preview, "native_owned_equipment_sources", {})
            )
            self.assertNotIn(char["id"], getattr(preview, "native_social_contexts", {}))
            with self.assertRaisesRegex(
                ValueError, "Owned social receipt actor/account mismatch"
            ):
                prepare_server_initialization(
                    dict(char, native_social_context=foreign.to_record()),
                    {-200: monster},
                    preview,
                    char["account_id"],
                    deck,
                    action_id=action_id,
                    rng=rng,
                )
            self.assertEqual(snapshot(preview), before)
            self.assertEqual(rng.getstate(), rng_before)
            rejected.append(action_id)

        values = self._fixture(
            9727,
            0,
            23,
            social_setup=setup,
            before_initialization=reject_foreign_before_initialization,
        )
        self.assertEqual(len(rejected), 1)
        char, monster, deck, rng, runtime, stats = values
        native_ids = (36720, 36721, 36722, 36723, 43060, 43061, 44747, 108826)
        self._assert_carrier(
            values, 682, 36720, tuple(x for x in native_ids if x != 36720)
        )
        receipt = current(runtime.fight, char)
        self.assertIs(type(receipt), OwnedSocialContext)
        from wakfu_server.combat_tactical_ai import NativeProvider, _source_key

        provider = NativeProvider(char, {-200: monster}, deck)
        stable_source_key = _source_key(runtime, provider)
        self.assertEqual(_source_key(runtime, provider), stable_source_key)
        self.assertEqual(
            (receipt.nation_id, receipt.guild_id, receipt.guild_level), (30, None, 0)
        )
        before = snapshot(runtime.fight)
        recovered = decode_state(encode_state(runtime.fight))
        self.assertEqual(snapshot(recovered), before)
        self.assertEqual(current(recovered, char), receipt)
        foreign = dict(char, account_id=char["account_id"] + 1)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            current(recovered, foreign)
        with self.assertRaises(ValueError):
            self.store.character(foreign["account_id"], char["id"])
        self.assertEqual(snapshot(runtime.fight), before)

    def test_actual_empty_guild_read_is_known_zero_with_ui_policy_disabled(self):
        with self.store.connection() as db:
            policy = db.execute(
                "SELECT value FROM settings WHERE name='guild_policy'"
            ).fetchone()["value"]
            policy = dict(policy, enabled=False, native_sync_enabled=False)
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(policy),),
            )
        values = self._fixture(13408, 0, 23)
        char, _, _, _, runtime, _ = values
        self._assert_carrier(values, 1282, 65862)
        self.assertNotIn("guild_native", char)
        receipt = current(runtime.fight, char)
        self.assertIsNone(receipt.guild_id)
        self.assertEqual(receipt.guild_level, 0)
        condition = ConditionContext(
            actors={
                "caster": ConditionActor(
                    actor_id=char["id"],
                    native_account_id=char["account_id"],
                    is_player=True,
                    is_native_fighter=True,
                    is_native_ehg=True,
                    native_social_context=receipt,
                )
            }
        )
        self.assertTrue(evaluate_condition("GetGuildLevel() == 0", condition))
        with self.store.connection() as db:
            after = db.execute(
                "SELECT value FROM settings WHERE name='guild_policy'"
            ).fetchone()["value"]
        self.assertIs(after["enabled"], False)
        self.assertIs(after["native_sync_enabled"], False)

    def test_legitimate_guild_creation_ready_uses_real_membership_level(self):
        def setup(account, generation, actor):
            from wakfu_server.inventory_items import grant

            policy = dict(
                enabled=True,
                native_sync_enabled=False,
                creation_kamas=10000,
                creation_item=16942,
                max_members=20,
                max_ranks=15,
                name_pattern=r"[A-Za-z][A-Za-z0-9 ]{2,30}",
                name_normalization="NFKC_CASEFOLD",
                allowed_blazons=[123],
                leader_permissions=(1 << 63) - 1,
                member_permissions=0,
                permissions={},
                invitation_seconds=3600,
                owner_id_semantics="account",
                description_max_bytes=500,
                message_max_bytes=500,
            )
            with self.store.connection() as db:
                db.execute(
                    "UPDATE settings SET value=%s WHERE name='guild_policy'",
                    (Jsonb(policy),),
                )
                # Existing isolated guild test economy funding; never changes combat stats or guild level.
                db.execute(
                    "UPDATE account_wallets SET kamas=50000 WHERE account_id=%s",
                    (account,),
                )
            char = self.store.character(account, actor)
            bag = next(row for row in char["inventory_containers"] if row["kind"] == 0)
            grant(
                self.store,
                account,
                generation,
                actor,
                reference=16942,
                quantity=1,
                container=bag["uid"],
                slot=0,
                allowed_references={16942},
            )
            created = GuildService(self.store).create(
                account,
                generation,
                actor,
                "Social Receipt Guild",
                123,
                "Leader",
                "Member",
                operation_key="social-create",
            )
            self.assertEqual(created["guild"]["level"], 1)
            self.created_guild_id = created["guild"]["id"]

        values = self._fixture(13408, 0, 23, social_setup=setup)
        char, _, _, _, runtime, _ = values
        self._assert_carrier(values, 1282, 65862)
        receipt = current(runtime.fight, char)
        self.assertEqual(
            (receipt.guild_id, receipt.guild_level), (self.created_guild_id, 1)
        )
        with self.store.connection() as db:
            actual = db.execute(
                "SELECT level FROM guilds WHERE id=%s", (self.created_guild_id,)
            ).fetchone()
        self.assertEqual(receipt.guild_level, actual["level"])
        self.assertNotIn(
            "guild_native", char
        )  # No implicit guild UI/native-sync activation.


def load_tests(loader, tests, pattern):
    """Exclude the imported null-carrier fixture from social discovery."""
    import unittest

    return unittest.TestSuite(
        EquipmentSocialContextPipelineTests(name)
        for name in (
            "test_actual_store_json_ai_context_and_unrelated_mvcc_write",
            "test_actual_nation_enrollment_ready_branch_and_typed_recovery",
            "test_actual_empty_guild_read_is_known_zero_with_ui_policy_disabled",
            "test_legitimate_guild_creation_ready_uses_real_membership_level",
        )
    )
