"""Application-wide QSS stylesheet for V1.

A single import keeps all visual tokens in one place so they
can be adjusted without touching widget code.
"""

APP_STYLE = """
/* ── Global ──────────────────────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: #f8fafc;
    color: #0f172a;
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 13px;
}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
QWidget#sidebar {
    background-color: #1e293b;
    border-right: 1px solid #0f172a;
}
QLabel#app-title {
    color: #f1f5f9;
    font-size: 14px;
    font-weight: 700;
    padding: 8px 16px 2px 16px;
}
QLabel#app-version {
    color: #475569;
    font-size: 11px;
    padding: 0 16px 16px 16px;
}
QLabel#nav-section {
    color: #475569;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 12px 16px 4px 16px;
    text-transform: uppercase;
}
QPushButton#nav {
    background-color: transparent;
    color: #94a3b8;
    text-align: left;
    padding: 9px 16px;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    margin: 1px 8px;
}
QPushButton#nav:hover {
    background-color: #334155;
    color: #e2e8f0;
}
QPushButton#nav:checked {
    background-color: #2563eb;
    color: #ffffff;
}

/* ── Top bar ──────────────────────────────────────────────────────────── */
QWidget#topbar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}
QLabel#page-title {
    font-size: 16px;
    font-weight: 700;
    color: #0f172a;
    padding: 0 0 0 4px;
}
QLabel#conn-ok {
    color: #16a34a;
    font-size: 12px;
    font-weight: 600;
}
QLabel#conn-fail {
    color: #dc2626;
    font-size: 12px;
    font-weight: 600;
}
QLabel#conn-pending {
    color: #d97706;
    font-size: 12px;
    font-weight: 600;
}

/* ── Cards ────────────────────────────────────────────────────────────── */
QFrame#card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}
QLabel#card-title {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
    letter-spacing: 0.5px;
}
QLabel#card-value {
    font-size: 30px;
    font-weight: 700;
    color: #0f172a;
}
QLabel#card-sub {
    font-size: 12px;
    color: #94a3b8;
}

/* ── Section labels ───────────────────────────────────────────────────── */
QLabel#section-title {
    font-size: 17px;
    font-weight: 700;
    color: #0f172a;
}
QLabel#section-sub {
    font-size: 13px;
    color: #64748b;
}
QLabel#label {
    font-size: 12px;
    font-weight: 600;
    color: #374151;
}

/* ── Tables ───────────────────────────────────────────────────────────── */
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    gridline-color: #f1f5f9;
    alternate-background-color: #f8fafc;
    selection-background-color: #eff6ff;
    selection-color: #1e40af;
}
QTableWidget::item {
    padding: 7px 10px;
    border: none;
}
QTableWidget::item:selected {
    background-color: #eff6ff;
    color: #1e40af;
}
QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    font-weight: 600;
    font-size: 12px;
    padding: 7px 10px;
    border: none;
    border-bottom: 2px solid #e2e8f0;
    border-right: 1px solid #e2e8f0;
}

/* ── Buttons ──────────────────────────────────────────────────────────── */
QPushButton {
    background-color: #f1f5f9;
    color: #334155;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 32px;
}
QPushButton:hover { background-color: #e2e8f0; }
QPushButton:pressed { background-color: #cbd5e1; }
QPushButton:disabled { color: #94a3b8; background-color: #f8fafc; }

QPushButton#primary {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
}
QPushButton#primary:hover { background-color: #1d4ed8; }
QPushButton#primary:pressed { background-color: #1e40af; }
QPushButton#primary:disabled { background-color: #bfdbfe; color: #ffffff; }

QPushButton#danger {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
}
QPushButton#danger:hover { background-color: #b91c1c; }
QPushButton#danger:disabled { background-color: #fca5a5; }

QPushButton#success {
    background-color: #16a34a;
    color: #ffffff;
    border: none;
}
QPushButton#success:hover { background-color: #15803d; }
QPushButton#success:disabled { background-color: #86efac; }

QPushButton#ghost {
    background-color: transparent;
    border: none;
    color: #2563eb;
    padding: 4px 8px;
}
QPushButton#ghost:hover { color: #1d4ed8; text-decoration: underline; }

/* ── Inputs ───────────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
    color: #0f172a;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
    border-color: #2563eb;
}
QLineEdit:disabled, QTextEdit:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
}
QLineEdit#search {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 20px;
    padding: 6px 14px;
}
QLineEdit#search:focus { border-color: #2563eb; background-color: #ffffff; }

QComboBox {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #0f172a;
    min-height: 32px;
}
QComboBox:focus { border-color: #2563eb; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    selection-background-color: #eff6ff;
    selection-color: #1e40af;
    padding: 4px;
}

/* ── List widgets ─────────────────────────────────────────────────────── */
QListWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 5px;
    margin: 1px 0;
}
QListWidget::item:selected {
    background-color: #eff6ff;
    color: #1e40af;
}
QListWidget::item:hover:!selected { background-color: #f8fafc; }

/* ── Check boxes ──────────────────────────────────────────────────────── */
QCheckBox {
    color: #0f172a;
    spacing: 8px;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid #d1d5db;
    border-radius: 4px;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}
QCheckBox::indicator:hover { border-color: #2563eb; }

/* ── Progress bar ─────────────────────────────────────────────────────── */
QProgressBar {
    background-color: #e2e8f0;
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
    font-size: 10px;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 4px;
}

/* ── Separators ───────────────────────────────────────────────────────── */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    color: #e2e8f0;
    max-height: 1px;
    background-color: #e2e8f0;
}

/* ── Status bar ───────────────────────────────────────────────────────── */
QStatusBar {
    background-color: #f8fafc;
    border-top: 1px solid #e2e8f0;
    color: #64748b;
    font-size: 12px;
    padding: 2px 8px;
}

/* ── Step badge labels ────────────────────────────────────────────────── */
QLabel#step-active {
    background-color: #2563eb;
    color: #ffffff;
    border-radius: 12px;
    font-weight: 700;
    font-size: 12px;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    qproperty-alignment: AlignCenter;
}
QLabel#step-done {
    background-color: #16a34a;
    color: #ffffff;
    border-radius: 12px;
    font-weight: 700;
    font-size: 12px;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    qproperty-alignment: AlignCenter;
}
QLabel#step-inactive {
    background-color: #e2e8f0;
    color: #94a3b8;
    border-radius: 12px;
    font-weight: 700;
    font-size: 12px;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    qproperty-alignment: AlignCenter;
}

/* ── Inline badge labels ──────────────────────────────────────────────── */
QLabel#badge-new {
    background-color: #dcfce7;
    color: #166534;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
}
QLabel#badge-exists {
    background-color: #f1f5f9;
    color: #475569;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
}
QLabel#badge-invalid {
    background-color: #fee2e2;
    color: #991b1b;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
}

/* ── Scrollbars ───────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #f8fafc;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background-color: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background-color: #f8fafc;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background-color: #94a3b8; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Tool tips ────────────────────────────────────────────────────────── */
QToolTip {
    background-color: #1e293b;
    color: #f1f5f9;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}
"""
