"""Manual VPN exclusion rule editor."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
)

from rules.models import RuleCategory, VpnExclusionRule


class RuleEditor(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add VPN Exclusion Rule")
        form = QFormLayout(self)
        self.category = QComboBox()
        self.category.addItem("Layer 3 / DNS", RuleCategory.CUSTOM)
        self.category.addItem("Major Application", RuleCategory.MAJOR_APPLICATION)
        self.category.addItem("NBAR Application", RuleCategory.APPLICATION)
        self.protocol = QComboBox()
        self.protocol.addItems(["any", "dns", "icmp", "tcp", "udp"])
        self.destination = QLineEdit()
        self.port = QLineEdit("any")
        self.application_id = QLineEdit()
        self.name = QLineEdit()
        self.order = QSpinBox()
        self.order.setRange(0, 9999)
        form.addRow("Type", self.category)
        form.addRow("Protocol", self.protocol)
        form.addRow("Destination", self.destination)
        form.addRow("Destination port", self.port)
        form.addRow("Application ID", self.application_id)
        form.addRow("Application name", self.name)
        form.addRow("Order", self.order)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _validate(self) -> None:
        try:
            self.rule()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid rule", str(exc))
            return
        self.accept()

    def rule(self) -> VpnExclusionRule:
        return VpnExclusionRule(
            category=self.category.currentData(),
            order=self.order.value(),
            protocol=self.protocol.currentText(),
            destination=self.destination.text() or None,
            port=self.port.text(),
            application_id=self.application_id.text() or None,
            name=self.name.text() or None,
        )

