"""VPN Exclusions panel — view, edit, dry-run and deploy for a single network."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.v1.dialogs.rule_editor_v1 import RuleEditorV1
from rules.comparer import compare
from rules.models import ChangeKind, RuleSet, VpnExclusionRule
from rules.parser import ImportValidationError, parse_file
from services.workflow import DryRun

if TYPE_CHECKING:
    from gui.v1.main_window_v1 import MainWindowV1


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    return line


class ExclusionsPanel(QWidget):
    """Manage VPN exclusion rules for one network at a time.

    Workflow:
      1. Pick a network from the combo.
      2. Load its current rules.
      3. Build proposed changes (import a file or add manually).
      4. Run a mandatory dry run.
      5. Review the diff and deploy.
    """

    def __init__(self, app: "MainWindowV1", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app = app
        self._networks: list[dict[str, Any]] = []
        self._proposed = RuleSet()
        self._dry_runs: list[DryRun] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(12)

        # ── Network selector ──────────────────────────────────────────────
        title = QLabel("Local Breakouts")
        title.setObjectName("section-title")
        sub = QLabel(
            "Select a network, load its current rules, then propose and deploy changes."
        )
        sub.setObjectName("section-sub")
        root.addWidget(title)
        root.addWidget(sub)

        sel_row = QHBoxLayout()
        sel_row.setSpacing(8)
        net_label = QLabel("Network")
        net_label.setObjectName("label")
        net_label.setFixedWidth(60)
        self._net_combo = QComboBox()
        self._net_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._net_combo.setPlaceholderText("Choose a network…")
        self._load_btn = QPushButton("Load Current Rules")
        self._load_btn.setObjectName("primary")
        self._load_btn.setEnabled(False)
        self._load_btn.clicked.connect(self._load_current)
        sel_row.addWidget(net_label)
        sel_row.addWidget(self._net_combo)
        sel_row.addWidget(self._load_btn)
        root.addLayout(sel_row)

        root.addWidget(_separator())

        # ── Current rules ─────────────────────────────────────────────────
        current_hdr = QHBoxLayout()
        current_hdr.addWidget(QLabel("Current Rules"))
        self._current_count = QLabel("Not loaded")
        self._current_count.setObjectName("section-sub")
        current_hdr.addStretch()
        current_hdr.addWidget(self._current_count)
        root.addLayout(current_hdr)
        self._current_table = self._make_table()
        self._current_table.setMaximumHeight(180)
        root.addWidget(self._current_table)

        root.addWidget(_separator())

        # ── Proposed changes ──────────────────────────────────────────────
        proposed_hdr = QHBoxLayout()
        proposed_hdr.addWidget(QLabel("Proposed Changes"))
        self._proposed_count = QLabel("No rules queued")
        self._proposed_count.setObjectName("section-sub")
        proposed_hdr.addStretch()
        proposed_hdr.addWidget(self._proposed_count)
        root.addLayout(proposed_hdr)

        propose_btns = QHBoxLayout()
        propose_btns.setSpacing(8)
        import_btn = QPushButton("Import File…")
        import_btn.clicked.connect(self._import_file)
        add_btn = QPushButton("+ Add Rule")
        add_btn.clicked.connect(self._add_rule)
        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self._edit_rule)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_rule)
        self._clear_proposed_btn = QPushButton("Clear All")
        self._clear_proposed_btn.setObjectName("danger")
        self._clear_proposed_btn.clicked.connect(self._clear_proposed)
        for btn in (import_btn, add_btn, edit_btn, remove_btn, self._clear_proposed_btn):
            propose_btns.addWidget(btn)
        propose_btns.addStretch()
        root.addLayout(propose_btns)

        self._proposed_table = self._make_table()
        self._proposed_table.setMaximumHeight(160)
        root.addWidget(self._proposed_table)

        root.addWidget(_separator())

        # ── Dry run ───────────────────────────────────────────────────────
        dry_hdr = QHBoxLayout()
        self._dry_btn = QPushButton("Run Dry Run")
        self._dry_btn.clicked.connect(self._run_dry)
        dry_hdr.addWidget(self._dry_btn)
        dry_hdr.addStretch()
        root.addLayout(dry_hdr)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(130)
        self._preview.setPlaceholderText("Dry-run diff will appear here…")
        root.addWidget(self._preview)

        # ── Deploy ────────────────────────────────────────────────────────
        deploy_row = QHBoxLayout()
        self._reviewed = QCheckBox("I have reviewed the dry-run output above")
        self._reviewed.stateChanged.connect(self._gate_deploy)
        self._deploy_btn = QPushButton("Deploy")
        self._deploy_btn.setObjectName("success")
        self._deploy_btn.setEnabled(False)
        self._deploy_btn.clicked.connect(self._deploy)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        deploy_row.addWidget(self._reviewed)
        deploy_row.addStretch()
        deploy_row.addWidget(self._progress)
        deploy_row.addWidget(self._deploy_btn)
        root.addLayout(deploy_row)

    # ── Called by main window ──────────────────────────────────────────────

    def refresh(self, networks: list[dict[str, Any]]) -> None:
        self._networks = networks
        selected_id = self._net_combo.currentData()
        self._net_combo.blockSignals(True)
        self._net_combo.clear()
        for net in networks:
            self._net_combo.addItem(net["name"], net["id"])
        self._net_combo.blockSignals(False)
        # Restore previous selection if still valid
        if selected_id:
            idx = self._net_combo.findData(selected_id)
            if idx >= 0:
                self._net_combo.setCurrentIndex(idx)
        self._load_btn.setEnabled(bool(networks))

    def pre_select_network(self, network: dict[str, Any]) -> None:
        """Navigate from another panel with a specific network already chosen."""
        idx = self._net_combo.findData(network["id"])
        if idx >= 0:
            self._net_combo.setCurrentIndex(idx)
        self._load_current()

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _make_table() -> QTableWidget:
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(
            ["Order", "Type", "Protocol", "Destination / Application", "Port", "ID"]
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table

    @staticmethod
    def _fill_table(table: QTableWidget, rules: list[VpnExclusionRule]) -> None:
        table.setRowCount(0)
        for rule in sorted(rules, key=lambda r: r.order):
            row = table.rowCount()
            table.insertRow(row)
            values = [
                rule.order,
                rule.category.value,
                rule.protocol,
                rule.destination or rule.name or "",
                rule.port,
                rule.application_id or "",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setData(256, rule)  # stash rule in UserRole
                table.setItem(row, col, item)

    def _load_current(self) -> None:
        net_id = self._net_combo.currentData()
        net_name = self._net_combo.currentText()
        if not net_id or not self._app.get_client():
            return
        self._load_btn.setEnabled(False)
        self._app.run_worker(
            lambda: self._app.get_client().get_rules(self._app.get_org_id(), net_id),
            on_result=lambda rs: self._on_current(rs, net_name),
            on_finished=lambda: self._load_btn.setEnabled(True),
            status_msg=f"Loading exclusions for {net_name}…",
        )

    def _on_current(self, ruleset: RuleSet, net_name: str) -> None:
        self._fill_table(self._current_table, ruleset.rules)
        self._current_count.setText(f"{len(ruleset.rules)} rule(s) in {net_name}")
        # Reset proposed and dry state when loading a fresh network
        self._proposed = RuleSet()
        self._dry_runs = []
        self._fill_table(self._proposed_table, [])
        self._proposed_count.setText("No rules queued")
        self._preview.clear()
        self._reviewed.setChecked(False)
        self._gate_deploy()
        self._app.log_activity(
            f"Loaded {len(ruleset.rules)} exclusion rule(s) for {net_name}", "INFO"
        )

    def _import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import VPN Exclusion Rules",
            "",
            "Rule files (*.csv *.json *.txt *.xlsx)",
        )
        if not path:
            return
        try:
            self._proposed = parse_file(Path(path))
            self._refresh_proposed()
            self._dry_runs = []
            self._reviewed.setChecked(False)
            self._app.log_activity(
                f"Imported {len(self._proposed.rules)} rule(s) from {Path(path).name}", "INFO"
            )
        except ImportValidationError as exc:
            self._app.show_error("Import failed", str(exc))
        except Exception as exc:
            self._app.show_error("Import failed", str(exc))

    def _add_rule(self) -> None:
        dialog = RuleEditorV1(parent=self)
        if dialog.exec():
            self._proposed.rules.append(dialog.rule())
            self._refresh_proposed()

    def _edit_rule(self) -> None:
        row = self._selected_proposed_row()
        if row < 0:
            return
        rule = self._proposed_table.item(row, 0).data(256)
        dialog = RuleEditorV1(rule=rule, parent=self)
        if dialog.exec():
            self._proposed.rules[row] = dialog.rule()
            self._refresh_proposed()

    def _remove_rule(self) -> None:
        row = self._selected_proposed_row()
        if row < 0:
            return
        del self._proposed.rules[row]
        self._refresh_proposed()

    def _clear_proposed(self) -> None:
        if not self._proposed.rules:
            return
        if QMessageBox.question(
            self, "Clear All", "Remove all proposed rules?"
        ) == QMessageBox.StandardButton.Yes:
            self._proposed = RuleSet()
            self._refresh_proposed()

    def _selected_proposed_row(self) -> int:
        rows = self._proposed_table.selectedItems()
        return rows[0].row() if rows else -1

    def _refresh_proposed(self) -> None:
        self._fill_table(self._proposed_table, self._proposed.rules)
        counts = {"custom": 0, "majorApplications": 0, "applications": 0}
        for rule in self._proposed.rules:
            counts[rule.category.value] += 1
        self._proposed_count.setText(
            f"{len(self._proposed.rules)} rule(s)  —  "
            f"{counts['custom']} custom, {counts['majorApplications']} major app, "
            f"{counts['applications']} NBAR  •  mode: {self._proposed.mode}"
        )

    def _run_dry(self) -> None:
        net_id = self._net_combo.currentData()
        net_name = self._net_combo.currentText()
        if not net_id or not self._proposed.rules:
            QMessageBox.warning(
                self,
                "Nothing to Dry Run",
                "Load a network and add at least one proposed rule first.",
            )
            return
        org_id = self._app.get_org_id()
        wf = self._app.get_workflow()
        self._dry_btn.setEnabled(False)
        self._app.run_worker(
            lambda: wf.dry_run(org_id, [{"id": net_id, "name": net_name}], self._proposed),
            on_result=self._on_dry,
            on_finished=lambda: self._dry_btn.setEnabled(True),
            status_msg="Running dry run…",
        )

    def _on_dry(self, dry_runs: list[DryRun]) -> None:
        self._dry_runs = dry_runs
        lines: list[str] = []
        for run in dry_runs:
            lines.append(f"Network: {run.network_name}  —  {run.change_count} change(s)\n")
            for kind in ChangeKind:
                count = run.comparison.count(kind)
                if count:
                    lines.append(f"  {kind.value.capitalize()}: {count}")
            lines.append("")
            lines.append("Final payload:\n" + json.dumps(run.comparison.final.payload(), indent=2))
        self._preview.setPlainText("\n".join(lines))
        self._reviewed.setChecked(False)
        self._gate_deploy()
        self._app.log_activity("Dry run complete.", "SUCCESS")

    def _gate_deploy(self) -> None:
        safe = (
            bool(self._dry_runs)
            and all(not r.comparison.has_blockers for r in self._dry_runs)
        )
        self._deploy_btn.setEnabled(safe and self._reviewed.isChecked())

    def _deploy(self) -> None:
        net_name = self._net_combo.currentText()
        changes = sum(r.change_count for r in self._dry_runs)
        answer = QMessageBox.question(
            self,
            "Confirm Deploy",
            f"Deploy {changes} change(s) to '{net_name}'?\n\n"
            "This will overwrite the VPN exclusion arrays shown in the preview.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._deploy_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        wf = self._app.get_workflow()

        def _do() -> dict:
            result = wf.deploy(self._dry_runs[0])
            return result

        def _done(result: dict) -> None:
            self._progress.setValue(100)
            self._app.log_activity(
                f"Deployed successfully to '{net_name}'.", "SUCCESS"
            )
            QMessageBox.information(
                self, "Deployed", f"VPN exclusions updated on '{net_name}'."
            )
            self._load_current()

        def _fail(msg: str) -> None:
            self._progress.setVisible(False)
            self._deploy_btn.setEnabled(True)
            self._app.show_error(
                "Deploy failed",
                f"Failed to update '{net_name}'.\n\n{msg.splitlines()[-1]}",
            )
            self._app.log_activity(f"Deploy failed for '{net_name}'.", "ERROR")

        self._app.run_worker(
            _do, on_result=_done, on_error=_fail, status_msg=f"Deploying to {net_name}…"
        )
