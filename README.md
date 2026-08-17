# Meraki Config Manager

A Windows desktop application for managing Cisco Meraki MX networks.

Secure profile-based login encrypts your Meraki Dashboard API key with your
password using PBKDF2 + AES-128. The key is never stored in plaintext, never
written to logs, and never visible in the UI.

## Features

- **Dashboard** — at-a-glance stats: organization name, network count, total
  VPN exclusion rules; quick-action buttons to jump to any feature
- **Networks** — full list of MX networks with product types, tags, VPN
  exclusion count and Network ID; search filter; one-click clone to New Network
- **Compare Networks** — side-by-side diff of VPN exclusion rules, SSIDs and
  appliance settings across any number of networks; colour-coded
  match / missing / different cells; export to PDF
- **Copy Rules** — 5-step wizard to copy Local Breakout VPN exclusion rules
  from one network to many; preview shows `[NEW]` / `[EXISTS]` per rule per
  network; type `CONFIRM` to deploy; export results to CSV or Excel
- **Group Policies** — 5-step wizard to compare and copy Group Policies across
  networks; identity matched by policy name; preview shows `[NEW]` / `[EXISTS]`
  per policy per network; type `CONFIRM` to deploy; results show `ADDED` /
  `ALREADY EXISTED`; export to CSV or Excel
- **New Network** — 6-step wizard to create a new MX network from a template,
  copying VPN rules, firewall rules, SSIDs and appliance settings
- **Activity Log** — colour-coded timestamped log of every operation

## Safety model

- API key is encrypted at rest (PBKDF2-HMAC-SHA256 + Fernet AES-128).
  It is **never written to disk in plaintext, displayed in the UI, or
  included in any log**.
- Deployment is disabled until a successful dry run has been reviewed.
- Live configuration is re-read before every deployment; a changed fingerprint
  blocks deployment and requires a new dry run.
- Rules and policies are compared individually; existing entries are preserved
  in the default `merge` mode.
- Identical rules / policies already on the destination are skipped
  automatically — no duplicates are ever created.
- Networks deploy independently; one API failure does not stop later networks.

## Building the Windows installer

Run on a Windows 10 or 11 machine (VM or physical):

1. Clone or copy this repository to the Windows machine.
2. Right-click **`build.bat`** → **Run as administrator**.
3. The script downloads Python 3.12, creates a virtual environment, installs
   all dependencies, runs PyInstaller, and builds the installer automatically
   (5–8 minutes on first run).
4. When complete, `Output\MerakiConfigManager-Setup.exe` is produced and the
   Output folder opens automatically.

No manual Python installation or command-line steps are required.

## Distributing to end users

Give each user the single file:

```
MerakiConfigManager-Setup.exe
```

They double-click it, click through the installer wizard (Next → Next → Finish),
and a **Meraki Config Manager** desktop shortcut is created automatically.

On first launch, the user creates a profile (username + password + API key).
On subsequent launches they sign in with username and password — the API key
is decrypted from the encrypted profile store automatically.

## Running in development (macOS / Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python main_client.py
```

## Required Meraki permissions

The Dashboard administrator account whose API key is used must have:

- Read access to the target organization and networks
- Write access to target networks (for deploy / copy / create operations)

Required OAuth scopes: `sdwan:config:read`, `sdwan:config:write`,
`dashboard:general:config:read`, `dashboard:general:config:write`

## Troubleshooting

**"Invalid API key" on profile creation**
Verify the key in Meraki Dashboard → Profile → API access. Regenerate if needed.

**"401 or 403" error**
The key is valid but the account lacks permission for this organization or
network. Ask your Meraki administrator to grant access.

**No networks shown after loading**
Only networks with the `appliance` product type (MX devices) are listed.
Wireless-only or switch-only networks are filtered out automatically.

**No Group Policies shown**
Group policies are network-level; only networks that have at least one group
policy configured will return results. Check Meraki Dashboard → Group Policies
for the source network.

**Windows Defender flags the installer**
This is a false positive common with unsigned Python executables.
Add an exclusion in Windows Security for the install folder:
`C:\Program Files\Meraki Config Manager\`

## Project structure

```text
auth/                 Encrypted profile store (PBKDF2 + Fernet)
config/               Settings dataclass
gui/
  v1/
    widgets/
      dashboard.py          Dashboard panel
      networks_panel.py     Networks table
      compare_panel.py      Compare Networks panel + PDF export
      copy_wizard.py        Copy Rules 5-step wizard
      group_policy_wizard.py  Group Policies 5-step wizard
      new_network_wizard.py 6-step New Network wizard
      activity_log.py       Activity log panel
meraki_client/        Meraki API wrapper with retry and NBAR direct PUT
rules/                VPN rule models, parsing, normalization and comparison
services/
  copy_service.py           VPN exclusion copy logic
  group_policy_service.py   Group Policy compare & copy logic
  compare_service.py        Cross-network diff report
  network_service.py        Network creation and config cloning
  workflow.py               Dry-run and deployment workflow
reporting/            Structured JSON logging
samples/              CSV, JSON and XLSX import examples
tests/                Unit tests (never contact Meraki)
main_client.py        Entry point — login dialog + main window
build.bat             Windows build script (produces installer)
meraki_client.spec    PyInstaller configuration
installer.iss         Inno Setup installer script
```
