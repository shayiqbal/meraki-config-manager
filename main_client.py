"""GrayBar Meraki Manager v2 — Client Entry Point with Profile Authentication.

Login flow:
  Landing  →  New User   →  Create profile (username + password + API key)
           →  Existing   →  Sign in (username + password)
                         →  Forgot Password → Delete profile
"""
from __future__ import annotations

import faulthandler
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from auth.profile_store import (
    authenticate,
    create_profile,
    delete_profile,
    username_exists,
)
from config.settings import Settings
from gui.v1.main_window_v1 import MainWindowV1

_APP_NAME  = "GrayBar Meraki Manager"
_FAULT_LOG = Path("logs/faulthandler.log")

# ── Shared stylesheet ──────────────────────────────────────────────────────────
_STYLE = """
QDialog, QWidget {
    background-color: #f8fafc;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #0f172a;
}
QLabel#app-title {
    font-size: 22px; font-weight: 700; color: #1e293b;
}
QLabel#app-sub {
    font-size: 12px; color: #64748b;
}
QLabel#screen-title {
    font-size: 15px; font-weight: 700; color: #1e293b;
}
QLabel#field-label {
    font-size: 12px; font-weight: 600; color: #374151;
}
QLabel#notice {
    font-size: 11px; color: #94a3b8;
}
QLabel#error {
    font-size: 12px; color: #dc2626;
}
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 13px;
    color: #0f172a;
}
QLineEdit:focus { border-color: #2563eb; }
QPushButton#primary {
    background-color: #2563eb; color: #ffffff;
    border: none; border-radius: 6px;
    padding: 9px 24px; font-size: 13px; font-weight: 600;
    min-height: 36px;
}
QPushButton#primary:hover  { background-color: #1d4ed8; }
QPushButton#primary:disabled { background-color: #bfdbfe; }
QPushButton#danger {
    background-color: #dc2626; color: #ffffff;
    border: none; border-radius: 6px;
    padding: 9px 24px; font-size: 13px; font-weight: 600;
    min-height: 36px;
}
QPushButton#danger:hover { background-color: #b91c1c; }
QPushButton#secondary {
    background-color: #f1f5f9; color: #334155;
    border: 1px solid #e2e8f0; border-radius: 6px;
    padding: 9px 20px; font-size: 13px; min-height: 36px;
}
QPushButton#secondary:hover { background-color: #e2e8f0; }
QPushButton#ghost {
    background: transparent; border: none;
    color: #2563eb; font-size: 12px; padding: 4px 8px;
}
QPushButton#ghost:hover { color: #1d4ed8; text-decoration: underline; }
QPushButton#toggle {
    background: transparent; border: none;
    color: #64748b; font-size: 16px; padding: 0 6px;
}
QPushButton#toggle:hover { color: #2563eb; }
QFrame#divider {
    background-color: #e2e8f0; max-height: 1px;
}
"""


# ── Crash handling ─────────────────────────────────────────────────────────────

