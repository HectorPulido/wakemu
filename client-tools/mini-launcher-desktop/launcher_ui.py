"""Shared native launcher for macOS, Windows and Linux.

The remote portal lives in a separate WebEngine page with no Python bridge.
Only native widgets can invoke the account backend.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import uuid

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

import launcher_backend as backend


def origin(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            return None
        return parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == "https" else 80)
    except (TypeError, ValueError):
        return None


class PortalPage(QWebEnginePage):
    """A remote page cannot invoke native launcher actions or leave its server."""
    def __init__(self, profile, allowed_origin, parent=None):
        super().__init__(profile, parent)
        self.allowed_origin = allowed_origin
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        return url.toString() == "about:blank" or origin(url.toString()) == self.allowed_origin

    def createWindow(self, window_type):
        return None


class WorkSignals(QObject):
    finished = Signal(int, object)


class BackendWork(QRunnable):
    def __init__(self, identifier, dispatch, action, data):
        super().__init__()
        self.identifier, self.dispatch, self.action = identifier, dispatch, action
        self.data = deepcopy(data)
        self.signals = WorkSignals()

    @Slot()
    def run(self):
        try:
            result = self.dispatch(self.action, self.data)
        except backend.LauncherError as error:
            result = {"ok": False, "error": str(error)}
        except Exception:
            # Passwords and response bodies must never appear in error messages.
            result = {"ok": False, "error": "The launcher could not complete this operation. Check your configuration and try again."}
        self.signals.finished.emit(self.identifier, result)


class RegistrationDialog(QDialog):
    def __init__(self, launcher):
        super().__init__(launcher)
        self.launcher = launcher
        self.submitting = False
        self.setWindowTitle("Create a game account")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        explanation = QLabel("Create an account on the selected private server.\nYour official game account is separate.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.confirm = QLineEdit()
        for field in (self.password, self.confirm):
            field.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        form.addRow("Confirm password", self.confirm)
        layout.addLayout(form)
        self.status = QLabel("Usernames: 3–32 letters, numbers, hyphens or underscores.\nPasswords: 8–256 characters.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.create_button = self.buttons.addButton("Create account", QDialogButtonBox.ButtonRole.AcceptRole)
        self.create_button.clicked.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        QTimer.singleShot(0, self.username.setFocus)

    def reject(self):
        if not self.submitting:
            super().reject()

    def submit(self):
        username, password = self.username.text().strip(), self.password.text()
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,32}", username):
            self.status.setText("Username: 3–32 letters, numbers, hyphens or underscores.")
            return
        if not 8 <= len(password) <= 256:
            self.status.setText("Password: 8–256 characters.")
            return
        if password != self.confirm.text():
            self.status.setText("Passwords do not match.")
            return
        data = self.launcher.payload()
        data.update(username=username, password=password, password_confirm=self.confirm.text(), password_edited=True)
        self.submitting = True
        self.buttons.setEnabled(False)
        self.status.setText("Creating your account…")

        def complete(result):
            self.submitting = False
            self.buttons.setEnabled(True)
            if result.get("ok"):
                self.launcher.apply_state(result["state"])
                self.accept()
            else:
                self.status.setText(result.get("error", "Could not create the account."))

        self.launcher.request("register", data, complete, report_error=False)


class Launcher(QMainWindow):
    FIELD_LABELS = {
        "name": "Server name", "server_host": "Server domain or IP",
        "install_root": "Client folder", "dispatch_port": "Dispatcher port",
        "game_ports": "Game ports", "chat_host": "Chat domain or IP", "chat_port": "Chat port",
        "api_url": "Authentication URL", "http_url": "Resources URL", "shop_url": "Shop URL",
        "achievements_url": "Achievements URL", "certificate": "Certificate file",
    }
    IDENTITY_FIELDS = {"server_host", "dispatch_port", "game_ports", "chat_host", "chat_port", "api_url", "http_url", "shop_url", "achievements_url", "certificate"}

    def __init__(self, dispatch=None, initial_state=None):
        super().__init__()
        self.dispatch = dispatch or backend.dispatch
        self.loading = False
        self.generation = 0
        self.serial = 0
        self.pending = {}
        self.servers = []
        self.current_id = "local"
        self.known_username = ""
        self.password_edited = False
        self.storage_available = True
        self.portal_view = None
        self.portal_profile = None
        self.registration = None
        self.closing = False
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(650)
        self.save_timer.timeout.connect(self.save)
        self.setWindowTitle("Wakfu Minilauncher")
        self.resize(1080, 820)
        self.setMinimumSize(820, 640)
        self.build_ui()
        if initial_state is not None:
            self.apply_state(initial_state)
        else:
            self.request("state", {}, self.state_loaded)

    def build_ui(self):
        self.setStyleSheet("""
            QMainWindow, QDialog { background: #f5f8fa; color: #173746; }
            QWidget { color: #173746; font-size: 14px; }
            QLineEdit, QComboBox { background: white; padding: 7px; border: 1px solid #d4dde1; border-radius: 5px; }
            QPushButton { background: #e4eaed; padding: 8px 14px; border: 0; border-radius: 5px; }
            QPushButton:hover { background: #d6e2e6; }
            QPushButton:disabled { color: #8a999f; }
            QPushButton#play { background: #287c81; color: white; font-weight: bold; }
            QTabWidget::pane { border: 0; } QTabWidget::tab-bar { left: 0; }
            QTabBar::tab { padding: 10px 16px; background: #e4eaed; margin-right: 6px; border-radius: 5px; }
            QTabBar::tab:selected { background: #287c81; color: white; }
            QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #a6b8c0; border-radius: 3px; background: white; }
            QCheckBox::indicator:checked { background: #287c81; }
            QScrollArea, QScrollArea > QWidget > QWidget { background: #f5f8fa; border: 0; }
        """)
        outer = QWidget()
        self.setCentralWidget(outer)
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(24, 20, 24, 20)
        heading = QHBoxLayout()
        brand = QLabel("WAKFU")
        brand.setStyleSheet("font-size: 32px; font-weight: bold;")
        heading.addWidget(brand)
        heading.addWidget(QLabel("Your server. Your accounts."))
        heading.addStretch()
        layout.addLayout(heading)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        play = QWidget()
        scroll.setWidget(play)
        self.tabs.addTab(scroll, "Play")
        form_layout = QVBoxLayout(play)
        server_row = QHBoxLayout()
        self.server_picker = QComboBox()
        self.server_picker.currentIndexChanged.connect(self.switch_server)
        server_row.addWidget(self.server_picker, 1)
        new_server = QPushButton("New server")
        new_server.clicked.connect(self.new_server)
        server_row.addWidget(new_server)
        form_layout.addLayout(server_row)
        self.fields = {}
        basic = QFormLayout()
        basic.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for key in ("name", "server_host", "install_root"):
            basic.addRow(self.FIELD_LABELS[key], self.make_field(key, browse=key == "install_root"))
        form_layout.addLayout(basic)
        detect = QPushButton("Detect configuration")
        detect.clicked.connect(self.discover)
        form_layout.addWidget(detect, alignment=Qt.AlignmentFlag.AlignLeft)
        account_form = QFormLayout()
        account_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.username = QComboBox()
        self.username.setEditable(True)
        self.username.editTextChanged.connect(self.account_changed)
        account_form.addRow("Username", self.username)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.textEdited.connect(self.password_changed)
        account_form.addRow("Password", self.password)
        form_layout.addLayout(account_form)
        self.remember = QCheckBox("Save account and password")
        self.remember.toggled.connect(self.schedule_save)
        form_layout.addWidget(self.remember)
        self.storage_note = QLabel("")
        self.storage_note.setWordWrap(True)
        form_layout.addWidget(self.storage_note)
        actions = QHBoxLayout()
        for label, callback in (
            ("Forget saved sign-in", self.forget), ("Register", self.open_registration),
            ("Check connection", self.check), ("Play", self.play),
        ):
            button = QPushButton(label)
            if label == "Play":
                button.setObjectName("play")
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch()
        form_layout.addLayout(actions)
        self.status = QLabel("Loading your servers…")
        self.status.setWordWrap(True)
        form_layout.addWidget(self.status)
        advanced_toggle = QCheckBox("Advanced settings")
        self.advanced = QWidget()
        advanced_form = QFormLayout(self.advanced)
        advanced_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for key in self.FIELD_LABELS:
            if key not in self.fields:
                advanced_form.addRow(self.FIELD_LABELS[key], self.make_field(key, browse=key == "certificate"))
        self.advanced.setVisible(False)
        advanced_toggle.toggled.connect(self.advanced.setVisible)
        form_layout.addWidget(advanced_toggle)
        form_layout.addWidget(self.advanced)
        form_layout.addStretch()
        self.portal_tab = QWidget()
        portal_layout = QVBoxLayout(self.portal_tab)
        portal_actions = QHBoxLayout()
        open_portal = QPushButton("Open achievements")
        open_portal.clicked.connect(self.open_portal)
        reload_portal = QPushButton("Reload")
        reload_portal.clicked.connect(self.reload_portal)
        portal_actions.addWidget(open_portal)
        portal_actions.addWidget(reload_portal)
        portal_actions.addStretch()
        portal_layout.addLayout(portal_actions)
        self.portal_status = QLabel("Open achievements using the account selected in Play.")
        self.portal_status.setWordWrap(True)
        portal_layout.addWidget(self.portal_status)
        self.portal_holder = QVBoxLayout()
        portal_layout.addLayout(self.portal_holder, 1)
        self.tabs.addTab(self.portal_tab, "Achievements and dungeons")

    def make_field(self, key, browse=False):
        field = QLineEdit()
        self.fields[key] = field
        field.textEdited.connect(lambda _text, name=key: self.field_changed(name))
        if not browse:
            return field
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(field, 1)
        button = QPushButton("Browse…")
        button.clicked.connect(lambda: self.browse(key))
        row.addWidget(button)
        return container

    def browse(self, key):
        if key == "install_root":
            value = QFileDialog.getExistingDirectory(self, "Select your Wakfu client folder", self.fields[key].text())
        else:
            value, _ = QFileDialog.getOpenFileName(self, "Select the server certificate", self.fields[key].text())
        if value:
            self.fields[key].setText(value)
            self.field_changed(key)

    def payload(self):
        server = {key: field.text().strip() for key, field in self.fields.items()}
        server["id"] = self.current_id
        return {"server": server, "selected_id": self.current_id,
                "username": self.username.currentText().strip(), "password": self.password.text(),
                "password_edited": self.password_edited, "remember": self.storage_available and self.remember.isChecked()}

    def request(self, action, data, callback=None, *, generation=None, report_error=True):
        self.serial += 1
        identifier = self.serial
        task = BackendWork(identifier, self.dispatch, action, data)
        expected = self.generation if generation is None else generation
        self.pending[identifier] = (task, expected, callback, report_error)
        task.signals.finished.connect(self.result_ready)
        self.status.setText({"play": "Signing in and opening Wakfu…", "save": "Saving…", "discover": "Detecting ports and services…", "check": "Checking connection…", "register": "Creating your account…"}.get(action, "Loading…"))
        self.pool.start(task)

    @Slot(int, object)
    def result_ready(self, identifier, result):
        entry = self.pending.pop(identifier, None)
        if entry is None:
            return
        _task, generation, callback, report_error = entry
        if generation != self.generation:
            return
        if result.get("ok"):
            self.status.setText(result.get("message", "Changes saved."))
        elif report_error:
            self.status.setText(result.get("error", "The operation failed."))
        if callback:
            callback(result)

    def state_loaded(self, result):
        if result.get("ok"):
            self.apply_state(result["state"])

    def apply_state(self, state):
        selected = state.get("selected_id", self.current_id)
        selected_username = state.get("username", state.get("selected_username", ""))
        if selected != self.current_id or selected_username != self.username.currentText().strip():
            self.invalidate_identity()
        self.loading = True
        self.servers = deepcopy(state.get("servers", []))
        self.current_id = state.get("selected_id", self.current_id)
        self.server_picker.clear()
        for server in self.servers:
            self.server_picker.addItem(server.get("name", "Server"), server["id"])
        index = self.server_picker.findData(self.current_id)
        self.server_picker.setCurrentIndex(max(0, index))
        server = next((s for s in self.servers if s["id"] == self.current_id), {})
        for key, field in self.fields.items():
            value = server.get(key, "")
            field.setText(", ".join(str(p) for p in value) if isinstance(value, list) else str(value))
        username = selected_username
        self.username.clear()
        self.username.addItems(state.get("accounts", []))
        self.username.setEditText(username)
        self.known_username = username
        self.password.setText(state.get("password", ""))
        self.password_edited = False
        self.storage_available = state.get("credential_storage_available", True)
        self.remember.setEnabled(self.storage_available)
        self.remember.setChecked(self.storage_available and state.get("remember", False))
        self.storage_note.setText("" if self.storage_available else "Secure credential storage is unavailable. Sign-in will not be saved; configure your system keyring to enable it.")
        self.loading = False

    def schedule_save(self, *_args):
        if not self.loading:
            self.save_timer.start()

    def invalidate_identity(self):
        self.generation += 1
        self.clear_portal()

    def field_changed(self, key):
        if self.loading:
            return
        if key in self.IDENTITY_FIELDS:
            self.invalidate_identity()
            self.password.clear()
            self.password_edited = False
        self.schedule_save()

    def password_changed(self, _value):
        self.invalidate_identity()
        self.password_edited = True
        self.schedule_save()

    def account_changed(self, _value):
        if self.loading:
            return
        previous = self.payload()
        previous["username"] = self.known_username
        save_previous = self.save_timer.isActive() and bool(self.known_username)
        self.save_timer.stop()
        self.invalidate_identity()
        if save_previous:
            self.request("save", previous, report_error=False)
        self.password.clear()
        self.password_edited = False
        self.known_username = self.username.currentText().strip()
        # Restoring a different account is read-only; never save empty credentials
        # under the previous account while the user is editing the username.
        self.request("state", {"selected_id": self.current_id, "username": self.known_username}, self.account_restored)

    def account_restored(self, result):
        if result.get("ok"):
            state = result["state"]
            self.loading = True
            self.password.setText(state.get("password", ""))
            self.storage_available = state.get("credential_storage_available", True)
            self.remember.setEnabled(self.storage_available)
            self.remember.setChecked(self.storage_available and state.get("remember", False))
            self.loading = False

    def save(self):
        self.save_timer.stop()
        self.request("save", self.payload(), self.saved)

    def saved(self, result):
        if result.get("ok"):
            # Do not replace live edit fields with an older autosave response.
            state = result.get("state", {})
            self.servers = deepcopy(state.get("servers", self.servers))
            self.server_picker.blockSignals(True)
            for index in range(self.server_picker.count()):
                identifier = self.server_picker.itemData(index)
                server = next((s for s in self.servers if s["id"] == identifier), None)
                if server:
                    self.server_picker.setItemText(index, server.get("name", "Server"))
            self.server_picker.blockSignals(False)

    def switch_server(self, index):
        if self.loading or index < 0:
            return
        identifier = self.server_picker.itemData(index)
        if identifier == self.current_id:
            return
        old = self.payload()
        self.save_timer.stop()
        self.invalidate_identity()
        self.current_id = identifier
        self.password.clear()
        self.request("save", old, report_error=False)
        self.request("state", {"selected_id": identifier}, self.state_loaded)

    def new_server(self):
        self.save_timer.stop()
        old = self.payload()
        self.invalidate_identity()
        self.request("save", old, report_error=False)
        template = deepcopy(self.servers[0]) if self.servers else {}
        template.update(id=uuid.uuid4().hex, name="New server", certificate="")
        self.apply_state({"servers": self.servers + [template], "selected_id": template["id"], "accounts": [], "username": "", "password": "", "remember": False, "credential_storage_available": self.storage_available})

    def discover(self):
        self.save_timer.stop()
        self.request("discover", self.payload(), self.discovered)

    def discovered(self, result):
        if result.get("ok"):
            self.loading = True
            for key, value in result["server"].items():
                if key in self.fields:
                    self.fields[key].setText(", ".join(map(str, value)) if isinstance(value, list) else str(value))
            self.loading = False
            self.invalidate_identity()
            self.schedule_save()

    def forget(self):
        self.save_timer.stop()
        self.invalidate_identity()
        self.request("forget", {"selected_id": self.current_id, "username": self.username.currentText().strip()}, self.state_loaded)

    def check(self):
        self.save_timer.stop()
        self.request("check", self.payload())

    def play(self):
        self.save_timer.stop()
        self.request("play", self.payload())

    def open_registration(self):
        if self.registration and self.registration.isVisible():
            self.registration.raise_()
            return
        self.registration = RegistrationDialog(self)
        self.registration.open()

    def clear_portal(self):
        if self.portal_view is not None:
            view, profile = self.portal_view, self.portal_profile
            self.portal_view, self.portal_profile = None, None
            self.portal_holder.removeWidget(view)
            view.stop()
            view.hide()
            # Destroy every remote page before its off-the-record profile.
            view.page().destroyed.connect(profile.deleteLater)
            view.deleteLater()
        self.portal_status.setText("Open achievements using the account selected in Play.")

    def open_portal(self):
        self.save_timer.stop()
        self.clear_portal()
        self.portal_status.setText("Opening achievements with your account…")
        self.request("web-login", self.payload(), self.portal_ready)

    def portal_ready(self, result):
        if not result.get("ok"):
            self.portal_status.setText(result.get("error", "Could not open achievements."))
            return
        url = result.get("url", "")
        allowed = origin(self.fields["achievements_url"].text())
        if allowed is None or origin(url) != allowed:
            self.portal_status.setText("The achievements address returned by the server is invalid.")
            return
        self.clear_portal()
        self.portal_profile = QWebEngineProfile(self)
        self.portal_profile.downloadRequested.connect(lambda item: item.cancel())
        self.portal_view = QWebEngineView(self.portal_tab)
        self.portal_view.setPage(PortalPage(self.portal_profile, allowed, self.portal_view))
        self.portal_holder.addWidget(self.portal_view)
        self.portal_view.setUrl(QUrl(url))
        self.portal_status.setText("Account: " + self.username.currentText().strip() + ". Check the character before traveling.")
        self.tabs.setCurrentWidget(self.portal_tab)

    def reload_portal(self):
        if self.portal_view is not None:
            self.portal_view.reload()
        else:
            self.open_portal()

    def closeEvent(self, event: QCloseEvent):
        self.clear_portal()
        if self.save_timer.isActive() and not self.closing:
            self.closing = True
            self.save_timer.stop()
            event.ignore()
            self.request("save", self.payload(), lambda _result: self.close())
            return
        event.accept()


def fixture_state():
    server = backend.default_state()["servers"][0]
    return {"servers": [server], "selected_id": server["id"], "username": "", "accounts": [], "password": "", "remember": False, "credential_storage_available": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-smoke", type=Path, metavar="DIRECTORY", help="Render a local UI fixture without sign-in, game startup or network requests.")
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setApplicationName("Wakfu Minilauncher")
    if args.ui_smoke:
        calls = []
        def fixture_dispatch(action, data):
            calls.append(action)
            return {"ok": True, "state": fixture_state()}
        window = Launcher(dispatch=fixture_dispatch, initial_state=fixture_state())
        window.status.setText("Preview only; no sign-in or game launch.")
        window.show()
        def capture():
            args.ui_smoke.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(args.ui_smoke / "ui.png"))
            window.open_registration()
            dialog = window.registration
            dialog.username.setText("fixture_user")
            dialog.password.setText("fixture-password")
            dialog.confirm.setText("different-password")
            dialog.submit()
            checks = {
                "passwords_masked": dialog.password.echoMode() == QLineEdit.EchoMode.Password and dialog.confirm.echoMode() == QLineEdit.EchoMode.Password,
                "mismatch_keeps_dialog_open": dialog.isVisible(),
                "mismatch_message_english": dialog.status.text() == "Passwords do not match.",
                "mismatch_does_not_submit": not calls,
                "portal_separate_from_privileged_ui": window.portal_view is None,
            }
            dialog.grab().save(str(args.ui_smoke / "registration.png"))
            dialog.reject()
            checks["cancel_preserves_account"] = window.username.currentText() == ""
            checks["cancel_does_not_submit"] = not calls
            report = {"passed": all(checks.values()), "checks": checks, "backend_requests": calls, "game_started": False}
            (args.ui_smoke / "result.json").write_text(json.dumps(report, indent=2) + "\n")
            app.exit(0 if report["passed"] else 1)
        QTimer.singleShot(350, capture)
    else:
        window = Launcher()
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
