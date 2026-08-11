"""V1 main application window with sidebar navigation."""
from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from config.settings import Settings
from gui.v1.style import APP_STYLE
from gui.v1.widgets.activity_log import ActivityLogPanel
from gui.v1.widgets.compare_panel import ComparePanel
from gui.v1.widgets.copy_wizard import CopyWizardPanel
from gui.v1.widgets.dashboard import DashboardPanel
from gui.v1.widgets.networks_panel import NetworksPanel
from gui.v1.widgets.new_network_wizard import NewNetworkWizardPanel
from gui.workers import Worker
from meraki_client.client_v1 import MerakiVpnClientV1
from reporting.logging_config import configure_logging
from services.compare_service import CompareService as CompareNetworksService
from services.copy_service import CopyService
from services.network_service import NetworkService
from services.workflow import WorkflowService

# ─── Thread-safe callback dispatcher ──────────────────────────────────────────
class _Dispatcher(QObject):
    """Routes worker thread signals to Python callbacks on the GUI thread.

    Plain Python lambdas connected to signals have no thread affinity, so Qt
    may invoke them directly in the worker thread — causing silent C++ crashes
    when those lambdas touch Qt widgets.  Wrapping them in @Slot methods on a
    QObject that lives in the GUI thread forces Qt to use QueuedConnection and
    guarantees delivery on the GUI thread.
    """

    def __init__(
        self,
        result_cb=None,
        error_cb=None,
        finished_cb=None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._result_cb = result_cb
        self._error_cb = error_cb
        self._finished_cb = finished_cb

    @Slot(object)
    def on_result(self, value: object) -> None:
        if self._result_cb:
            self._result_cb(value)

    @Slot(str)
    def on_error(self, msg: str) -> None:
        if self._error_cb:
            self._error_cb(msg)

    @Slot()
    def on_finished(self) -> None:
        if self._finished_cb:
            self._finished_cb()
        self.deleteLater()


# ─── Sidebar navigation entries ───────────────────────────────────────────────
_NAV = [
    ("dashboard",    "  🏠  Dashboard"),
    ("networks",     "  🌐  Networks"),
    ("compare",     "  🔍  Compare Networks"),
    ("copy",         "  📋  Copy Rules"),
    ("new_network",  "  ➕  New Network"),
    ("activity",     "  📝  Activity Log"),
]


class MainWindowV1(QMainWindow):
    """V1 main window — sidebar navigation, modern layout, reuses proven backend."""

    # Emitted when the network list is refreshed so all panels can update
    networks_changed = Signal(list)

    def __init__(
        self,
        settings: Settings,
        app_name: str = "Meraki Config Tool",
        show_credits: bool = True,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._app_name = app_name
        self._show_credits = show_credits
        self._logger = configure_logging(settings.log_path)
        self._pool = QThreadPool.globalInstance()
        self._active_workers: set[Worker] = set()

        # ── Service layer ──────────────────────────────────────────────────
        self._client: MerakiVpnClientV1 | None = None
        self._workflow: WorkflowService | None = None
        self._copy_service: CopyService | None = None
        self._network_service: NetworkService | None = None
        self._compare_service: CompareNetworksService | None = None

        # ── State ──────────────────────────────────────────────────────────
        self._organizations: list[dict] = []
        self._networks: list[dict] = []
        self._current_org_id: str | None = None
        self._current_org_name: str = ""
        self._session_token: int = 0

        self.setWindowTitle(app_name)
        self.resize(1280, 820)
        self.setMinimumSize(1000, 640)
        self.setStyleSheet(APP_STYLE)

        # ── Central layout ─────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────────────────
        sidebar = self._build_sidebar()
        main_layout.addWidget(sidebar)

        # ── Right pane (top bar + content) ─────────────────────────────────
        right_pane = QWidget()
        right_lay = QVBoxLayout(right_pane)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)
        right_lay.addWidget(self._build_topbar())
        right_lay.addWidget(self._build_content())
        main_layout.addWidget(right_pane, 1)

        # ── Status bar ─────────────────────────────────────────────────────
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Connecting to Meraki Dashboard…")

        # ── Wire networks_changed to all panels ────────────────────────────
        self.networks_changed.connect(self._dashboard.refresh)
        self.networks_changed.connect(self._networks_panel.refresh)
        self.networks_changed.connect(self._compare_panel.refresh)
        self.networks_changed.connect(self._copy_wizard.refresh)
        self.networks_changed.connect(self._new_network.refresh)

        # ── Initial connection ─────────────────────────────────────────────
        self._connect()

    # ── Sidebar ────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(0)

        # Split app_name into two lines for sidebar (first word / rest)
        parts = self._app_name.split(" ", 1)
        app_title = QLabel(parts[0])
        app_title.setObjectName("app-title")
        app_version = QLabel(parts[1] if len(parts) > 1 else "")
        app_version.setObjectName("app-version")
        lay.addWidget(app_title)
        lay.addWidget(app_version)

        self._nav_buttons: dict[str, QPushButton] = {}
        for key, label in _NAV:
            btn = QPushButton(label)
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self.navigate_to(k))
            self._nav_buttons[key] = btn
            lay.addWidget(btn)
            if key == "exclusions":
                lay.addSpacing(8)

        lay.addStretch()

        # New Session button
        new_session_btn = QPushButton("  🔄  New Session")
        new_session_btn.setObjectName("nav")
        new_session_btn.setToolTip("Disconnect and reconnect with a new API key.")
        new_session_btn.clicked.connect(self._new_session)
        lay.addWidget(new_session_btn)

        # Mini connection indicator
        self._sidebar_conn = QLabel("⬤  Connecting…")
        self._sidebar_conn.setObjectName("app-version")
        self._sidebar_conn.setContentsMargins(16, 0, 0, 8)
        lay.addWidget(self._sidebar_conn)

        # Credits section — only shown in the internal (non-client) version
        if self._show_credits:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color: #334155; background-color: #334155; max-height: 1px;")
            lay.addWidget(sep)
            for line in ("Created by Shay Iqbal", "Technical Leader, CX", "Cisco"):
                lbl = QLabel(line)
                lbl.setObjectName("app-version")
                lbl.setContentsMargins(16, 2, 16, 2)
                lay.addWidget(lbl)
        lay.addSpacing(8)

        return sidebar

    # ── Top bar ────────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        topbar = QWidget()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(56)
        lay = QHBoxLayout(topbar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(12)

        self._page_title_label = QLabel("Dashboard")
        self._page_title_label.setObjectName("page-title")
        lay.addWidget(self._page_title_label)
        lay.addStretch()

        # Organization selector
        org_label = QLabel("Organization:")
        org_label.setObjectName("section-sub")
        self._org_combo = QComboBox()
        self._org_combo.setMinimumWidth(220)
        self._org_combo.setEnabled(False)
        self._org_combo.currentIndexChanged.connect(self._on_org_changed)

        self._load_nets_btn = QPushButton("Load Networks")
        self._load_nets_btn.setObjectName("primary")
        self._load_nets_btn.setEnabled(False)
        self._load_nets_btn.clicked.connect(self._load_networks)

        self._conn_label = QLabel("Connecting…")
        self._conn_label.setObjectName("conn-pending")

        lay.addWidget(self._conn_label)
        lay.addWidget(org_label)
        lay.addWidget(self._org_combo)
        lay.addWidget(self._load_nets_btn)
        return topbar

    # ── Content area ───────────────────────────────────────────────────────

    def _build_content(self) -> QStackedWidget:
        self._content = QStackedWidget()
        self._dashboard = DashboardPanel(self)
        self._networks_panel = NetworksPanel(self)
        self._compare_panel = ComparePanel(self)
        self._copy_wizard = CopyWizardPanel(self)
        self._new_network = NewNetworkWizardPanel(self)
        self._activity_log = ActivityLogPanel(self)

        self._panels = {
            "dashboard": self._dashboard,
            "networks": self._networks_panel,
            "compare": self._compare_panel,
            "copy": self._copy_wizard,
            "new_network": self._new_network,
            "activity": self._activity_log,
        }
        for panel in self._panels.values():
            self._content.addWidget(panel)
        return self._content

    # ── Navigation ─────────────────────────────────────────────────────────

    def navigate_to(self, key: str, context: dict | None = None) -> None:
        panel = self._panels.get(key)
        if panel is None:
            return
        self._content.setCurrentWidget(panel)
        # Update sidebar button states
        for k, btn in self._nav_buttons.items():
            btn.setChecked(k == key)
        # Update top-bar page title
        labels = {
            "dashboard": "Dashboard",
            "networks": "Networks",
            "compare": "Compare Networks",
            "copy": "Copy Rules",
            "new_network": "New Network",
            "activity": "Activity Log",
        }
        self._page_title_label.setText(labels.get(key, ""))
        # Handle contextual navigation
        if context and key == "new_network" and "template" in context:
            self._new_network.pre_select_template(context["template"])

    # ── Connection and org loading ─────────────────────────────────────────

    def _connect(self) -> None:
        try:
            self._settings.validate()
            self._client = MerakiVpnClientV1(self._settings, self._logger)
            self._workflow = WorkflowService(self._client)
            self._copy_service = CopyService(self._client)
            self._network_service = NetworkService(self._client)
            self._compare_service = CompareNetworksService(self._client)
        except Exception as exc:
            self._conn_label.setText("Not Connected")
            self._conn_label.setObjectName("conn-fail")
            self._sidebar_conn.setText("⬤  Not Connected")
            self.statusBar().showMessage(str(exc))
            self.log_activity(str(exc), "ERROR")
            return
        self.run_worker(
            self._client.organizations,
            on_result=self._on_orgs,
            on_error=self._on_connect_error,
            status_msg="Loading organizations…",
        )

    def _on_orgs(self, orgs: list[dict]) -> None:
        self._organizations = orgs
        self._org_combo.blockSignals(True)
        self._org_combo.clear()
        self._org_combo.addItem("Choose an organization…", None)
        for org in orgs:
            self._org_combo.addItem(org["name"], org["id"])
        self._org_combo.blockSignals(False)
        self._org_combo.setEnabled(True)
        self._load_nets_btn.setEnabled(False)
        self._conn_label.setText(f"✓ Connected  ({len(orgs)} org)")
        self._conn_label.setObjectName("conn-ok")
        self._sidebar_conn.setText(f"⬤  {len(orgs)} org(s)")
        self._conn_label.setStyleSheet("")
        self.statusBar().showMessage("Connected — select an organization.")
        self.log_activity(f"Connected to Meraki Dashboard. {len(orgs)} organization(s) found.", "SUCCESS")
        self.navigate_to("dashboard")

    def _on_connect_error(self, msg: str) -> None:
        self._conn_label.setText("Connection failed")
        self._conn_label.setObjectName("conn-fail")
        self._conn_label.setStyleSheet("")
        self._sidebar_conn.setText("⬤  Failed")
        self.statusBar().showMessage(
            "Connection failed — update MERAKI_DASHBOARD_API_KEY in .env then click 'New Session'"
        )
        self.log_activity(
            f"Connection failed: {msg.splitlines()[-1]}  "
            f"— edit .env and click 'New Session' to retry.",
            "ERROR",
        )

    def _on_org_changed(self, index: int) -> None:
        # Bump token so any in-flight load for the previous org is silently discarded
        self._session_token += 1
        org_id = self._org_combo.currentData()
        self._load_nets_btn.setEnabled(bool(org_id))
        self._networks = []
        self._current_org_id = None
        self._current_org_name = ""
        self.networks_changed.emit([])
        if org_id:
            self.statusBar().showMessage(
                f"Organization changed — click 'Load Networks' to switch."
            )

    def _load_networks(self) -> None:
        org_id = self._org_combo.currentData()
        org_name = self._org_combo.currentText()
        if not org_id or not self._client:
            return
        # Bump token so a second rapid click discards the first load's result
        self._session_token += 1
        self._current_org_id = org_id
        self._current_org_name = org_name
        self._load_nets_btn.setEnabled(False)
        self.networks_changed.emit([])  # clear panels immediately before new data arrives
        self.run_worker(
            lambda: self._client.networks(org_id),
            on_result=self._on_networks,
            on_finished=lambda: self._load_nets_btn.setEnabled(True),
            status_msg=f"Loading networks for {org_name}…",
        )

    def _new_session(self) -> None:
        """Disconnect and reconnect with a new API key (or reload .env in dev mode)."""
        # Client build (no .env): show the API key dialog again
        if not self._show_credits:
            from main_client import LoginDialog
            dlg = LoginDialog(self)
            if dlg.exec() != dlg.DialogCode.Accepted:
                return
            new_key = dlg.authenticated_key()
            if not new_key:
                return
            self._settings = Settings(
                api_key=new_key,
                max_retries=self._settings.max_retries,
                retry_base_seconds=self._settings.retry_base_seconds,
                early_access=self._settings.early_access,
            )
        else:
            answer = QMessageBox.question(
                self,
                "New Session",
                "Start a new session?\n\n"
                "All current state will be cleared and the app will reconnect "
                "to the Meraki Dashboard.\n\n"
                "If you updated your API key in .env, changes will take effect now.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                self._settings = Settings.load()
            except Exception:
                pass

        self._session_token += 1
        self._client = None
        self._workflow = None
        self._copy_service = None
        self._network_service = None
        self._organizations = []
        self._networks = []
        self._current_org_id = None
        self._current_org_name = ""
        self._org_combo.blockSignals(True)
        self._org_combo.clear()
        self._org_combo.setEnabled(False)
        self._org_combo.blockSignals(False)
        self._load_nets_btn.setEnabled(False)
        self._conn_label.setText("Reconnecting…")
        self._conn_label.setObjectName("conn-pending")
        self._conn_label.setStyleSheet("")
        self._sidebar_conn.setText("⬤  Connecting…")
        self.networks_changed.emit([])
        self.statusBar().showMessage("Starting new session…")
        self.log_activity("New session started — reconnecting.", "INFO")
        self._connect()

    def _on_networks(self, networks: list[dict]) -> None:
        self._networks = networks
        self.networks_changed.emit(networks)
        self.statusBar().showMessage(
            f"Loaded {len(networks)} MX network(s) for {self._current_org_name}"
        )
        self.log_activity(
            f"Loaded {len(networks)} network(s) for '{self._current_org_name}'.", "INFO"
        )

    def reload_networks(self) -> None:
        """Re-fetch networks for the current org — called after creating a network."""
        if self._current_org_id and self._client:
            self._load_networks()

    # ── Worker runner ──────────────────────────────────────────────────────

    def run_worker(
        self,
        func: Callable,
        on_result: Callable | None = None,
        on_error: Callable | None = None,
        on_finished: Callable | None = None,
        status_msg: str = "",
    ) -> None:
        """Run *func* in a thread pool. All callbacks execute on the GUI thread.

        Uses _Dispatcher (a QObject living in the GUI thread) so that Qt's
        AutoConnection delivers every callback on the GUI thread — preventing
        the silent C++ segfaults that occur when plain lambdas are called
        directly from worker threads.

        on_result is still guarded by _session_token so stale results from a
        previous org or session are silently discarded.
        """
        token = self._session_token
        if status_msg:
            self.statusBar().showMessage(status_msg)

        worker = Worker(func)
        self._active_workers.add(worker)

        def _result_cb(value: object) -> None:
            if self._session_token == token and on_result:
                on_result(value)

        def _error_cb(msg: str) -> None:
            (on_error or self._default_error)(msg)

        def _finished_cb() -> None:
            self._active_workers.discard(worker)
            if self._session_token == token:
                self.statusBar().showMessage("Ready")
            if on_finished:
                on_finished()

        dispatcher = _Dispatcher(
            result_cb=_result_cb if on_result else None,
            error_cb=_error_cb,
            finished_cb=_finished_cb,
            parent=self,          # lives in the GUI thread
        )
        from PySide6.QtCore import Qt as _Qt
        worker.signals.result.connect(dispatcher.on_result,   _Qt.ConnectionType.QueuedConnection)
        worker.signals.error.connect(dispatcher.on_error,     _Qt.ConnectionType.QueuedConnection)
        worker.signals.finished.connect(dispatcher.on_finished, _Qt.ConnectionType.QueuedConnection)
        self._pool.start(worker)

    def _default_error(self, msg: str) -> None:
        last_line = msg.splitlines()[-1] if "\n" in msg else msg
        self.log_activity(last_line, "ERROR")
        self._logger.error(msg)
        QMessageBox.critical(self, "Operation Failed", last_line)

    # ── Activity log ────────────────────────────────────────────────────────

    def log_activity(self, message: str, level: str = "INFO") -> None:
        self._activity_log.append(message, level)

    # ── Error dialog helper ─────────────────────────────────────────────────

    def show_error(self, title: str, message: str) -> None:
        self.log_activity(message, "ERROR")
        QMessageBox.critical(self, title, message)

    # ── Accessors for panels ────────────────────────────────────────────────

    def get_client(self) -> MerakiVpnClientV1 | None:
        return self._client

    def get_workflow(self) -> WorkflowService | None:
        return self._workflow

    def get_copy_service(self) -> CopyService | None:
        return self._copy_service

    def get_network_service(self) -> NetworkService | None:
        return self._network_service

    def get_compare_service(self) -> CompareNetworksService | None:
        return self._compare_service

    def get_org_id(self) -> str | None:
        return self._current_org_id

    def get_org_name(self) -> str:
        return self._current_org_name

    def get_networks(self) -> list[dict]:
        return self._networks
