"""New Network wizard — 6-step guided workflow to create a network from a template."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.network_service import (
    CloneableConfig,
    CreateNetworkOptions,
    CreateNetworkResult,
    NetworkService,
)

if TYPE_CHECKING:
    from gui.v1.main_window_v1 import MainWindowV1

_STEP_LABELS = [
    "Template",
    "Details",
    "What to Copy",
    "Preview",
    "Creating…",
    "Results",
]

_TIMEZONES = [
    "America/Los_Angeles",
    "America/Denver",
    "America/Chicago",
    "America/New_York",
    "Europe/London",
    "Europe/Amsterdam",
    "Europe/Berlin",
    "Europe/Paris",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Asia/Kolkata",
    "Australia/Sydney",
    "UTC",
]


def _step_header(step: int, total: int, title: str, subtitle: str) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 8)
    step_note = QLabel(f"Step {step} of {total}  —  {title}")
    step_note.setObjectName("section-title")
    sub = QLabel(subtitle)
    sub.setObjectName("section-sub")
    sub.setWordWrap(True)
    lay.addWidget(step_note)
    lay.addWidget(sub)
    return w


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    return line


class NewNetworkWizardPanel(QWidget):
    """6-step wizard: template → details → copy options → preview → create → results."""

    _progress_signal = Signal(str)  # thread-safe label updates from worker thread

    def __init__(self, app: "MainWindowV1", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app = app
        self._networks: list[dict[str, Any]] = []
        self._template_config: CloneableConfig | None = None
        self._result: CreateNetworkResult | None = None
        self._ssid_psks: dict[int, str] = {}   # slot → PSK (empty = skip)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(0)

        # ── Step indicator ────────────────────────────────────────────────
        self._indicator = self._build_indicator()
        root.addWidget(self._indicator)

        # ── Pages ─────────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._page_template = self._build_template()
        self._page_details = self._build_details()
        self._page_copy_opts = self._build_copy_opts()
        self._page_preview = self._build_preview()
        self._page_creating = self._build_creating()
        self._page_results = self._build_results()
        for p in (
            self._page_template, self._page_details,
            self._page_copy_opts, self._page_preview,
            self._page_creating, self._page_results,
        ):
            self._stack.addWidget(p)
        root.addWidget(self._stack, 1)

        # ── Nav buttons ───────────────────────────────────────────────────
        nav = QHBoxLayout()
        nav.setContentsMargins(0, 12, 0, 0)
        self._back_btn = QPushButton("← Back")
        self._back_btn.clicked.connect(self._go_back)
        self._next_btn = QPushButton("Next →")
        self._next_btn.setObjectName("primary")
        self._next_btn.clicked.connect(self._go_next)
        self._create_btn = QPushButton("✓ Create Network")
        self._create_btn.setObjectName("success")
        self._create_btn.clicked.connect(self._create)
        self._create_btn.setVisible(False)
        self._restart_btn = QPushButton("Start Over")
        self._restart_btn.clicked.connect(lambda: self._goto(0))
        self._restart_btn.setVisible(False)
        nav.addWidget(self._back_btn)
        nav.addStretch()
        nav.addWidget(self._restart_btn)
        nav.addWidget(self._create_btn)
        nav.addWidget(self._next_btn)
        root.addLayout(nav)

        self._goto(0)

    # ── Page builders ──────────────────────────────────────────────────────

    def _build_indicator(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 16)
        lay.setSpacing(0)
        self._step_labels: list[QLabel] = []
        for i, label in enumerate(_STEP_LABELS):
            num = QLabel(str(i + 1))
            num.setObjectName("step-inactive")
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._step_labels.append(num)
            lay.addWidget(num)
            text = QLabel(f"  {label}  ")
            text.setObjectName("section-sub")
            lay.addWidget(text)
            if i < len(_STEP_LABELS) - 1:
                lay.addWidget(QLabel("──"))
        lay.addStretch()
        return w

    def _build_template(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)
        lay.addWidget(_step_header(1, 6, "Select Template Network",
                                   "The new network will be configured using the selected network "
                                   "as a template. Only safe, non-unique settings are copied."))
        self._template_search = QLineEdit()
        self._template_search.setObjectName("search")
        self._template_search.setPlaceholderText("🔍  Search networks…")
        self._template_search.textChanged.connect(self._filter_template_list)
        lay.addWidget(self._template_search)
        self._template_list = QListWidget()
        self._template_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._template_list.itemSelectionChanged.connect(self._on_template_selected)
        lay.addWidget(self._template_list)
        self._template_status = QLabel("Select a template network above.")
        self._template_status.setObjectName("section-sub")
        lay.addWidget(self._template_status)
        return w

    def _build_details(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)
        lay.addWidget(_step_header(2, 6, "New Network Details",
                                   "Enter the unique details for the new network. "
                                   "Name must be unique within the organization."))
        form = QFormLayout()
        form.setSpacing(10)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Branch Office — London")
        form.addRow("Network Name *", self._name_edit)
        self._tz_combo = QComboBox()
        for tz in _TIMEZONES:
            self._tz_combo.addItem(tz)
        form.addRow("Time Zone", self._tz_combo)
        self._notes_edit = QLineEdit()
        self._notes_edit.setPlaceholderText("Optional description for this network")
        form.addRow("Notes", self._notes_edit)
        lay.addLayout(form)
        lay.addStretch()
        return w

    def _build_copy_opts(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)
        lay.addWidget(_step_header(3, 6, "Select What to Copy",
                                   "Choose which settings from the template network to apply "
                                   "to the new network. Items marked ⚠ should be reviewed."))

        box = QGroupBox("Settings to Copy")
        box_lay = QVBoxLayout(box)
        self._chk_tags = QCheckBox("Network tags")
        self._chk_vpn = QCheckBox("VPN exclusion rules")
        self._chk_vpn.setChecked(True)
        self._chk_routes = QCheckBox(
            "Static routes  ⚠  (gateway IPs may be network-specific)"
        )
        self._chk_l3 = QCheckBox(
            "L3 firewall rules  ⚠  (rules may reference network-specific addresses)"
        )
        self._chk_l7 = QCheckBox("L7 firewall rules")
        self._chk_ssids = QCheckBox(
            "MX Wireless SSIDs  ⚠  (PSKs and RADIUS credentials must be re-entered manually)"
        )
        self._chk_settings = QCheckBox(
            "Appliance settings  (client tracking method, deployment mode)"
        )
        self._chk_settings.setChecked(True)
        for chk in (
            self._chk_tags, self._chk_vpn, self._chk_routes,
            self._chk_l3, self._chk_l7, self._chk_ssids, self._chk_settings,
        ):
            box_lay.addWidget(chk)
        lay.addWidget(box)

        note = QLabel(
            "Settings that cannot be safely cloned (e.g. VLANs, IP addresses, "
            "SSID PSKs, RADIUS secrets) are never copied automatically."
        )
        note.setObjectName("section-sub")
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addStretch()
        return w

    def _build_preview(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)
        lay.addWidget(_step_header(4, 6, "Preview",
                                   "Review everything that will be created and copied "
                                   "before committing."))
        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        lay.addWidget(self._preview_text)
        return w

    def _build_creating(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)
        lay.addWidget(_step_header(5, 6, "Creating Network…",
                                   "The network is being created and configured. Please wait."))
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress_label = QLabel("Initializing…")
        self._progress_label.setObjectName("section-sub")
        self._progress_signal.connect(self._progress_label.setText)
        lay.addWidget(self._progress)
        lay.addWidget(self._progress_label)
        lay.addStretch()
        return w

    def _build_results(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)
        lay.addWidget(_step_header(6, 6, "Results",
                                   "The create operation is complete. "
                                   "Review each step's outcome below."))
        self._results_text = QTextEdit()
        self._results_text.setReadOnly(True)
        lay.addWidget(self._results_text)
        return w

    # ── Navigation ─────────────────────────────────────────────────────────

    def refresh(self, networks: list[dict[str, Any]]) -> None:
        self._networks = networks
        if self._stack.currentIndex() == 0:
            self._populate_template_list()

    def pre_select_template(self, network: dict[str, Any]) -> None:
        """Called when navigated from Networks panel with a pre-chosen template."""
        self._goto(0)
        self._populate_template_list()
        for i in range(self._template_list.count()):
            item = self._template_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole)["id"] == network["id"]:
                self._template_list.setCurrentItem(item)
                break

    def _goto(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._back_btn.setVisible(0 < index < 5)
        self._next_btn.setVisible(index < 3)
        self._create_btn.setVisible(index == 3)
        self._restart_btn.setVisible(index == 5)
        self._update_indicator(index)
        if index == 0:
            self._populate_template_list()
        elif index == 3:
            self._build_preview_text()

    def _go_back(self) -> None:
        self._goto(self._stack.currentIndex() - 1)

    def _go_next(self) -> None:
        idx = self._stack.currentIndex()
        if idx == 0 and not self._validate_template():
            return
        if idx == 1 and not self._validate_details():
            return
        # Step 2 (copy opts) → Step 3 (preview): prompt for PSKs if needed
        if idx == 2 and self._chk_ssids.isChecked():
            self._prompt_psks()   # may update self._ssid_psks then continue
            return
        self._goto(idx + 1)

    def _prompt_psks(self) -> None:
        """Show a PSK dialog if any selected SSIDs use PSK auth; otherwise go straight to preview."""
        cfg = self._template_config
        psk_ssids = [
            s for s in (cfg.ssids if cfg else [])
            if s.get("authMode") == "psk" and s.get("name")
        ]
        if not psk_ssids:
            # No PSK SSIDs — skip dialog
            self._goto(3)
            return

        dlg = _PskDialog(psk_ssids, self._ssid_psks, self)
        if dlg.exec():
            self._ssid_psks = dlg.get_psks()
        else:
            self._ssid_psks = {}   # user cancelled — clear any previous entries
        self._goto(3)

    def _update_indicator(self, active: int) -> None:
        for i, lbl in enumerate(self._step_labels):
            if i < active:
                lbl.setObjectName("step-done")
                lbl.setText("✓")
            elif i == active:
                lbl.setObjectName("step-active")
                lbl.setText(str(i + 1))
            else:
                lbl.setObjectName("step-inactive")
                lbl.setText(str(i + 1))
            lbl.setStyleSheet("")

    # ── Step 1 ─────────────────────────────────────────────────────────────

    def _populate_template_list(self) -> None:
        self._template_search.clear()
        selected_id = (
            self._selected_template()["id"] if self._selected_template() else None
        )
        self._template_list.clear()
        for net in self._networks:
            item = QListWidgetItem(
                f"{net['name']}  [{', '.join(net.get('productTypes') or [])}]"
            )
            item.setData(Qt.ItemDataRole.UserRole, net)
            self._template_list.addItem(item)
            if net["id"] == selected_id:
                self._template_list.setCurrentItem(item)

    def _filter_template_list(self, text: str) -> None:
        q = text.lower()
        for i in range(self._template_list.count()):
            item = self._template_list.item(i)
            net = item.data(Qt.ItemDataRole.UserRole)
            item.setHidden(bool(q) and q not in net["name"].lower())

    def _on_template_selected(self) -> None:
        tmpl = self._selected_template()
        if not tmpl:
            return
        self._template_status.setText(
            f"Template: {tmpl['name']}  —  loading configuration…"
        )
        self._template_config = None
        net_svc = self._app.get_network_service()
        org_id = self._app.get_org_id()
        self._app.run_worker(
            lambda: net_svc.get_cloneable_config(org_id, tmpl),
            on_result=self._on_template_config,
            status_msg=f"Reading config from {tmpl['name']}…",
        )

    def _on_template_config(self, config: CloneableConfig) -> None:
        self._template_config = config
        tmpl = self._selected_template()
        n = tmpl["name"] if tmpl else "—"
        excl = len(config.vpn_exclusions.rules)
        routes = len(config.static_routes)
        l3 = len(config.l3_firewall_rules)
        l7 = len(config.l7_firewall_rules)
        self._template_status.setText(
            f"Template: {n}  —  "
            f"{excl} VPN exclusion(s), {routes} static route(s), "
            f"{l3} L3 rule(s), {l7} L7 rule(s)"
        )
        # Pre-fill timezone from template
        tz = config.source_timezone
        idx = self._tz_combo.findText(tz)
        if idx >= 0:
            self._tz_combo.setCurrentIndex(idx)

    def _selected_template(self) -> dict[str, Any] | None:
        items = self._template_list.selectedItems()
        return items[0].data(Qt.ItemDataRole.UserRole) if items else None

    def _validate_template(self) -> bool:
        if not self._selected_template():
            QMessageBox.warning(self, "No Template", "Please select a template network.")
            return False
        if self._template_config is None:
            QMessageBox.warning(
                self, "Loading…",
                "Template configuration is still loading. Please wait a moment.",
            )
            return False
        return True

    # ── Step 2 ─────────────────────────────────────────────────────────────

    def _validate_details(self) -> bool:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Name Required", "Please enter a network name.")
            return False
        return True

    # ── Step 4: preview text ───────────────────────────────────────────────

    def _build_preview_text(self) -> None:
        if not self._template_config:
            self._preview_text.setPlainText("No template config loaded.")
            return
        cfg = self._template_config
        lines: list[str] = []
        tmpl = self._selected_template()
        lines.append(f"Template:   {tmpl['name'] if tmpl else '—'}")
        lines.append(f"New Name:   {self._name_edit.text().strip()}")
        lines.append(f"Time Zone:  {self._tz_combo.currentText()}")
        if self._notes_edit.text().strip():
            lines.append(f"Notes:      {self._notes_edit.text().strip()}")
        lines.append("")
        lines.append("What will be applied:")
        lines.append(f"  {'✓' if self._chk_tags.isChecked() else '–'}  Tags  "
                     f"({len(cfg.tags)} tag(s) from template)")
        lines.append(f"  {'✓' if self._chk_vpn.isChecked() else '–'}  VPN exclusion rules  "
                     f"({len(cfg.vpn_exclusions.rules)} rule(s))")
        lines.append(f"  {'✓' if self._chk_routes.isChecked() else '–'}  Static routes  "
                     f"({len(cfg.static_routes)} route(s))")
        lines.append(f"  {'✓' if self._chk_l3.isChecked() else '–'}  L3 firewall rules  "
                     f"({len(cfg.l3_firewall_rules)} rule(s))")
        lines.append(f"  {'✓' if self._chk_l7.isChecked() else '–'}  L7 firewall rules  "
                     f"({len(cfg.l7_firewall_rules)} rule(s))")

        ssid_count = len([s for s in cfg.ssids if s.get("name")])
        lines.append(f"  {'✓' if self._chk_ssids.isChecked() else '–'}  MX Wireless SSIDs  "
                     f"({ssid_count} SSID slot(s) configured on template)"
                     + ("  ⚠ PSKs must be set manually" if self._chk_ssids.isChecked() else ""))

        tracking = cfg.appliance_settings.get("clientTrackingMethod", "—")
        deploy   = cfg.appliance_settings.get("deploymentMode", "—")
        lines.append(f"  {'✓' if self._chk_settings.isChecked() else '–'}  Appliance settings  "
                     f"(tracking: {tracking}, deployment: {deploy})")

        lines.append("")
        lines.append("Will NOT be copied:")
        lines.append("  –  VLANs and VLAN subnets (network-unique)")
        lines.append("  –  IP/WAN addresses (network-unique)")
        lines.append("  –  SSID PSKs and RADIUS secrets (write-only, cannot be read)")
        lines.append("  –  Warm spare or HA settings")
        lines.append("  –  Client VPN settings")
        lines.append("  –  Device assignments")
        self._preview_text.setPlainText("\n".join(lines))

    # ── Step 5: create ─────────────────────────────────────────────────────

    def _create(self) -> None:
        tmpl = self._selected_template()
        name = self._name_edit.text().strip()
        answer = QMessageBox.question(
            self,
            "Create Network",
            f"Create '{name}' using '{tmpl['name'] if tmpl else '?'}' as template?\n\n"
            "This action creates a new network in your Meraki organization.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        options = CreateNetworkOptions(
            name=name,
            timezone=self._tz_combo.currentText(),
            notes=self._notes_edit.text().strip(),
            copy_tags=self._chk_tags.isChecked(),
            copy_vpn_exclusions=self._chk_vpn.isChecked(),
            copy_static_routes=self._chk_routes.isChecked(),
            copy_l3_firewall=self._chk_l3.isChecked(),
            copy_l7_firewall=self._chk_l7.isChecked(),
            copy_ssids=self._chk_ssids.isChecked(),
            copy_network_settings=self._chk_settings.isChecked(),
            ssid_psks=dict(self._ssid_psks),
        )
        self._goto(4)  # show creating page
        org_id = self._app.get_org_id()
        config = self._template_config
        net_svc = self._app.get_network_service()

        def _do() -> CreateNetworkResult:
            def _prog(msg: str) -> None:
                self._progress_signal.emit(msg)   # thread-safe: routes via Qt signal
            return net_svc.create_and_configure(org_id, options, config, progress=_prog)

        def _done(result: CreateNetworkResult) -> None:
            self._result = result
            self._progress.setRange(0, 100)
            self._progress.setValue(100)
            self._show_results()
            self._goto(5)
            level = "SUCCESS" if result.success else "ERROR"
            self._app.log_activity(
                f"Network '{name}' created: "
                + (f"ID {result.network_id}" if result.success else result.error),
                level,
            )
            # Reload networks so the new one appears
            self._app.reload_networks()

        self._app.run_worker(_do, on_result=_done, status_msg=f"Creating '{name}'…")

    def _show_results(self) -> None:
        result = self._result
        if not result:
            return
        lines: list[str] = []
        overall = "✓ Network created successfully." if result.success else f"✗ {result.error}"
        lines.append(overall)
        if result.network_id:
            lines.append(f"  Network ID: {result.network_id}")
        lines.append("")
        lines.append("Step outcomes:")
        for label, ok, detail in result.steps:
            icon = "  ✓" if ok else "  ✗"
            lines.append(f"{icon}  {label}" + (f"  —  {detail}" if detail else ""))
        self._results_text.setPlainText("\n".join(lines))


# ── PSK Entry Dialog ────────────────────────────────────────────────────────────

class _PskDialog(QDialog):
    """Prompts the user to enter PSKs for PSK-protected MX SSIDs.

    Shows one password field per PSK SSID.  The user can fill in any subset
    and leave the rest blank — blank entries are skipped (PSK stays unconfigured).
    A 'Skip All — Update Manually Later' button is also available.
    """

    def __init__(
        self,
        psk_ssids: list[dict],
        existing_psks: dict[int, str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configure SSID Passwords")
        self.setMinimumWidth(480)
        self._fields: dict[int, QLineEdit] = {}

        lay = QVBoxLayout(self)
        lay.setSpacing(14)

        # Header
        title = QLabel("Set SSID Passwords")
        title.setObjectName("section-title")
        lay.addWidget(title)

        sub = QLabel(
            "The SSIDs below use password protection (PSK). "
            "Enter a password for each one now, or leave blank to configure manually "
            "in the Meraki dashboard after the network is created."
        )
        sub.setObjectName("section-sub")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        # Scrollable area for SSID fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        form = QFormLayout(container)
        form.setSpacing(10)

        for ssid in psk_ssids:
            number = ssid.get("number", 0)
            name   = ssid.get("name", f"SSID {number}")
            field  = QLineEdit()
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setPlaceholderText("Leave blank to skip")
            field.setText(existing_psks.get(number, ""))
            lbl = QLabel(f"  SSID {number}:  {name}")
            lbl.setObjectName("label")
            form.addRow(lbl, field)
            self._fields[number] = field

        scroll.setWidget(container)
        lay.addWidget(scroll)

        # Hint
        hint = QLabel("Minimum 8 characters required by Meraki for WPA PSKs.")
        hint.setObjectName("section-sub")
        lay.addWidget(hint)

        # Buttons
        btns = QDialogButtonBox()
        save_btn   = btns.addButton("Save & Continue", QDialogButtonBox.ButtonRole.AcceptRole)
        skip_btn   = btns.addButton("Skip All — Update Manually Later",
                                    QDialogButtonBox.ButtonRole.RejectRole)
        save_btn.setObjectName("primary")
        skip_btn.setObjectName("ghost")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def get_psks(self) -> dict[int, str]:
        """Return {slot: psk} for every field that has a non-empty value."""
        return {
            number: field.text().strip()
            for number, field in self._fields.items()
            if field.text().strip()
        }
