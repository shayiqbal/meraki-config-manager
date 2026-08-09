"""Dashboard overview panel."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from gui.v1.main_window_v1 import MainWindowV1


def _stat_card(title: str, value: str, subtitle: str) -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.setSpacing(4)
    t = QLabel(title.upper())
    t.setObjectName("card-title")
    v = QLabel(value)
    v.setObjectName("card-value")
    s = QLabel(subtitle)
    s.setObjectName("card-sub")
    lay.addWidget(t)
    lay.addWidget(v)
    lay.addWidget(s)
    return card


class DashboardPanel(QWidget):
    """Overview: key counts and quick-action links."""

    def __init__(self, app: "MainWindowV1", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app = app
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(20)

        # ── Header ────────────────────────────────────────────────────────
        title = QLabel("Dashboard")
        title.setObjectName("section-title")
        sub = QLabel(
            "An overview of your Meraki networks and VPN exclusion configuration."
        )
        sub.setObjectName("section-sub")
        root.addWidget(title)
        root.addWidget(sub)

        # ── Stat cards row ─────────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        self._card_networks = _stat_card("Networks", "—", "loaded networks")
        self._card_exclusions = _stat_card("VPN Exclusions", "—", "rules across all networks")
        self._card_org = _stat_card("Organization", "—", "connected dashboard")
        for card in (self._card_networks, self._card_exclusions, self._card_org):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cards_row.addWidget(card)
        root.addLayout(cards_row)

        # ── Refresh button ─────────────────────────────────────────────────
        refresh_btn = QPushButton("Refresh Overview")
        refresh_btn.setObjectName("primary")
        refresh_btn.clicked.connect(self._load_overview)
        refresh_btn.setFixedWidth(180)
        root.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # ── Status note ────────────────────────────────────────────────────
        self._status_label = QLabel(
            "Select an organization and load networks to see details."
        )
        self._status_label.setObjectName("section-sub")
        root.addWidget(self._status_label)

        # ── Quick actions ──────────────────────────────────────────────────
        qa_title = QLabel("Quick Actions")
        qa_title.setObjectName("label")
        root.addWidget(qa_title)

        qa_row = QHBoxLayout()
        qa_row.setSpacing(10)
        for label, nav in [
            ("View Networks", "networks"),
            ("Manage Exclusions", "exclusions"),
            ("Copy Rules to Other Networks", "copy"),
            ("Create New Network", "new_network"),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, n=nav: self._app.navigate_to(n))
            qa_row.addWidget(btn)
        qa_row.addStretch()
        root.addLayout(qa_row)
        root.addStretch()

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self, networks: list[dict]) -> None:
        """Called by the main window when network data changes."""
        self._set_card_value(self._card_networks, str(len(networks)), f"in {self._app.get_org_name()}")
        self._set_card_value(self._card_exclusions, "—", "rules across all networks")
        self._set_card_value(self._card_org, self._app.get_org_name() or "—", "connected organization")
        if networks:
            self._status_label.setText(
                f"{len(networks)} MX network(s) loaded. "
                "Click 'Refresh Overview' to count total VPN exclusions."
            )
        else:
            self._status_label.setText("Select an organization and load networks to see details.")

    @staticmethod
    def _set_card_value(card: QFrame, value: str, sub: str = "") -> None:
        labels = card.findChildren(QLabel)
        if len(labels) >= 2:
            labels[1].setText(value)
        if len(labels) >= 3 and sub:
            labels[2].setText(sub)

    def _load_overview(self) -> None:
        networks = self._app.get_networks()
        client = self._app.get_client()
        org_id = self._app.get_org_id()
        if not networks or not client or not org_id:
            self._status_label.setText(
                "Please connect and load networks first."
            )
            return
        self._status_label.setText("Loading exclusion counts…")
        self._app.run_worker(
            lambda: self._count_exclusions(client, org_id, networks),
            on_result=self._on_overview,
            status_msg="Counting VPN exclusions…",
        )

    @staticmethod
    def _count_exclusions(client, org_id: str, networks: list[dict]) -> tuple[int, int]:
        total = 0
        for net in networks:
            try:
                rs = client.get_rules(org_id, net["id"])
                total += len(rs.rules)
            except Exception:
                pass
        return len(networks), total

    def _on_overview(self, result: tuple[int, int]) -> None:
        net_count, excl_count = result
        self._set_card_value(
            self._card_networks, str(net_count), f"in {self._app.get_org_name()}"
        )
        self._set_card_value(
            self._card_exclusions, str(excl_count), "rules across all networks"
        )
        self._set_card_value(
            self._card_org, self._app.get_org_name(), "connected organization"
        )
        self._status_label.setText("Overview up to date.")
