"""Networks panel — view and manage all loaded MX networks."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from gui.v1.main_window_v1 import MainWindowV1


class NetworksPanel(QWidget):
    """Displays all loaded networks with exclusion counts and quick-action buttons."""

    def __init__(self, app: "MainWindowV1", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app = app
        self._networks: list[dict[str, Any]] = []
        self._exclusion_counts: dict[str, int] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(14)

        # ── Header ────────────────────────────────────────────────────────
        title = QLabel("Networks")
        title.setObjectName("section-title")
        sub = QLabel(
            "All MX networks in the selected organization. "
            "Select a network below to manage its VPN exclusions or clone it."
        )
        sub.setObjectName("section-sub")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        # ── Toolbar ───────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._search = QLineEdit()
        self._search.setObjectName("search")
        self._search.setPlaceholderText("Search networks…")
        self._search.setFixedWidth(260)
        self._search.textChanged.connect(self._filter)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._load_counts)
        self._view_excl_btn = QPushButton("Manage Exclusions")
        self._view_excl_btn.setObjectName("primary")
        self._view_excl_btn.setEnabled(False)
        self._view_excl_btn.clicked.connect(self._go_exclusions)
        self._clone_btn = QPushButton("Clone Network…")
        self._clone_btn.setEnabled(False)
        self._clone_btn.clicked.connect(self._go_clone)

        toolbar.addWidget(self._search)
        toolbar.addStretch()
        toolbar.addWidget(self._refresh_btn)
        toolbar.addWidget(self._view_excl_btn)
        toolbar.addWidget(self._clone_btn)
        root.addLayout(toolbar)

        # ── Table ─────────────────────────────────────────────────────────
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Product Types", "Tags", "VPN Exclusions", "Network ID"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.selectionModel().selectionChanged.connect(self._on_selection)
        root.addWidget(self._table)

        # ── Status ────────────────────────────────────────────────────────
        self._status = QLabel("No networks loaded. Select an organization and load networks first.")
        self._status.setObjectName("section-sub")
        root.addWidget(self._status)

    # ── Called by main window when network list changes ────────────────────

    def refresh(self, networks: list[dict[str, Any]]) -> None:
        self._networks = networks
        self._exclusion_counts.clear()
        self._populate()
        if networks:
            self._status.setText(
                f"{len(networks)} network(s) loaded. "
                "Click 'Refresh' to load exclusion counts."
            )
        else:
            self._status.setText("No networks loaded.")

    # ── Internal ──────────────────────────────────────────────────────────

    def _populate(self, query: str = "") -> None:
        self._table.setRowCount(0)
        q = query.lower()
        for net in self._networks:
            if q and q not in net["name"].lower():
                continue
            row = self._table.rowCount()
            self._table.insertRow(row)
            name_item = QTableWidgetItem(net["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, net)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(
                row, 1, QTableWidgetItem(", ".join(net.get("productTypes") or []))
            )
            self._table.setItem(
                row, 2, QTableWidgetItem(", ".join(net.get("tags") or []))
            )
            count = self._exclusion_counts.get(net["id"])
            count_text = str(count) if count is not None else "—"
            self._table.setItem(row, 3, QTableWidgetItem(count_text))
            self._table.setItem(row, 4, QTableWidgetItem(net["id"]))

    def _filter(self, text: str) -> None:
        self._populate(query=text)

    def _on_selection(self) -> None:
        has = bool(self._table.selectedItems())
        self._view_excl_btn.setEnabled(has)
        self._clone_btn.setEnabled(has)

    def _selected_network(self) -> dict[str, Any] | None:
        rows = self._table.selectedItems()
        if not rows:
            return None
        return self._table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _go_exclusions(self) -> None:
        net = self._selected_network()
        if net:
            self._app.navigate_to("exclusions", context={"network": net})

    def _go_clone(self) -> None:
        net = self._selected_network()
        if net:
            self._app.navigate_to("new_network", context={"template": net})

    def _load_counts(self) -> None:
        client = self._app.get_client()
        org_id = self._app.get_org_id()
        networks = self._networks
        if not client or not org_id or not networks:
            return
        self._status.setText("Loading exclusion counts…")
        self._refresh_btn.setEnabled(False)
        self._app.run_worker(
            lambda: {
                net["id"]: len(client.get_rules(org_id, net["id"]).rules)
                for net in networks
            },
            on_result=self._on_counts,
            on_finished=lambda: self._refresh_btn.setEnabled(True),
            status_msg="Loading exclusion counts…",
        )

    def _on_counts(self, counts: dict[str, int]) -> None:
        self._exclusion_counts = counts
        self._populate(query=self._search.text())
        self._status.setText(
            f"{len(self._networks)} network(s)  •  "
            f"{sum(counts.values())} total VPN exclusion rule(s)"
        )
