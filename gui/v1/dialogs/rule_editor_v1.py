"""Enhanced VPN exclusion rule editor dialog for V1."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from rules.models import RuleCategory, VpnExclusionRule


class RuleEditorV1(QDialog):
    """Add or edit a single VPN exclusion rule with inline help text."""

    def __init__(self, rule: VpnExclusionRule | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VPN Exclusion Rule" if rule is None else "Edit Rule")
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 20)

        # ── Rule type ─────────────────────────────────────────────────────
        type_box = QGroupBox("Rule Type")
        type_form = QFormLayout(type_box)
        self.category = QComboBox()
        self.category.addItem("Layer 3 / DNS  (custom destination)", RuleCategory.CUSTOM)
        self.category.addItem("Major Application  (well-known service)", RuleCategory.MAJOR_APPLICATION)
        self.category.addItem("NBAR Application  (application ID)", RuleCategory.APPLICATION)
        self.category.currentIndexChanged.connect(self._update_fields)
        type_form.addRow("Type", self.category)
        root.addWidget(type_box)

        # ── Custom (Layer 3 / DNS) fields ─────────────────────────────────
        self._custom_box = QGroupBox("Destination")
        custom_form = QFormLayout(self._custom_box)
        self.protocol = QComboBox()
        self.protocol.addItems(["any", "tcp", "udp", "icmp", "dns"])
        custom_form.addRow("Protocol", self.protocol)
        self.destination = QLineEdit()
        self.destination.setPlaceholderText("e.g. 10.0.0.0/8 or any (for DNS: hostname)")
        custom_form.addRow("Destination", self.destination)
        dest_hint = QLabel(
            "For Layer 3: an IP CIDR or 'any'.  For DNS: a hostname (e.g. example.com)."
        )
        dest_hint.setObjectName("section-sub")
        dest_hint.setWordWrap(True)
        custom_form.addRow("", dest_hint)
        self.port = QLineEdit("any")
        self.port.setPlaceholderText("e.g. 443  or  8000-9000  or  any")
        custom_form.addRow("Destination Port", self.port)
        root.addWidget(self._custom_box)

        # ── Application fields ────────────────────────────────────────────
        self._app_box = QGroupBox("Application")
        app_form = QFormLayout(self._app_box)
        self.application_id = QLineEdit()
        self.application_id.setPlaceholderText("Meraki application ID")
        app_form.addRow("Application ID", self.application_id)
        self.app_name = QLineEdit()
        self.app_name.setPlaceholderText("Display name (optional)")
        app_form.addRow("Name", self.app_name)
        root.addWidget(self._app_box)

        # ── Order ─────────────────────────────────────────────────────────
        self.order = QSpinBox()
        self.order.setRange(0, 9999)
        order_row = QHBoxLayout()
        order_row.addWidget(QLabel("Rule order"))
        order_row.addWidget(self.order)
        order_row.addStretch()
        root.addLayout(order_row)

        # ── Buttons ───────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        # ── Populate if editing ───────────────────────────────────────────
        if rule is not None:
            self._populate(rule)

        self._update_fields()

    def _populate(self, rule: VpnExclusionRule) -> None:
        idx = self.category.findData(rule.category)
        if idx >= 0:
            self.category.setCurrentIndex(idx)
        self.protocol.setCurrentText(rule.protocol)
        self.destination.setText(rule.destination or "")
        self.port.setText(rule.port or "any")
        self.application_id.setText(rule.application_id or "")
        self.app_name.setText(rule.name or "")
        self.order.setValue(rule.order)

    def _update_fields(self) -> None:
        cat = self.category.currentData()
        is_custom = cat == RuleCategory.CUSTOM
        self._custom_box.setVisible(is_custom)
        self._app_box.setVisible(not is_custom)

    def _validate(self) -> None:
        try:
            self.rule()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Rule", str(exc))
            return
        self.accept()

    def rule(self) -> VpnExclusionRule:
        cat = self.category.currentData()
        return VpnExclusionRule(
            category=cat,
            order=self.order.value(),
            protocol=self.protocol.currentText() if cat == RuleCategory.CUSTOM else "any",
            destination=self.destination.text().strip() or None,
            port=self.port.text().strip() or "any",
            application_id=self.application_id.text().strip() or None,
            name=self.app_name.text().strip() or None,
        )
