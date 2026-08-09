"""Compare Networks panel — diff source vs. targets across three config categories."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.compare_service import CompareReport, CompareRow

if TYPE_CHECKING:
    from gui.v1.main_window_v1 import MainWindowV1

# Colour map for cell status
_COLOURS: dict[str, tuple[str, str]] = {
    "match":     ("#dcfce7", "#166534"),   # bg, fg
    "missing":   ("#fee2e2", "#991b1b"),
    "different": ("#fef3c7", "#92400e"),
    "na":        ("#f1f5f9", "#94a3b8"),
}


def _coloured_item(text: str, status: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    bg, fg = _COLOURS.get(status, ("#ffffff", "#0f172a"))
    item.setBackground(QColor(bg))
    item.setForeground(QColor(fg))
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


class ComparePanel(QWidget):
    """Pick a source network, pick targets, run comparison, view diff by category."""

    _progress = Signal(str)  # thread-safe progress updates → GUI thread

    def __init__(self, app: "MainWindowV1", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app = app
        self._networks: list[dict[str, Any]] = []
        self._report: CompareReport | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────────
        title = QLabel("Compare Networks")
        title.setObjectName("section-title")
        sub = QLabel(
            "Select a source network and one or more targets to compare. "
            "Results show what differs across VPN Exclusion Rules, SSIDs and Basic Settings."
        )
        sub.setObjectName("section-sub")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        # ── Selector pane (source | targets) ──────────────────────────────
        sel_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Source
        src_w = QWidget()
        src_lay = QVBoxLayout(src_w)
        src_lay.setContentsMargins(0, 0, 0, 0)
        src_lay.setSpacing(6)
        src_lay.addWidget(self._make_label("Source Network"))
        self._src_search = QLineEdit()
        self._src_search.setObjectName("search")
        self._src_search.setPlaceholderText("🔍  Search…")
        self._src_search.textChanged.connect(self._filter_src)
        self._src_list = QListWidget()
        self._src_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._src_list.itemChanged.connect(self._on_src_item_changed)
        self._src_status = QLabel("")
        self._src_status.setObjectName("section-sub")
        src_lay.addWidget(self._src_search)
        src_lay.addWidget(self._src_list)
        src_lay.addWidget(self._src_status)
        sel_splitter.addWidget(src_w)

        # Targets
        tgt_w = QWidget()
        tgt_lay = QVBoxLayout(tgt_w)
        tgt_lay.setContentsMargins(0, 0, 0, 0)
        tgt_lay.setSpacing(6)
        tgt_hdr = QHBoxLayout()
        tgt_hdr.addWidget(self._make_label("Compare Against"))
        sel_all = QPushButton("All")
        sel_all.setFixedWidth(44)
        sel_all.clicked.connect(lambda: self._check_targets(True))
        clr = QPushButton("None")
        clr.setFixedWidth(44)
        clr.clicked.connect(lambda: self._check_targets(False))
        tgt_hdr.addStretch()
        tgt_hdr.addWidget(sel_all)
        tgt_hdr.addWidget(clr)
        tgt_lay.addLayout(tgt_hdr)
        self._tgt_search = QLineEdit()
        self._tgt_search.setObjectName("search")
        self._tgt_search.setPlaceholderText("🔍  Search…")
        self._tgt_search.textChanged.connect(self._filter_tgt)
        self._tgt_list = QListWidget()
        self._tgt_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._tgt_list.itemChanged.connect(lambda _: self._gate_compare())
        tgt_lay.addWidget(self._tgt_search)
        tgt_lay.addWidget(self._tgt_list)
        sel_splitter.addWidget(tgt_w)
        sel_splitter.setSizes([400, 400])
        root.addWidget(sel_splitter)

        # ── Compare buttons + status ───────────────────────────────────────
        btn_row = QHBoxLayout()
        self._compare_btn = QPushButton("🔍  Run Comparison")
        self._compare_btn.setObjectName("primary")
        self._compare_btn.setEnabled(False)
        self._compare_btn.clicked.connect(self._run_compare)

        self._compare_all_btn = QPushButton("🌐  Compare with All Networks")
        self._compare_all_btn.setEnabled(False)
        self._compare_all_btn.clicked.connect(self._run_compare_all)

        self._export_pdf_btn = QPushButton("📄  Export PDF")
        self._export_pdf_btn.setEnabled(False)
        self._export_pdf_btn.clicked.connect(self._export_pdf)

        self._run_status = QLabel("Select a source and at least one target, then click Run Comparison.")
        self._run_status.setObjectName("section-sub")
        self._progress.connect(self._run_status.setText)

        btn_row.addWidget(self._compare_btn)
        btn_row.addWidget(self._compare_all_btn)
        btn_row.addWidget(self._export_pdf_btn)
        btn_row.addWidget(self._run_status)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # ── Summary card ───────────────────────────────────────────────────
        self._summary_frame = QFrame()
        self._summary_frame.setObjectName("card")
        self._summary_frame.setVisible(False)
        sum_lay = QHBoxLayout(self._summary_frame)
        sum_lay.setContentsMargins(16, 10, 16, 10)
        sum_lay.setSpacing(24)
        self._sum_networks = self._make_stat("—", "Networks Compared")
        self._sum_rule_diff = self._make_stat("—", "VPN Rule Differences")
        self._sum_ssid_diff = self._make_stat("—", "SSID Differences")
        self._sum_settings_diff = self._make_stat("—", "Setting Differences")
        for w in (self._sum_networks, self._sum_rule_diff,
                  self._sum_ssid_diff, self._sum_settings_diff):
            sum_lay.addWidget(w)
        sum_lay.addStretch()
        root.addWidget(self._summary_frame)

        # ── Results tabs ───────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tab_rules = self._make_results_tab("VPN Exclusion Rules")
        self._tab_ssids = self._make_results_tab("SSIDs")
        self._tab_settings = self._make_results_tab("Basic Settings")
        self._tabs.addTab(self._tab_rules[0], "VPN Exclusion Rules")
        self._tabs.addTab(self._tab_ssids[0], "SSIDs")
        self._tabs.addTab(self._tab_settings[0], "Basic Settings")
        root.addWidget(self._tabs, 1)

        # ── Legend ─────────────────────────────────────────────────────────
        legend = QHBoxLayout()
        for label, colour in [("✓ Match", "#dcfce7"), ("✗ Missing", "#fee2e2"),
                               ("⚠ Different", "#fef3c7"), ("— N/A", "#f1f5f9")]:
            badge = QLabel(f"  {label}  ")
            badge.setStyleSheet(
                f"background-color:{colour};border-radius:4px;padding:2px 6px;font-size:11px;"
            )
            legend.addWidget(badge)
        legend.addStretch()
        root.addLayout(legend)

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _make_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("label")
        return lbl

    @staticmethod
    def _make_stat(value: str, subtitle: str) -> QWidget:
        """Small stat widget used in the summary card."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        val_lbl = QLabel(value)
        val_lbl.setObjectName("card-value")
        val_lbl.setStyleSheet("font-size:22px;font-weight:700;color:#0f172a;")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setObjectName("card-sub")
        lay.addWidget(val_lbl)
        lay.addWidget(sub_lbl)
        w._val_lbl = val_lbl  # type: ignore[attr-defined]
        return w

    @staticmethod
    def _make_results_tab(title: str) -> tuple[QWidget, QTableWidget]:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Source", title])
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        lay.addWidget(table)
        return w, table

    def _results_table(self, tab_idx: int) -> QTableWidget:
        return [self._tab_rules[1], self._tab_ssids[1], self._tab_settings[1]][tab_idx]

    # ── Data refresh ───────────────────────────────────────────────────────

    def refresh(self, networks: list[dict[str, Any]]) -> None:
        self._networks = networks
        self._populate_lists()
        self._gate_compare()
        self._compare_all_btn.setEnabled(bool(networks))

    def _populate_lists(self) -> None:
        self._src_search.clear()
        self._tgt_search.clear()
        src_id = self._selected_src_id()

        self._src_list.blockSignals(True)
        self._tgt_list.blockSignals(True)

        self._src_list.clear()
        self._tgt_list.clear()
        for net in self._networks:
            # source list (radio-style: only one checked at a time)
            s_item = QListWidgetItem(net["name"])
            s_item.setData(Qt.ItemDataRole.UserRole, net)
            s_item.setFlags(s_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            s_item.setCheckState(
                Qt.CheckState.Checked if net["id"] == src_id else Qt.CheckState.Unchecked
            )
            self._src_list.addItem(s_item)

            # target list
            t_item = QListWidgetItem(net["name"])
            t_item.setData(Qt.ItemDataRole.UserRole, net)
            t_item.setFlags(t_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            t_item.setCheckState(Qt.CheckState.Unchecked)
            self._tgt_list.addItem(t_item)

        self._src_list.blockSignals(False)
        self._tgt_list.blockSignals(False)

    def _on_src_item_changed(self, changed_item: QListWidgetItem) -> None:
        """Enforce radio-button behaviour: only one source can be checked at a time."""
        try:
            if changed_item.checkState() != Qt.CheckState.Checked:
                self._gate_compare()
                return
            self._src_list.blockSignals(True)
            for i in range(self._src_list.count()):
                item = self._src_list.item(i)
                if item is not changed_item:
                    item.setCheckState(Qt.CheckState.Unchecked)
            self._src_list.blockSignals(False)

            src = changed_item.data(Qt.ItemDataRole.UserRole)
            self._src_status.setText(f"Source: {src['name']}")
            src_id = src["id"]
            self._tgt_list.blockSignals(True)
            for i in range(self._tgt_list.count()):
                item = self._tgt_list.item(i)
                net = item.data(Qt.ItemDataRole.UserRole)
                item.setHidden(net["id"] == src_id)
                if net["id"] == src_id:
                    item.setCheckState(Qt.CheckState.Unchecked)
            self._tgt_list.blockSignals(False)
            self._gate_compare()
        except Exception as exc:
            print(f"[ComparePanel] _on_src_item_changed error: {exc}")

    # ── Filtering ──────────────────────────────────────────────────────────

    def _filter_src(self, text: str) -> None:
        q = text.lower()
        for i in range(self._src_list.count()):
            item = self._src_list.item(i)
            item.setHidden(bool(q) and q not in item.data(Qt.ItemDataRole.UserRole)["name"].lower())

    def _filter_tgt(self, text: str) -> None:
        src_id = self._selected_src_id()
        q = text.lower()
        for i in range(self._tgt_list.count()):
            item = self._tgt_list.item(i)
            net = item.data(Qt.ItemDataRole.UserRole)
            hide = net["id"] == src_id or (bool(q) and q not in net["name"].lower())
            item.setHidden(hide)

    def _check_targets(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._tgt_list.blockSignals(True)
        for i in range(self._tgt_list.count()):
            item = self._tgt_list.item(i)
            if not item.isHidden():
                item.setCheckState(state)
        self._tgt_list.blockSignals(False)
        self._gate_compare()

    # ── Selection helpers ──────────────────────────────────────────────────

    def _selected_src(self) -> dict[str, Any] | None:
        for i in range(self._src_list.count()):
            item = self._src_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _selected_src_id(self) -> str | None:
        src = self._selected_src()
        return src["id"] if src else None

    def _selected_targets(self) -> list[dict[str, Any]]:
        return [
            self._tgt_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._tgt_list.count())
            if not self._tgt_list.item(i).isHidden()
            and self._tgt_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _gate_compare(self) -> None:
        ok = bool(self._selected_src()) and bool(self._selected_targets())
        self._compare_btn.setEnabled(ok)

    # ── Comparison run ─────────────────────────────────────────────────────

    def _run_compare_all(self) -> None:
        """Select all target networks then run comparison immediately."""
        if not self._selected_src():
            return
        self._check_targets(True)
        self._run_compare()

    def _run_compare(self) -> None:
        src = self._selected_src()
        targets = self._selected_targets()
        org_id = self._app.get_org_id()
        cmp_svc = self._app.get_compare_service()
        if not src or not targets or not org_id or not cmp_svc:
            return
        self._compare_btn.setEnabled(False)
        self._compare_all_btn.setEnabled(False)
        self._export_pdf_btn.setEnabled(False)
        self._run_status.setText(f"Comparing against {len(targets)} network(s)…")
        self._app.run_worker(
            lambda: cmp_svc.compare(org_id, src, targets, progress=self._progress.emit),
            on_result=self._on_report,
            on_finished=lambda: (
                self._compare_btn.setEnabled(bool(self._selected_src()) and bool(self._selected_targets())),
                self._compare_all_btn.setEnabled(bool(self._networks)),
            ),
            status_msg="Running comparison…",
        )

    def _on_report(self, report: CompareReport) -> None:
        self._report = report
        targets = report.target_networks
        n = len(targets)

        # Count differences across all targets
        rule_diffs = sum(
            1 for row in report.vpn_rules
            for cell in row.cells.values()
            if cell.status in ("missing", "different")
        )
        ssid_diffs = sum(
            1 for row in report.ssids
            for cell in row.cells.values()
            if cell.status in ("missing", "different")
        )
        settings_diffs = sum(
            1 for row in report.settings
            for cell in row.cells.values()
            if cell.status in ("missing", "different")
        )

        # Update summary card
        self._sum_networks._val_lbl.setText(str(n))
        self._sum_rule_diff._val_lbl.setText(str(rule_diffs))
        self._sum_ssid_diff._val_lbl.setText(str(ssid_diffs))
        self._sum_settings_diff._val_lbl.setText(str(settings_diffs))
        self._summary_frame.setVisible(True)

        self._run_status.setText(
            f"Complete — {len(report.vpn_rules)} VPN rule(s), "
            f"{len(report.ssids)} SSID(s), {len(report.settings)} setting(s) "
            f"vs {n} network(s)"
        )
        self._fill_table(self._tab_rules[1], report.vpn_rules, targets)
        self._fill_table(self._tab_ssids[1], report.ssids, targets)
        self._fill_table(self._tab_settings[1], report.settings, targets)
        self._export_pdf_btn.setEnabled(True)
        self._app.log_activity(
            f"Compare complete: source='{report.source_network['name']}', "
            f"{n} target(s) | {rule_diffs} rule diff(s), {ssid_diffs} SSID diff(s).",
            "INFO",
        )

    @staticmethod
    def _fill_table(table: QTableWidget, rows: list[CompareRow], targets: list[dict]) -> None:
        """Rebuild a results table with one column per target network."""
        table.clear()
        target_names = [t["name"] for t in targets]
        table.setColumnCount(2 + len(targets))
        table.setHorizontalHeaderLabels(["Item", "Source"] + target_names)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for col in range(2, 2 + len(targets)):
            table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)

        if not rows:
            table.setRowCount(1)
            na = QTableWidgetItem("No data available for this category")
            na.setFlags(na.flags() & ~Qt.ItemFlag.ItemIsEditable)
            na.setForeground(QColor("#94a3b8"))
            table.setItem(0, 0, na)
            return

        table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            lbl_item = QTableWidgetItem(row.label)
            lbl_item.setFlags(lbl_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(r_idx, 0, lbl_item)
            src_item = QTableWidgetItem(row.source_display)
            src_item.setFlags(src_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(r_idx, 1, src_item)
            for c_idx, target in enumerate(targets):
                cell = row.cells.get(target["id"])
                if cell is None:
                    table.setItem(r_idx, 2 + c_idx, _coloured_item("—", "na"))
                    continue
                icons = {"match": "✓", "missing": "✗ Missing", "different": "⚠", "na": "—"}
                text = icons.get(cell.status, "?")
                if cell.status == "different" and cell.detail:
                    text = f"⚠ {cell.detail}"
                item = _coloured_item(text, cell.status)
                item.setToolTip(cell.detail)
                table.setItem(r_idx, 2 + c_idx, item)

    # ── PDF export ─────────────────────────────────────────────────────────

    def _export_pdf(self) -> None:
        if not self._report:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Comparison Report",
            f"meraki_comparison_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            "PDF files (*.pdf)",
        )
        if not path:
            return
        html = self._build_report_html(self._report)
        doc = QTextDocument()
        doc.setHtml(html)
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        layout = QPageLayout()
        layout.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageLayout(layout)
        doc.print_(writer)
        self._app.log_activity(f"PDF report saved: {path}", "SUCCESS")

    @staticmethod
    def _build_report_html(report: CompareReport) -> str:
        targets = report.target_networks
        src_name = report.source_network.get("name", "—")
        generated = datetime.now().strftime("%Y-%m-%d %H:%M")

        rule_diffs = sum(
            1 for row in report.vpn_rules
            for cell in row.cells.values()
            if cell.status in ("missing", "different")
        )
        ssid_diffs = sum(
            1 for row in report.ssids
            for cell in row.cells.values()
            if cell.status in ("missing", "different")
        )
        settings_diffs = sum(
            1 for row in report.settings
            for cell in row.cells.values()
            if cell.status in ("missing", "different")
        )

        css = """
        body{font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#0f172a;margin:0;padding:0}
        h1{font-size:18px;color:#1e293b;margin-bottom:4px}
        h2{font-size:13px;color:#334155;margin:16px 0 6px 0;border-bottom:1px solid #e2e8f0;padding-bottom:4px}
        .meta{font-size:10px;color:#64748b;margin-bottom:12px}
        .summary{display:flex;gap:24px;background:#f8fafc;border:1px solid #e2e8f0;
                  border-radius:6px;padding:12px;margin-bottom:16px}
        .stat{text-align:center}
        .stat-val{font-size:22px;font-weight:700;color:#0f172a}
        .stat-lbl{font-size:10px;color:#64748b}
        table{width:100%;border-collapse:collapse;margin-bottom:16px;font-size:10px}
        th{background:#1e293b;color:#f1f5f9;padding:5px 7px;text-align:left;font-size:10px}
        td{padding:4px 7px;border-bottom:1px solid #f1f5f9;vertical-align:top}
        .match{background:#dcfce7;color:#166534}
        .missing{background:#fee2e2;color:#991b1b}
        .different{background:#fef3c7;color:#92400e}
        .na{background:#f1f5f9;color:#94a3b8}
        .footer{font-size:9px;color:#94a3b8;margin-top:24px;text-align:center}
        """

        def _cell_html(status: str, text: str) -> str:
            cls = {"match": "match", "missing": "missing",
                   "different": "different", "na": "na"}.get(status, "")
            return f'<td class="{cls}">{text}</td>'

        def _table_html(title: str, rows: list[CompareRow]) -> str:
            if not rows:
                return f"<h2>{title}</h2><p style='color:#94a3b8;font-size:10px'>No data available.</p>"
            heads = "".join(f"<th>{t['name']}</th>" for t in targets)
            html = f"<h2>{title}</h2><table><tr><th>Item</th><th>Source</th>{heads}</tr>"
            for row in rows:
                html += f"<tr><td>{row.label}</td><td>{row.source_display}</td>"
                for target in targets:
                    cell = row.cells.get(target["id"])
                    if cell is None:
                        html += '<td class="na">—</td>'
                    else:
                        icons = {"match": "✓", "missing": "✗ Missing",
                                 "different": "⚠", "na": "—"}
                        txt = icons.get(cell.status, "?")
                        if cell.status == "different" and cell.detail:
                            txt = f"⚠ {cell.detail}"
                        html += _cell_html(cell.status, txt)
                html += "</tr>"
            html += "</table>"
            return html

        target_names = ", ".join(t["name"] for t in targets)

        html = f"""<html><head><style>{css}</style></head><body>
        <h1>Meraki Config Tool — Network Comparison Report</h1>
        <div class="meta">
            Source: <b>{src_name}</b> &nbsp;|&nbsp;
            Targets: <b>{target_names}</b> &nbsp;|&nbsp;
            Generated: {generated}
        </div>
        <div class="summary">
            <div class="stat"><div class="stat-val">{len(targets)}</div>
                <div class="stat-lbl">Networks Compared</div></div>
            <div class="stat"><div class="stat-val">{rule_diffs}</div>
                <div class="stat-lbl">VPN Rule Differences</div></div>
            <div class="stat"><div class="stat-val">{ssid_diffs}</div>
                <div class="stat-lbl">SSID Differences</div></div>
            <div class="stat"><div class="stat-val">{settings_diffs}</div>
                <div class="stat-lbl">Setting Differences</div></div>
        </div>
        {_table_html("VPN Exclusion Rules", report.vpn_rules)}
        {_table_html("SSIDs", report.ssids)}
        {_table_html("Basic Settings", report.settings)}
        <div class="footer">Generated by Meraki Config Tool &nbsp;·&nbsp;
            Created by Shay Iqbal, Technical Leader CX, Cisco</div>
        </body></html>"""
        return html
