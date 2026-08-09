# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for GrayBar Meraki Manager (Windows build)
# Run from the project root:  pyinstaller meraki_client.spec

import sys
from pathlib import Path

block_cipher = None
APP_NAME = "GrayBarMerakiManager"

a = Analysis(
    ["main_client.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Bundle the samples folder so import examples are available
        ("samples", "samples"),
    ],
    hiddenimports=[
        # PySide6 plugins needed at runtime
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtPrintSupport",
        # Meraki SDK internals
        "meraki.api",
        "meraki.api.appliance",
        "meraki.api.organizations",
        "meraki.api.networks",
        "meraki.rest_session",
        # Requests / urllib
        "requests",
        "urllib3",
        "certifi",
        "charset_normalizer",
        "idna",
        # dotenv (imported by settings even if .env is absent)
        "dotenv",
        # openpyxl for Excel export
        "openpyxl",
        "openpyxl.styles",
        "openpyxl.utils",
        # Pydantic
        "pydantic",
        "pydantic_core",
        # Cryptography (profile encryption)
        "cryptography",
        "cryptography.fernet",
        "cryptography.hazmat.primitives",
        "cryptography.hazmat.primitives.hashes",
        "cryptography.hazmat.primitives.kdf.pbkdf2",
        "cryptography.hazmat.backends",
        # Auth / profile store
        "auth",
        "auth.profile_store",
        # App packages
        "config",
        "config.settings",
        "gui",
        "gui.v1",
        "gui.v1.main_window_v1",
        "gui.v1.style",
        "gui.v1.widgets.dashboard",
        "gui.v1.widgets.networks_panel",
        "gui.v1.widgets.exclusions_panel",
        "gui.v1.widgets.compare_panel",
        "gui.v1.widgets.copy_wizard",
        "gui.v1.widgets.new_network_wizard",
        "gui.v1.widgets.activity_log",
        "gui.v1.dialogs.rule_editor_v1",
        "gui.workers",
        "meraki_client",
        "meraki_client.client",
        "meraki_client.client_v1",
        "meraki_client.retry",
        "meraki_client.exceptions",
        "rules",
        "rules.models",
        "rules.parser",
        "rules.normalizer",
        "rules.comparer",
        "services",
        "services.workflow",
        "services.copy_service",
        "services.compare_service",
        "services.network_service",
        "reporting",
        "reporting.logging_config",
        "reporting.summary",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Keep the bundle lean — exclude unused heavy packages
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
        "cv2",
        "IPython",
        "notebook",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,            # compress binaries (reduces size ~30%)
    console=False,       # no terminal window — pure GUI
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
