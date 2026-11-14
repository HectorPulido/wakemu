"""Native registration and portal isolation, without account/network requests."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QLineEdit

spec = importlib.util.spec_from_file_location("shared_launcher_ui", SOURCE / "launcher_ui.py")
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class LauncherUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.calls = []
        def dispatch(action, data):
            self.calls.append((action, data))
            return {"ok": True, "state": ui.fixture_state()}
        self.window = ui.Launcher(dispatch=dispatch, initial_state=ui.fixture_state())

    def tearDown(self):
        self.window.save_timer.stop()
        self.window.clear_portal()
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_registration_mismatch_and_cancel_do_not_submit_or_change_selected_account(self):
        self.window.username.blockSignals(True)
        self.window.username.setEditText("retained_account")
        self.window.username.blockSignals(False)
        self.window.open_registration()
        dialog = self.window.registration
        dialog.username.setText("new_account")
        dialog.password.setText("fixture-password")
        dialog.confirm.setText("different-password")
        dialog.submit()
        self.assertEqual(dialog.status.text(), "Passwords do not match.")
        self.assertFalse(dialog.submitting)
        self.assertEqual(dialog.password.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(dialog.confirm.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(self.calls, [])
        dialog.reject()
        self.assertEqual(self.window.username.currentText(), "retained_account")
        self.window.open_registration()
        self.assertEqual(self.window.registration.username.text(), "")
        self.assertEqual(self.window.registration.password.text(), "")
        self.assertEqual(self.calls, [])
        self.window.registration.reject()

    def test_stale_portal_response_cannot_open_previous_account(self):
        called = []
        self.window.pending[17] = (None, self.window.generation, lambda result: called.append(result), True)
        self.window.invalidate_identity()
        self.window.result_ready(17, {"ok": True, "url": "https://old.invalid/player/#token=fixture"})
        self.assertEqual(called, [])
        self.assertIsNone(self.window.portal_view)

    def test_portal_origin_and_popups_are_restricted_without_a_native_bridge(self):
        self.window.portal_ready({"ok": True, "url": "https://other.invalid/player/#token=fixture"})
        self.assertIsNone(self.window.portal_view)
        self.assertIn("invalid", self.window.portal_status.text())
        # Verify navigation checks directly without constructing/loading a web page.
        class PageFixture:
            allowed_origin = ("https", "expected.invalid", 443)
        from PySide6.QtCore import QUrl
        allowed = ui.PortalPage.acceptNavigationRequest
        self.assertTrue(allowed(PageFixture(), QUrl("https://expected.invalid/player/"), None, True))
        self.assertFalse(allowed(PageFixture(), QUrl("https://other.invalid/"), None, True))
        self.assertFalse(allowed(PageFixture(), QUrl("file:///tmp/private"), None, True))
        self.assertIsNone(ui.PortalPage.createWindow(PageFixture(), None))

    def test_secure_storage_unavailable_disables_remember_and_payload(self):
        state = ui.fixture_state()
        state.update(credential_storage_available=False, remember=True)
        self.window.apply_state(state)
        self.assertFalse(self.window.remember.isEnabled())
        self.assertFalse(self.window.remember.isChecked())
        self.assertFalse(self.window.payload()["remember"])
        self.assertIn("unavailable", self.window.storage_note.text())

    def test_registration_or_restored_account_change_clears_existing_portal(self):
        state = ui.fixture_state()
        state["username"] = "newly_registered_account"
        before = self.window.generation
        with patch.object(self.window, "clear_portal") as clear:
            self.window.apply_state(state)
        clear.assert_called_once_with()
        self.assertGreater(self.window.generation, before)
        self.assertEqual(self.window.username.currentText(), "newly_registered_account")

    def test_password_edit_invalidates_pending_account_restore(self):
        called = []
        self.window.pending[18] = (None, self.window.generation, lambda result: called.append(result), True)
        self.window.password_changed("new password")
        self.window.result_ready(18, {"ok": True, "state": {"password": "previous password"}})
        self.assertEqual(called, [])
        self.assertTrue(self.window.password_edited)


if __name__ == "__main__":
    unittest.main()
