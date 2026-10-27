"""Publication identity and dynamic inputs preserve NPC activation semantics."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from wakfu_server import combat_npc_activation as activation
from wakfu_server.combat_published_catalogs import (
    POLICY,
    resolve_static_catalog_descriptor,
)


class NpcActivationProjectionTests(unittest.TestCase):
    def setUp(self):
        activation.imports_enabled.cache_clear()
        self.addCleanup(activation.imports_enabled.cache_clear)
        self.policy = {
            "schema": "native-npc-activation-v1",
            "legacy_spell_ids": [1, 2],
            "enabled_monsters": {
                "10": {"min_level": 2, "max_level": 8, "spell_ids": [3, 4]},
                "11": None,
                "12": {"min_level": True, "max_level": 8, "spell_ids": [3]},
            },
        }
        self.reads = []

    def published(self, *, revision="a" * 64, collection="activation/root"):
        records = copy.deepcopy(self.policy)
        reads = self.reads
        descriptor = dict(
            policy=POLICY,
            revision=revision,
            manifest_sha256=revision,
            collection=collection,
            count=len(records),
            ordered_keys_sha256=hashlib.sha256(
                json.dumps(list(records)).encode()
            ).hexdigest(),
        )

        class Reader:
            representation = "native_json"

            def __init__(self):
                self.descriptor = descriptor

            def __iter__(self):
                return iter(records)

            def __contains__(self, key):
                return key in records

            def record_bytes(self, key):
                if key not in records:
                    raise KeyError(key)
                reads.append(key)
                return json.dumps(records[key]).encode()

        with patch(
            "wakfu_server.native_compiled_catalog.published_collection",
            return_value=Reader(),
        ):
            return resolve_static_catalog_descriptor(descriptor)

    def check_queries(self, policy):
        self.assertTrue(activation.imports_enabled(policy, 10, 2, 3))
        self.assertTrue(activation.imports_enabled(policy, "10", 8, 4))
        for monster, level, spell in (
            (10, 1, 3),
            (10, 9, 3),
            (10, 3, 5),
            (11, 3, 3),
            (99, 3, 3),
            (10, 3, []),
        ):
            self.assertFalse(activation.imports_enabled(policy, monster, level, spell))
        with self.assertRaisesRegex(ValueError, "Invalid native NPC activation range"):
            activation.imports_enabled(policy, 12, 3, 3)

    def test_sealed_policy_is_read_once_and_matches_mutable_policy(self):
        self.check_queries(self.policy)
        published = self.published()
        self.check_queries(published)
        self.check_queries(published)
        self.assertEqual(self.reads, ["schema", "legacy_spell_ids", "enabled_monsters"])
        self.assertEqual(len(activation._RECORDS), 1)
        rules = next(iter(activation._RECORDS.values()))[0]
        with self.assertRaises(TypeError):
            rules["10"] = None
        self.assertEqual(rules["10"], (2, 8, (3, 4)))

    def test_mutable_private_input_never_reuses_a_decision(self):
        self.assertTrue(activation.imports_enabled(self.policy, 10, 3, 3))
        self.policy["enabled_monsters"]["10"]["spell_ids"].clear()
        self.assertFalse(activation.imports_enabled(self.policy, 10, 3, 3))
        self.policy["legacy_spell_ids"].append(True)
        with self.assertRaisesRegex(ValueError, "Invalid native NPC activation policy"):
            activation.imports_enabled(self.policy, 10, 3, 3)
        self.assertFalse(activation._RECORDS)

    def test_revision_and_collection_do_not_share_rules(self):
        first = self.published()
        self.assertTrue(activation.imports_enabled(first, 10, 3, 3))
        self.policy["enabled_monsters"]["10"]["spell_ids"] = [7]
        for source in (
            self.published(revision="b" * 64),
            self.published(collection="other/root"),
        ):
            self.assertFalse(activation.imports_enabled(source, 10, 3, 3))
            self.assertTrue(activation.imports_enabled(source, 10, 3, 7))
        self.assertTrue(activation.imports_enabled(first, 10, 3, 3))
        self.assertEqual(len(activation._RECORDS), 3)

    def test_zero_revision_and_oversize_are_not_retained(self):
        source = self.published(revision="0" * 64)
        self.check_queries(source)
        self.assertFalse(activation._RECORDS)
        with patch.object(activation, "_MAX_BYTES", 1):
            self.check_queries(self.published())
        self.assertFalse(activation._RECORDS)
        self.assertEqual(activation._BYTES, 0)

    def test_cache_limits_evict_and_reset_accounting(self):
        with patch.object(activation, "_MAX_ENTRIES", 2):
            for index in range(1, 5):
                self.assertTrue(
                    activation.imports_enabled(
                        self.published(revision=format(index, "064x")), 10, 3, 3
                    )
                )
                self.assertLessEqual(len(activation._RECORDS), 2)
        self.assertGreater(activation._BYTES, 0)
        activation.imports_enabled.cache_clear()
        self.assertEqual(activation._BYTES, 0)

    def test_strict_malformed_fields_keep_lazy_selected_errors(self):
        self.assertTrue(activation.imports_enabled(None, 10, 3, 3))
        for field, value in (
            ("min_level", True),
            ("max_level", False),
            ("min_level", 0),
            ("max_level", 1),
            ("spell_ids", [True]),
            ("spell_ids", (3,)),
        ):
            self.policy["enabled_monsters"]["10"] = {
                "min_level": 2,
                "max_level": 8,
                "spell_ids": [3],
            }
            self.policy["enabled_monsters"]["10"][field] = value
            sources = [self.policy]
            if not isinstance(value, tuple):
                sources.append(
                    self.published(
                        revision=hashlib.sha256(
                            repr((field, value)).encode()
                        ).hexdigest()
                    )
                )
            for source in sources:
                self.assertFalse(activation.imports_enabled(source, 99, 3, 3))
                with self.assertRaisesRegex(
                    ValueError, "Invalid native NPC activation range"
                ):
                    activation.imports_enabled(source, 10, 3, 3)
        for field, value in (
            ("schema", "unknown"),
            ("legacy_spell_ids", [True]),
            ("legacy_spell_ids", (1,)),
            ("enabled_monsters", []),
        ):
            policy = copy.deepcopy(self.policy)
            policy[field] = value
            with self.assertRaisesRegex(
                ValueError, "Invalid native NPC activation policy"
            ):
                activation.imports_enabled(policy, 99, 3, 3)
