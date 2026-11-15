"""Extracted World providers and receipts preserve their strict source boundary."""

from hashlib import sha256
from source_view import WorldSourcePath as Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType
import unittest
from unittest.mock import patch

from wakfu_server.application.source_identity import dispatcher_source_sha256
from wakfu_server.combat_live_reproduction import (
    LiveReplayContext,
    LiveProviderReplayError,
)
from wakfu_server import catalog_gc_bootstrap


class DispatcherSourceIdentityTests(unittest.TestCase):
    def test_legacy_tree_keeps_single_file_identity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = b"def session():\n    pass\n"
            (root / "local_game_server.py").write_bytes(source)
            self.assertEqual(dispatcher_source_sha256(root), sha256(source).hexdigest())

    def test_application_edits_additions_and_removal_change_identity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            hub = root / "local_game_server.py"
            hub.write_text("from wakfu_server.application.bootstrap import main\n")
            application = root / "wakfu_server/application"
            application.mkdir(parents=True)
            session = application / "session.py"
            session.write_text("phase = 'selected'\n")
            original = dispatcher_source_sha256(root)
            session.write_text("phase = 'loaded'\n")
            changed = dispatcher_source_sha256(root)
            self.assertNotEqual(original, changed)
            session.write_text("phase = 'selected'\n")
            self.assertEqual(original, dispatcher_source_sha256(root))
            other = application / "inventory.py"
            other.write_text("enabled = True\n")
            self.assertNotEqual(original, dispatcher_source_sha256(root))
            other.unlink()
            self.assertEqual(original, dispatcher_source_sha256(root))
            session.rename(application / "renamed.py")
            self.assertNotEqual(original, dispatcher_source_sha256(root))
            hub.write_text("raise RuntimeError('changed hub')\n")
            self.assertNotEqual(original, dispatcher_source_sha256(root))

    def test_bytecode_and_private_outputs_do_not_change_source_identity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "local_game_server.py").write_text("pass\n")
            application = root / "wakfu_server/application"
            application.mkdir(parents=True)
            (application / "session.py").write_text("pass\n")
            original = dispatcher_source_sha256(root)
            (application / "private.json").write_text("{}")
            (application / "session.pyc").write_bytes(b"irrelevant")
            self.assertEqual(original, dispatcher_source_sha256(root))


class ExtractedProviderIdentityTests(unittest.TestCase):
    module = "wakfu_server.application.session_combat"

    def validate(self, identities):
        context = object.__new__(LiveReplayContext)
        context.identities = identities
        context._validate_providers()

    def test_exact_application_providers_and_legacy_receipts_are_qualified(self):
        names = {
            "stats_serializer": "current_combat_stats",
            "runtime_stats_serializer": "current_combat_stats",
            "turn_start_provider": "area_boundary_provider",
            "turn_end_provider": "apply_readiness.<locals>.<lambda>",
            "expiration_runtime_factory": "apply_readiness.<locals>.<lambda>",
        }
        for field, name in names.items():
            with self.subTest(field=field):
                self.validate(
                    {
                        field: dict(
                            module=self.module, qualname="CombatSessionMixin." + name
                        )
                    }
                )
                self.validate(
                    {
                        field: dict(
                            module="local_game_server",
                            qualname="session.<locals>." + name,
                        )
                    }
                )

    def test_provider_names_cannot_be_reused_from_another_module_or_field(self):
        for module, name in (
            (self.module + "_other", "CombatSessionMixin.current_combat_stats"),
            (self.module, "OtherMixin.current_combat_stats"),
            (self.module, "CombatSessionMixin.area_boundary_provider"),
            (self.module, "CombatSessionMixin.current_combat_stats.<locals>.<lambda>"),
        ):
            with self.subTest(module=module, name=name), self.assertRaises(
                LiveProviderReplayError
            ):
                self.validate({"stats_serializer": dict(module=module, qualname=name)})

    def test_imported_application_bootstrap_rejects_heap_freeze(self):
        name = "wakfu_server.application.bootstrap"
        with patch.dict(sys.modules, {name: ModuleType(name)}):
            with self.assertRaisesRegex(RuntimeError, "World was imported"):
                catalog_gc_bootstrap._assert_startup()
