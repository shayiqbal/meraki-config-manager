"""Main application window."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config.settings import Settings
from gui.rule_editor import RuleEditor
from gui.workers import Worker
from meraki_client.client import MerakiVpnClient
from reporting.logging_config import configure_logging
from rules.models import ChangeKind, RuleSet
from rules.parser import parse_file
from services.workflow import DryRun, WorkflowService


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.logger = configure_logging(settings.log_path)
        self.client: MerakiVpnClient | None = None
        self.workflow: WorkflowService | None = None
        self.organizations: list[dict] = []
        self.networks: list[dict] = []
        self.proposed = RuleSet()
        self.dry_runs: list[DryRun] = []
        self.pool = QThreadPool.globalInstance()
        self.active_workers: set[Worker] = set()
        self.setWindowTitle("Meraki VPN Exclusion Manager")
        self.resize(1180, 760)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self._build_connection()
        self._build_networks()
        self._build_rules()
        self._build_import()
        self._build_dry_run()
        self._build_deploy()
        self.statusBar().showMessage("Ready")
        self._connect()

    def _page(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.tabs.addTab(page, title)
        return page, layout

    def _build_connection(self) -> None:
        _, layout = self._page("1. Connection")
        self.connection_status = QLabel("Checking Meraki connection…")
        self.connection_status.setStyleSheet("font-size: 18px; padding: 24px;")
        self.retry_connection = QPushButton("Retry connection")
        self.retry_connection.clicked.connect(self._connect)
        layout.addWidget(self.connection_status)
        layout.addWidget(self.retry_connection)
        layout.addStretch()

    def _build_networks(self) -> None:
        _, layout = self._page("2. Networks")
        self.organization = QComboBox()
        self.organization.setEnabled(False)
        self.organization.currentIndexChanged.connect(self._organization_changed)
        self.load_networks_button = QPushButton("Load networks for selected organization")
        self.load_networks_button.setEnabled(False)
        self.load_networks_button.clicked.connect(self._load_networks)
        self.network_filter = QLineEdit()
        self.network_filter.setPlaceholderText("Search networks")
        self.network_filter.textChanged.connect(self._filter_networks)
        self.network_list = QListWidget()
        self.network_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        buttons = QHBoxLayout()
        select_all = QPushButton("Select all")
        clear = QPushButton("Clear")
        select_all.clicked.connect(lambda: self._check_networks(True))
        clear.clicked.connect(lambda: self._check_networks(False))
        buttons.addWidget(select_all)
        buttons.addWidget(clear)
        layout.addWidget(QLabel("Organization"))
        layout.addWidget(self.organization)
        layout.addWidget(self.load_networks_button)
        layout.addWidget(self.network_filter)
        layout.addWidget(self.network_list)
        layout.addLayout(buttons)

    def _build_rules(self) -> None:
        _, layout = self._page("3. Current Rules")
        read = QPushButton("Retrieve selected networks")
        read.clicked.connect(self._read_current)
        self.current_table = self._table()
        layout.addWidget(read)
        layout.addWidget(self.current_table)

    def _build_import(self) -> None:
        _, layout = self._page("4. Import / Edit")
        buttons = QHBoxLayout()
        import_button = QPushButton("Import CSV, JSON, TXT, or XLSX")
        import_button.clicked.connect(self._import)
        add_button = QPushButton("Add manually")
        add_button.clicked.connect(self._add_manual)
        remove_button = QPushButton("Remove selected pending rule")
        remove_button.clicked.connect(self._remove_pending)
        buttons.addWidget(import_button)
        buttons.addWidget(add_button)
        buttons.addWidget(remove_button)
        self.import_summary = QLabel("No proposed rules loaded")
        self.pending_table = self._table()
        layout.addLayout(buttons)
        layout.addWidget(self.import_summary)
        layout.addWidget(self.pending_table)

    def _build_dry_run(self) -> None:
        _, layout = self._page("5. Dry Run")
        self.dry_button = QPushButton("Run mandatory dry run")
        self.dry_button.clicked.connect(self._run_dry)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.raw_preview = QTextEdit()
        self.raw_preview.setReadOnly(True)
        self.raw_preview.setPlaceholderText("Raw final payload appears here")
        layout.addWidget(self.dry_button)
        layout.addWidget(QLabel("Human-readable preview"))
        layout.addWidget(self.preview)
        layout.addWidget(QLabel("Raw JSON preview"))
        layout.addWidget(self.raw_preview)

    def _build_deploy(self) -> None:
        _, layout = self._page("6. Deploy")
        self.reviewed = QCheckBox("I reviewed the complete dry-run preview")
        self.reviewed.stateChanged.connect(self._deployment_gate)
        self.deploy_button = QPushButton("Deploy to selected networks")
        self.deploy_button.setEnabled(False)
        self.deploy_button.clicked.connect(self._deploy)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.results = QTextEdit()
        self.results.setReadOnly(True)
        layout.addWidget(self.reviewed)
        layout.addWidget(self.deploy_button)
        layout.addWidget(self.progress)
        layout.addWidget(self.results)

    @staticmethod
    def _table() -> QTableWidget:
        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(
            ["Network", "Order", "Type", "Protocol", "Destination / Name", "Port", "ID"]
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _worker(self, function, on_result) -> None:
        worker = Worker(function)
        self.active_workers.add(worker)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(self._error)
        worker.signals.finished.connect(lambda: self.statusBar().showMessage("Ready"))
        worker.signals.finished.connect(
            lambda current=worker: self.active_workers.discard(current)
        )
        self.pool.start(worker)

    def _connect(self) -> None:
        self.statusBar().showMessage("Connecting…")
        try:
            self.settings.validate()
            self.client = MerakiVpnClient(self.settings, self.logger)
            self.workflow = WorkflowService(self.client)
        except Exception as exc:
            self.connection_status.setText(f"Connection unavailable\n{exc}")
            return
        self._worker(self.client.organizations, self._connected)

    def _connected(self, organizations: list[dict]) -> None:
        self.organizations = organizations
        self.connection_status.setText(
            f"Connected securely • {len(organizations)} organization(s) available\n"
            "Open Networks, choose one organization, then click Load networks."
        )
        self.organization.blockSignals(True)
        self.organization.clear()
        self.organization.addItem("Choose an organization…", None)
        for item in organizations:
            self.organization.addItem(item["name"], item["id"])
        self.organization.blockSignals(False)
        self.organization.setEnabled(True)
        self.load_networks_button.setEnabled(True)
        self.tabs.setCurrentIndex(1)

    def _load_networks(self) -> None:
        if not self.client:
            return
        if not self.organization.currentData():
            self._warn("Choose an organization first.")
            return
        organization_id = self.organization.currentData()
        self.load_networks_button.setEnabled(False)
        self.organization.setEnabled(False)
        self.network_list.clear()
        self.statusBar().showMessage(
            f"Loading networks for {self.organization.currentText()}…"
        )
        self._worker(lambda: self.client.networks(organization_id), self._networks_loaded)

    def _networks_loaded(self, networks: list[dict]) -> None:
        self.networks = networks
        self._filter_networks()
        self.organization.setEnabled(True)
        self.load_networks_button.setEnabled(True)
        self.statusBar().showMessage(
            f"Loaded {len(networks)} MX network(s) for "
            f"{self.organization.currentText()}"
        )

    def _organization_changed(self) -> None:
        # Changing the selection is local-only. A Dashboard request occurs only
        # after the user explicitly clicks Load networks.
        self.networks = []
        self.network_list.clear()
        self.dry_runs = []
        self.reviewed.setChecked(False)

    def _filter_networks(self) -> None:
        selected = {
            self.network_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.network_list.count())
            if self.network_list.item(i).checkState() == Qt.CheckState.Checked
        }
        query = self.network_filter.text().lower()
        self.network_list.clear()
        for network in self.networks:
            if query in network["name"].lower():
                item = QListWidgetItem(network["name"])
                item.setData(Qt.ItemDataRole.UserRole, network["id"])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if network["id"] in selected
                    else Qt.CheckState.Unchecked
                )
                self.network_list.addItem(item)

    def _check_networks(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for index in range(self.network_list.count()):
            self.network_list.item(index).setCheckState(state)

    def _selected_networks(self) -> list[dict]:
        ids = {
            self.network_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.network_list.count())
            if self.network_list.item(i).checkState() == Qt.CheckState.Checked
        }
        return [item for item in self.networks if item["id"] in ids]

    def _read_current(self) -> None:
        selected = self._selected_networks()
        if not selected or not self.client:
            self._warn("Select at least one network.")
            return
        org = self.organization.currentData()
        self._worker(
            lambda: [(n, self.client.get_rules(org, n["id"])) for n in selected],
            self._show_current,
        )

    def _show_current(self, results) -> None:
        self.current_table.setRowCount(0)
        for network, ruleset in results:
            for rule in ruleset.rules:
                self._append_rule(self.current_table, rule, network["name"])

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import VPN exclusion rules",
            "",
            "Rule files (*.csv *.json *.txt *.xlsx)",
        )
        if not path:
            return
        try:
            self.proposed = parse_file(path)
            self._refresh_pending()
            self.dry_runs = []
            self.reviewed.setChecked(False)
        except Exception as exc:
            self._error(str(exc))

    def _add_manual(self) -> None:
        dialog = RuleEditor(self)
        if dialog.exec():
            self.proposed.rules.append(dialog.rule())
            self._refresh_pending()

    def _remove_pending(self) -> None:
        rows = sorted({item.row() for item in self.pending_table.selectedItems()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self.proposed.rules):
                self.proposed.rules.pop(row)
        self._refresh_pending()

    def _refresh_pending(self) -> None:
        self.pending_table.setRowCount(0)
        for rule in sorted(self.proposed.rules, key=lambda item: item.order):
            self._append_rule(self.pending_table, rule, "")
        counts = {key: 0 for key in ("custom", "majorApplications", "applications")}
        for rule in self.proposed.rules:
            counts[rule.category.value] += 1
        self.import_summary.setText(
            f"{len(self.proposed.rules)} rule(s): {counts['custom']} custom, "
            f"{counts['majorApplications']} major application, "
            f"{counts['applications']} NBAR application • mode: {self.proposed.mode}"
        )

    @staticmethod
    def _append_rule(table: QTableWidget, rule, network: str) -> None:
        row = table.rowCount()
        table.insertRow(row)
        values = [
            network,
            rule.order,
            rule.category.value,
            rule.protocol,
            rule.destination or rule.name or "",
            rule.port,
            rule.application_id or "",
        ]
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(str(value)))

    def _run_dry(self) -> None:
        selected = self._selected_networks()
        if not selected or not self.proposed.rules or not self.workflow:
            self._warn("Select networks and load at least one proposed rule.")
            return
        org = self.organization.currentData()
        self.dry_button.setEnabled(False)
        self._worker(
            lambda: self.workflow.dry_run(org, selected, self.proposed),
            self._dry_complete,
        )

    def _dry_complete(self, dry_runs: list[DryRun]) -> None:
        self.dry_button.setEnabled(True)
        self.dry_runs = dry_runs
        lines: list[str] = []
        payloads = {}
        colors = {
            ChangeKind.NEW: "#166534",
            ChangeKind.REMOVED: "#991b1b",
            ChangeKind.INVALID: "#991b1b",
            ChangeKind.DUPLICATE: "#92400e",
        }
        for run in dry_runs:
            lines.append(f"{run.network_name} — {run.change_count} change(s)")
            for kind in ChangeKind:
                count = run.comparison.count(kind)
                if count:
                    lines.append(f"  {kind.value.title()}: {count}")
            lines.append("")
            payloads[run.network_name] = run.comparison.final.payload()
        self.preview.setPlainText("\n".join(lines))
        self.raw_preview.setPlainText(json.dumps(payloads, indent=2))
        self.reviewed.setChecked(False)
        self.tabs.setCurrentIndex(4)
        if any(run.comparison.has_blockers for run in dry_runs):
            self.preview.setTextColor(QColor(colors[ChangeKind.INVALID]))
        self._deployment_gate()

    def _deployment_gate(self) -> None:
        safe = bool(self.dry_runs) and all(not r.comparison.has_blockers for r in self.dry_runs)
        self.deploy_button.setEnabled(safe and self.reviewed.isChecked())

    def _deploy(self) -> None:
        changes = sum(run.change_count for run in self.dry_runs)
        names = "\n".join(f"• {run.network_name}" for run in self.dry_runs)
        answer = QMessageBox.question(
            self,
            "Confirm VPN exclusion deployment",
            f"Organization: {self.organization.currentText()}\n"
            f"Networks:\n{names}\n\nTotal changes: {changes}\n\n"
            "This replaces the three VPN exclusion arrays shown in the preview. Continue?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.progress.setValue(0)
        self.results.clear()
        self.deploy_button.setEnabled(False)
        self._deploy_next(0)

    def _deploy_next(self, index: int) -> None:
        if index >= len(self.dry_runs):
            self.progress.setValue(100)
            self.results.append("Deployment processing complete.")
            return
        run = self.dry_runs[index]
        worker = Worker(lambda: self.workflow.deploy(run))
        self.active_workers.add(worker)
        worker.signals.result.connect(
            lambda _: self.results.append(f"✓ {run.network_name}: updated and verified")
        )
        worker.signals.error.connect(
            lambda message: self.results.append(
                f"✗ {run.network_name}: {message.splitlines()[-1]}"
            )
        )
        worker.signals.finished.connect(
            lambda: (
                self.progress.setValue(int((index + 1) / len(self.dry_runs) * 100)),
                self._deploy_next(index + 1),
            )
        )
        worker.signals.finished.connect(
            lambda current=worker: self.active_workers.discard(current)
        )
        self.pool.start(worker)

    def _warn(self, message: str) -> None:
        QMessageBox.warning(self, "VPN Exclusion Manager", message)

    def _error(self, message: str) -> None:
        self.logger.error(message)
        self.organization.setEnabled(bool(self.organizations))
        self.load_networks_button.setEnabled(bool(self.organizations))
        QMessageBox.critical(
            self,
            "Operation failed",
            message.splitlines()[-1] if "\n" in message else message,
        )
