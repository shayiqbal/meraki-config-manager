# GrayBar Meraki Manager

A Windows desktop application for managing Cisco Meraki MX networks.
Built for GrayBar network teams running on a shared Windows 11 VM or jump host.

Each team member enters their own Meraki Dashboard API key on every launch.
The key is never stored to disk.

## What it does

- **Compare Networks** — side-by-side diff of VPN exclusion rules, SSIDs and
  settings across any number of networks; export results to PDF
- **Copy Rules** — copy Local Breakout VPN exclusion rules from one network to
  many; export results to CSV or Excel showing Added vs Already Existed per rule
- **Local Breakouts** — view, import, dry-run, and deploy VPN exclusion rules
  for a single network
- **New Network** — create a new MX network from a template with optional
  copy of VPN rules, firewall rules, SSIDs, and appliance settings
- **Activity Log** — timestamped in-app log of every operation

## Safety model

- The API key is entered through the login dialog on every launch; it is
  **never written to disk, displayed in the UI, or included in any log**.
- Deployment is disabled until a successful dry run has been reviewed.
- Each network is compared and deployed independently.
- Existing rules are preserved in the default `merge` mode.
- Identical rules are skipped automatically.
- The live configuration is re-read before every deployment.
- A changed live fingerprint blocks deployment and requires a new dry run.
- Networks deploy independently; one API failure does not stop later networks.

## Building the Windows installer

Run on a Windows 11 machine (VM or physical):

1. Copy or clone this repository to the Windows machine.
2. Double-click **`build.bat`**.
3. The script downloads Python 3.12, installs all dependencies, and builds
   the installer automatically (takes 5–8 minutes on first run).
4. When complete, `Output\GrayBarMerakiManager-Setup.exe` is produced and
   the Output folder opens automatically.

No manual Python installation or command-line steps are required.

## Distributing to end users

Give each user the single file:

```
GrayBarMerakiManager-Setup.exe
```

They double-click it, click through the installer wizard (Next → Next → Finish),
and a **GrayBar Meraki Manager** desktop shortcut is created automatically.

Double-clicking the shortcut opens the API key dialog. The user enters their
Meraki Dashboard API key, clicks **Connect**, and the full application opens.

## Required Meraki permissions

The Dashboard administrator account whose API key is used must have:

- Read access to the target organization and networks
- Write access to target networks (for deploy / copy / create operations)

Required OAuth scopes: `sdwan:config:read`, `sdwan:config:write`

## Troubleshooting

**"Invalid API key" on connect**
Verify the key in Meraki Dashboard → Profile → API access. Regenerate if needed.

**"401 or 403" error**
The key is valid but the account lacks permission for this organization or network.
Ask your Meraki administrator to grant access.

**No networks shown after loading**
Only networks with the `appliance` product type (MX devices) are listed.
Wireless-only or switch-only networks are filtered out automatically.

**Windows Defender flags the installer**
This is a false positive common with unsigned Python executables.
Add an exclusion in Windows Security for the install folder:
`C:\Program Files\GrayBar Meraki Manager\`

## Project structure

```text
config/          Settings (no .env — key is entered at runtime)
gui/             PySide6 application windows and panels
meraki_client/   Meraki API wrapper with retry and direct NBAR support
rules/           Rule models, parsing, normalization and comparison
services/        Workflow, copy, compare and network creation logic
reporting/       Structured logging
samples/         CSV, JSON and XLSX import examples
tests/           Unit tests (never contact Meraki)
main_client.py   Entry point — API key dialog + main window
build.bat        Windows build script (produces installer)
meraki_client.spec  PyInstaller configuration
installer.iss    Inno Setup installer script
```