def _install_handlers() -> None:
    try:
        _FAULT_LOG.parent.mkdir(parents=True, exist_ok=True)
        faulthandler.enable(file=_FAULT_LOG.open("w"))
    except Exception:
        pass

    def _hook(exc_type, exc_value, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            with open("logs/crash.log", "a") as f:
                f.write(f"\n{'─'*60}\n{msg}\n")
        except Exception:
            pass
        QMessageBox.critical(None, "Unexpected Error", msg[:2000])

    sys.excepthook = _hook


class _App(QApplication):
    def notify(self, receiver, event):
        try:
            return super().notify(receiver, event)
        except Exception:
            QMessageBox.critical(None, "Unexpected Error", traceback.format_exc()[:2000])
            return False


# ── Helper widgets ─────────────────────────────────────────────────────────────

def _divider() -> QFrame:
    f = QFrame()
    f.setObjectName("divider")
    f.setFrameShape(QFrame.Shape.HLine)
    return f


def _password_row(placeholder: str = "Enter password…") -> tuple[QLineEdit, QPushButton]:
    """Return (QLineEdit, toggle_btn) pre-configured for password entry."""
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    btn = QPushButton("👁")
    btn.setObjectName("toggle")
    btn.setFixedWidth(34)
    btn.setToolTip("Show / hide")

    def _toggle():
        hidden = edit.echoMode() == QLineEdit.EchoMode.Password
        edit.setEchoMode(
            QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password
        )
        btn.setText("🙈" if hidden else "👁")

    btn.clicked.connect(_toggle)
    return edit, btn


def _pw_layout(edit: QLineEdit, toggle: QPushButton) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(4)
    row.addWidget(edit)
    row.addWidget(toggle)
    return row


# ── Main Login Dialog ──────────────────────────────────────────────────────────

class LoginDialog(QDialog):
    """3-screen login flow: Landing → New User | Existing User → (Forgot Password)."""

    # Page indices in the stacked widget
    _PAGE_LANDING  = 0
    _PAGE_NEW      = 1
    _PAGE_EXISTING = 2
    _PAGE_DELETE   = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_APP_NAME)
        self.setFixedWidth(460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet(_STYLE)
        self._authenticated_key: str = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(0)

        # App branding (always visible)
        title = QLabel(_APP_NAME)
        title.setObjectName("app-title")
        sub = QLabel("Cisco Meraki Network Management")
        sub.setObjectName("app-sub")
        root.addWidget(title)
        root.addSpacing(2)
        root.addWidget(sub)
        root.addSpacing(20)
        root.addWidget(_divider())
        root.addSpacing(20)

        # Stacked pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_landing())   # 0
        self._stack.addWidget(self._build_new_user())  # 1
        self._stack.addWidget(self._build_existing())  # 2
        self._stack.addWidget(self._build_delete())    # 3
        root.addWidget(self._stack)

        self._goto(self._PAGE_LANDING)

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _goto(self, page: int) -> None:
        self._stack.setCurrentIndex(page)
        # Clear errors when navigating
        for lbl in (self._new_error, self._existing_error, self._delete_error):
            lbl.setVisible(False)

    # ── Page 0: Landing ────────────────────────────────────────────────────────

    def _build_landing(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lbl = QLabel("Are you a new or existing user?")
        lbl.setObjectName("screen-title")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)
        lay.addSpacing(8)

        new_btn = QPushButton("  New User  —  Create Profile")
        new_btn.setObjectName("primary")
        new_btn.clicked.connect(lambda: self._goto(self._PAGE_NEW))

        existing_btn = QPushButton("  Existing User  —  Sign In")
        existing_btn.setObjectName("secondary")
        existing_btn.clicked.connect(lambda: self._goto(self._PAGE_EXISTING))

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("ghost")
        cancel_btn.clicked.connect(self.reject)

        lay.addWidget(new_btn)
        lay.addWidget(existing_btn)
        lay.addSpacing(8)
        lay.addWidget(cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    # ── Page 1: New User ────────────────────────────────────────────────────────

    def _build_new_user(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        title = QLabel("Create Your Profile")
        title.setObjectName("screen-title")
        lay.addWidget(title)
        lay.addSpacing(4)

        # Username
        lay.addWidget(self._lbl("Username"))
        self._new_username = QLineEdit()
        self._new_username.setPlaceholderText("e.g. John Smith")
        lay.addWidget(self._new_username)

        # Password
        lay.addWidget(self._lbl("Password"))
        self._new_pw, new_pw_toggle = _password_row("Create a password")
        lay.addLayout(_pw_layout(self._new_pw, new_pw_toggle))

        # Confirm password
        lay.addWidget(self._lbl("Confirm Password"))
        self._new_pw2, new_pw2_toggle = _password_row("Re-enter your password")
        lay.addLayout(_pw_layout(self._new_pw2, new_pw2_toggle))

        # API Key
        lay.addWidget(self._lbl("Meraki Dashboard API Key"))
        self._new_api, new_api_toggle = _password_row("Paste your API key here…")
        lay.addLayout(_pw_layout(self._new_api, new_api_toggle))

        # Error
        self._new_error = QLabel("")
        self._new_error.setObjectName("error")
        self._new_error.setWordWrap(True)
        self._new_error.setVisible(False)
        lay.addWidget(self._new_error)

        # Buttons
        lay.addSpacing(4)
        btn_row = QHBoxLayout()
        back = QPushButton("← Back")
        back.setObjectName("secondary")
        back.clicked.connect(lambda: self._goto(self._PAGE_LANDING))
        create = QPushButton("Create & Sign In")
        create.setObjectName("primary")
        create.clicked.connect(self._do_create)
        self._new_username.returnPressed.connect(self._do_create)
        self._new_pw2.returnPressed.connect(self._do_create)
        btn_row.addWidget(back)
        btn_row.addStretch()
        btn_row.addWidget(create)
        lay.addLayout(btn_row)

        notice = QLabel("Your API key is encrypted with your password and never stored in plaintext.")
        notice.setObjectName("notice")
        notice.setWordWrap(True)
        lay.addSpacing(8)
        lay.addWidget(notice)
        return w

    # ── Page 2: Existing User ──────────────────────────────────────────────────

    def _build_existing(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        title = QLabel("Sign In")
        title.setObjectName("screen-title")
        lay.addWidget(title)
        lay.addSpacing(4)

        lay.addWidget(self._lbl("Username"))
        self._ex_username = QLineEdit()
        self._ex_username.setPlaceholderText("Enter your username")
        lay.addWidget(self._ex_username)

        lay.addWidget(self._lbl("Password"))
        self._ex_pw, ex_pw_toggle = _password_row("Enter your password")
        lay.addLayout(_pw_layout(self._ex_pw, ex_pw_toggle))

        self._existing_error = QLabel("")
        self._existing_error.setObjectName("error")
        self._existing_error.setWordWrap(True)
        self._existing_error.setVisible(False)
        lay.addWidget(self._existing_error)

        lay.addSpacing(4)
        btn_row = QHBoxLayout()
        back = QPushButton("← Back")
        back.setObjectName("secondary")
        back.clicked.connect(lambda: self._goto(self._PAGE_LANDING))
        sign_in = QPushButton("Sign In")
        sign_in.setObjectName("primary")
        sign_in.clicked.connect(self._do_sign_in)
        self._ex_pw.returnPressed.connect(self._do_sign_in)
        btn_row.addWidget(back)
        btn_row.addStretch()
        btn_row.addWidget(sign_in)
        lay.addLayout(btn_row)

        lay.addSpacing(12)
        lay.addWidget(_divider())
        lay.addSpacing(8)
        forgot = QPushButton("Forgot password? Delete my profile")
        forgot.setObjectName("ghost")
        forgot.clicked.connect(lambda: self._goto(self._PAGE_DELETE))
        lay.addWidget(forgot, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    # ── Page 3: Delete Profile (Forgot Password) ───────────────────────────────

    def _build_delete(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        title = QLabel("Delete Profile")
        title.setObjectName("screen-title")
        lay.addWidget(title)
        lay.addSpacing(2)

        warning = QLabel(
            "This will permanently delete your profile.\n"
            "Your stored API key cannot be recovered.\n"
            "You will need to create a new profile after deletion."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #92400e; background: #fef3c7; "
                              "border-radius: 6px; padding: 10px;")
        lay.addWidget(warning)
        lay.addSpacing(8)

        lay.addWidget(self._lbl("Username to delete"))
        self._del_username = QLineEdit()
        self._del_username.setPlaceholderText("Enter the username to delete")
        lay.addWidget(self._del_username)

        self._delete_error = QLabel("")
        self._delete_error.setObjectName("error")
        self._delete_error.setWordWrap(True)
        self._delete_error.setVisible(False)
        lay.addWidget(self._delete_error)

        lay.addSpacing(4)
        btn_row = QHBoxLayout()
        back = QPushButton("← Back")
        back.setObjectName("secondary")
        back.clicked.connect(lambda: self._goto(self._PAGE_EXISTING))
        delete = QPushButton("Delete Profile")
        delete.setObjectName("danger")
        delete.clicked.connect(self._do_delete)
        self._del_username.returnPressed.connect(self._do_delete)
        btn_row.addWidget(back)
        btn_row.addStretch()
        btn_row.addWidget(delete)
        lay.addLayout(btn_row)
        return w

    # ── Actions ────────────────────────────────────────────────────────────────

    def _do_create(self) -> None:
        username = self._new_username.text().strip()
        password = self._new_pw.text()
        confirm  = self._new_pw2.text()
        api_key  = self._new_api.text().strip()

        if not username:
            self._new_error.setText("Username is required.")
            self._new_error.setVisible(True)
            return
        if len(password) < 8:
            self._new_error.setText("Password must be at least 8 characters.")
            self._new_error.setVisible(True)
            return
        if password != confirm:
            self._new_error.setText("Passwords do not match.")
            self._new_error.setVisible(True)
            return
        if not api_key:
            self._new_error.setText("API key is required.")
            self._new_error.setVisible(True)
            return

        # Validate API key with Meraki before saving
        self._new_error.setText("Validating API key with Meraki Dashboard…")
        self._new_error.setStyleSheet("color: #2563eb; font-size: 12px;")
        self._new_error.setVisible(True)
        QApplication.processEvents()

        try:
            import meraki
            dashboard = meraki.DashboardAPI(
                api_key=api_key,
                suppress_logging=True,
                print_console=False,
                wait_on_rate_limit=False,
                maximum_retries=1,
            )
            dashboard.organizations.getOrganizations()
        except Exception as exc:
            msg = str(exc)
            self._new_error.setText(
                "Invalid API key — please check and try again."
                if "401" in msg or "403" in msg
                else f"Could not reach Meraki Dashboard:\n{msg[:100]}"
            )
            self._new_error.setStyleSheet("color: #dc2626; font-size: 12px;")
            self._new_error.setVisible(True)
            return

        try:
            create_profile(username, password, api_key)
        except ValueError as exc:
            self._new_error.setText(str(exc))
            self._new_error.setStyleSheet("color: #dc2626; font-size: 12px;")
            self._new_error.setVisible(True)
            return

        self._authenticated_key = api_key
        self.accept()

    def _do_sign_in(self) -> None:
        username = self._ex_username.text().strip()
        password = self._ex_pw.text()

        if not username or not password:
            self._existing_error.setText("Please enter your username and password.")
            self._existing_error.setVisible(True)
            return

        try:
            api_key = authenticate(username, password)
        except ValueError as exc:
            self._existing_error.setText(str(exc))
            self._existing_error.setVisible(True)
            return

        self._authenticated_key = api_key
        self.accept()

    def _do_delete(self) -> None:
        username = self._del_username.text().strip()
        if not username:
            self._delete_error.setText("Please enter the username to delete.")
            self._delete_error.setVisible(True)
            return

        answer = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Permanently delete the profile for '{username}'?\n\n"
            "This cannot be undone. You will need to create a new profile "
            "with your API key.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        deleted = delete_profile(username)
        if not deleted:
            self._delete_error.setText(
                f"No profile found for '{username}'. Check the username and try again."
            )
            self._delete_error.setVisible(True)
            return

        QMessageBox.information(
            self,
            "Profile Deleted",
            f"Profile for '{username}' has been deleted.\n\n"
            "Please create a new profile to continue.",
        )
        self._goto(self._PAGE_LANDING)

    # ── Result accessor ────────────────────────────────────────────────────────

    def authenticated_key(self) -> str:
        return self._authenticated_key

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("field-label")
        return lbl


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    _install_handlers()

    app = _App(sys.argv)
    app.setApplicationName(_APP_NAME)
    app.setOrganizationName("GrayBar")

    dlg = LoginDialog()
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return 0

    settings = Settings(
        api_key=dlg.authenticated_key(),
        max_retries=4,
        retry_base_seconds=1.0,
        early_access=True,
    )

    window = MainWindowV1(settings, app_name=_APP_NAME, show_credits=False)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
