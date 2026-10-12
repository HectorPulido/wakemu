"""Administrative genesis settings validate and audit isolated policy edits."""

from copy import deepcopy

from postgres_case import PostgresCase
from wakfu_server.admin_domain import AdminService


class EcologyAdminGenesisPolicyTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.admin = AdminService(self.store)

    def _audit_count(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT count(*) AS count FROM admin_panel_audit WHERE action='setting.update'"
            ).fetchone()["count"]

    def test_invalid_target_and_group_size_policies_are_rejected_without_audit(self):
        current = self.admin.setting("monster_genesis")
        audits = self._audit_count()
        invalid = (
            {"groups_per_region": 0, "min_members": 2, "max_members": 5},
            {"groups_per_region": 10, "min_members": 1, "max_members": 5},
            {"groups_per_region": 10, "min_members": 5, "max_members": 4},
            {"groups_per_region": 10, "min_members": 2, "max_members": 9},
            {"groups_per_region": True, "min_members": 2, "max_members": 5},
            {"groups_per_region": 10, "min_members": 2, "max_members": True},
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.admin.update_setting(
                    "monster_genesis",
                    {"value": value, "expected_revision": current["revision"]},
                    "ecology-genesis-policy-test",
                )
        self.assertEqual(self.admin.setting("monster_genesis"), current)
        self.assertEqual(self._audit_count(), audits)

    def test_valid_group_policy_update_is_audited_as_new_actions(self):
        current = self.admin.setting("monster_genesis")
        audits = self._audit_count()
        changed = deepcopy(current["value"])
        changed["groups_per_region"] = 9
        result = self.admin.update_setting(
            "monster_genesis",
            {"value": changed, "expected_revision": current["revision"]},
            "ecology-genesis-policy-test",
        )
        self.assertEqual(result["changed_name"], "monster_genesis")
        self.assertEqual(result["apply_mode"], "new_actions")
        self.assertEqual(self.admin.setting("monster_genesis")["value"], changed)
        self.assertEqual(self._audit_count(), audits + 1)
