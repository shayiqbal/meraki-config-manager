"""Activity log panel — colour-coded timestamped operation history."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


_LEVEL_COLOURS = {
    "INFO":    ("#1e40af", "#eff6ff"),
    "SUCCESS": ("#15803d", "#f0fdf4"),
    "WARNING": ("#b45309", "#fffbeb"),
    "ERROR":   ("#b91c1c", "#fef2f2"),
}


class ActivityLogPanel(QWidget):
    """Scrollable, HTML-formatted operation history panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        title = QLabel("Activity Log")
        title.setObjectName("section-title")
        sub = QLabel("All recent operations with timestamps and outcomes.")
        sub.setObjectName("section-sub")
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(clear_btn)
        root.addLayout(header_row)
        root.addWidget(sub)

        # ── Log view ──────────────────────────────────────────────────────
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._log.setPlaceholderText("No activity yet. Operations will appear here.")
        root.addWidget(self._log)

        self._entries: list[str] = []

    # ── Public API used by MainWindowV1 ────────────────────────────────────

    def append(self, message: str, level: str = "INFO") -> None:
        """Add a timestamped entry at the given level."""
        ts = datetime.now().strftime("%H:%M:%S")
        text_colour, bg_colour = _LEVEL_COLOURS.get(level.upper(), _LEVEL_COLOURS["INFO"])
        html = (
            f'<div style="margin:3px 0;padding:6px 10px;'
            f'background-color:{bg_colour};border-radius:5px;">'
            f'<span style="color:#64748b;font-size:11px;">[{ts}]</span>&nbsp;'
            f'<span style="color:{text_colour};font-weight:600;font-size:11px;">'
            f'{level.upper()}</span>&nbsp;'
            f'<span style="color:#0f172a;font-size:12px;">{message}</span>'
            f'</div>'
        )
        self._entries.append(html)
        self._log.append(html)
        # Keep cursor at bottom
        scrollbar = self._log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _clear(self) -> None:
        self._entries.clear()
        self._log.clear()
