"""Original missing casting geometry comes from revision-scoped SQL authority."""
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase

REVISION = "b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450"


class NativeCastingRootSupplementTests(PostgresCase):
    def setUp(self):
        super().setUp()
        from wakfu_server.native_casting_roots import _supplemental_root

        _supplemental_root.cache_clear()
        self.addCleanup(_supplemental_root.cache_clear)

    def test_original_null_collision_and_selectors_are_revision_and_spell_scoped(self):
        from wakfu_server import native_catalog
        from wakfu_server.native_casting_roots import supplemental_root

        with patch.object(
            native_catalog, "_database", return_value=self.store
        ), patch.object(native_catalog, "release", return_value=REVISION):
            for root, mask in ((401997, 1266637395197957), (402030, 140737488363540)):
                metadata = supplemental_root(root, spell_reference=8460)
                self.assertIsNone(metadata["native_casting_collision_area"])
                self.assertIs(metadata["native_selector_present"], True)
                self.assertEqual(
                    metadata["native_target_selector"], {"class": "fcE", "mask": mask}
                )
                self.assertIsNone(supplemental_root(root, spell_reference=4778))
            self.assertIsNone(supplemental_root(1, spell_reference=8460))
            with patch.object(native_catalog, "release", return_value="a" * 64):
                self.assertIsNone(supplemental_root(401997, spell_reference=8460))

    def test_primary_root_wins_and_unknown_root_remains_unknown(self):
        from wakfu_server.combat_casting_context import NativeOwnedCastingContext
        from wakfu_server.combat_conditions import UnknownCondition
        from wakfu_server import native_catalog

        current = SimpleNamespace(plan={"spell_id": 8460})
        primary = {"primary": "already-published-native-authority"}
        with patch(
            "wakfu_server.combat_casting_context.casting_root_catalog",
            return_value={"roots": {"401997": primary}},
        ), patch(
            "wakfu_server.native_casting_roots.supplemental_root",
            side_effect=AssertionError(
                "Primary metadata must not consult supplemental authority"
            ),
        ):
            self.assertIs(
                NativeOwnedCastingContext.root_record(current, 401997), primary
            )
        with patch(
            "wakfu_server.combat_casting_context.casting_root_catalog",
            return_value={"roots": {}},
        ), patch.object(
            native_catalog, "_database", return_value=self.store
        ), patch.object(
            native_catalog, "release", return_value=REVISION
        ):
            with self.assertRaisesRegex(
                UnknownCondition, "Missing native casting root"
            ):
                NativeOwnedCastingContext.root_record(current, 1)
            self.assertIsNone(
                NativeOwnedCastingContext.root_record(current, 401997)[
                    "native_casting_collision_area"
                ]
            )

    def test_database_rejects_inconsistent_null_selector_and_source_identity(self):
        import psycopg

        for statement in (
            "UPDATE native_casting_root_supplements SET source_jar_sha256='unknown' WHERE root_id=401997",
            "UPDATE native_casting_root_supplements SET metadata=jsonb_set(metadata,'{native_selector_present}','false') WHERE root_id=401997",
        ):
            with self.subTest(statement=statement), self.assertRaises(
                psycopg.errors.CheckViolation
            ):
                with self.store.connection() as database:
                    database.execute(statement)
