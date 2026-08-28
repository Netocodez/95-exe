VENV SETUP ON WINDOWS
python -m venv venv

.\venv\Scripts\Activate.ps1

pip install -r requirements.txt


# 2nd & 3rd 95 Analyzer — Windows Auto-Update & System Tray Setup Guide

## 1. Purpose

This guide explains how to implement and operate a reusable Windows auto-update system for a Python/Flask application packaged with Nuitka.

The solution provides:

- Centralized application versioning.
- GitHub Releases as the distribution channel.
- A small `update.json` manifest.
- Automatic and manual update checks.
- In-app update notifications.
- SHA-256 verification of downloaded update packages.
- A separate `updater.exe` so the running application can safely be replaced.
- Windows system-tray controls.
- A clean **Quit** action that shuts down the local Flask application.
- Preservation of application/user data during updates.
- Inno Setup for first-time installation.
- A repeatable release workflow that can also be reused in other Python desktop applications.

---

# 2. Architecture

The system has four major parts:

```text
                         GitHub
                           |
                 +---------+---------+
                 |                   |
             update.json       GitHub Release
                 |                   |
                 |              update ZIP
                 |                   |
                 +---------+---------+
                           |
                           v
                    Running Application
                           |
                 +---------+---------+
                 |                   |
           Update Checker        System Tray
                 |                   |
                 v                   v
             Flask UI          Open / Update / Quit
                 |
          New version found
                 |
                 v
          Download update ZIP
                 |
            SHA-256 verify
                 |
                 v
             updater.exe
                 |
        close main application
                 |
        replace application files
                 |
        preserve user data
                 |
             restart app
```

The important principle is:

> The main application never tries to overwrite itself. A separate updater process performs the replacement after the main application has exited.

---

# 3. Recommended Project Structure

A reusable implementation can use:

```text
project/
│
├── app/
│   ├── __init__.py
│   ├── templates/
│   ├── static/
│   └── ...
│
├── desktop/
│   └── tray.py
│
├── updater/
│   ├── checker.py
│   └── updater.py
│
├── version.py
├── run.py
├── build_windows.bat
├── installer.iss
├── prepare_release.py
├── requirements.txt
└── update.json
```

For another application, keep the same architecture and change the application-specific names, URLs, executable name, paths and UI integration.

---

# 4. Step 1 — Central Version File

Create:

```text
version.py
```

Example:

```python
__version__ = "1.0.0"

APP_NAME = "2nd & 3rd 95 Analyzer"

UPDATE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/"
    "netocodez/2nd-and-3rd-95-analysis/main/update.json"
)
```

## Why this matters

Do not maintain the application version independently in:

- `run.py`
- Inno Setup
- updater
- Flask UI
- GitHub
- installer

The version should have one source of truth.

For a new release:

```text
1.0.0
```

becomes:

```text
1.1.0
```

Then build the release.

---

# 5. Versioning Rules

Use semantic versioning where practical:

```text
MAJOR.MINOR.PATCH
```

Examples:

```text
1.0.0
1.0.1
1.1.0
2.0.0
```

Suggested meaning:

### PATCH

Bug fixes:

```text
1.0.0 -> 1.0.1
```

### MINOR

Backward-compatible features:

```text
1.0.1 -> 1.1.0
```

### MAJOR

Breaking changes:

```text
1.9.0 -> 2.0.0
```

---

# 6. Step 2 — Install Dependencies

Install:

```powershell
pip install pystray pillow requests
```

Add them to `requirements.txt`:

```text
pystray
Pillow
requests
```

If your application already uses these packages, avoid duplicate entries.

---

# 7. Step 3 — System Tray

Create:

```text
desktop/tray.py
```

The tray controller should provide:

```text
Open Analyzer
Check for Updates
-----------------
Quit
```

The tray is useful because your application is a local Flask server opened in a browser. The browser window belongs to Chrome/Edge, while the actual Flask process continues in the background.

The tray gives users direct control over the actual desktop application process.

## Expected Windows behavior

```text
Windows Taskbar
    |
    +-- Browser window
          |
          +-- 2nd & 3rd 95 Analyzer
```

and:

```text
Windows Notification Area
    |
    +-- Analyzer icon
```

Right-click:

```text
2nd & 3rd 95 Analyzer
----------------------
Open Analyzer
Check for Updates
----------------------
Quit
```

---

# 8. Taskbar vs System Tray

These are different Windows concepts.

## Taskbar

The browser or desktop window appears on the Windows taskbar.

## System Tray / Notification Area

The Python application can place an icon near the Windows clock.

For a browser-based Flask desktop application, use the system tray as the main control surface for the background process.

This means users do not have to open Task Manager just to quit the application.

---

# 9. Step 4 — Update Checker

Create:

```text
updater/checker.py
```

Its responsibilities are:

1. Download `update.json`.
2. Read the latest version.
3. Compare it with the installed version.
4. Return release information if an update exists.
5. Download the update ZIP when requested.
6. Verify SHA-256.
7. Launch `updater.exe`.
8. Exit the main application.

The update checker should fail safely.

If GitHub cannot be reached:

```text
Application continues normally.
```

An unavailable update server must never prevent the analyzer from starting.

---

# 10. Update Manifest

Create:

```text
update.json
```

Example:

```json
{
    "version": "1.1.0",
    "release_date": "2026-08-27",
    "mandatory": false,
    "download_url": "https://github.com/netocodez/2nd-and-3rd-95-analysis/releases/download/v1.1.0/2nd-and-3rd-95-analysis-v1.1.0.zip",
    "sha256": "PUT_REAL_SHA256_HERE",
    "release_notes": [
        "Improved 2nd 95 processing",
        "Improved 3rd 95 processing",
        "Bug fixes"
    ]
}
```

## Fields

### version

Latest available version.

### release_date

Release date.

### mandatory

Controls whether the update is optional or mandatory.

### download_url

Direct GitHub Release asset URL.

### sha256

SHA-256 hash of the exact ZIP.

### release_notes

Information displayed to users.

---

# 11. Version Comparison

Do not compare versions as strings:

```python
"1.10.0" > "1.9.0"
```

String comparisons can produce incorrect results.

Compare numeric components:

```text
1.10.0
  |
  +-- 1
  +-- 10
  +-- 0
```

against:

```text
1.9.0
```

as:

```text
[1, 10, 0] > [1, 9, 0]
```

For more sophisticated projects, use a semantic-versioning library.

---

# 12. Step 5 — Download Verification

The update ZIP must be verified before installation.

Process:

```text
Download ZIP
     |
     v
Calculate SHA-256
     |
     v
Compare against update.json
     |
   +---+---+
   |       |
 MATCH   DIFFERENT
   |       |
   v       v
Install  Reject
```

If the hash does not match:

```text
Do not install the update.
Delete the download.
Tell the user the update could not be verified.
```

SHA-256 protects against corrupted or incomplete downloads.

---

# 13. SHA-256 Generation

On Windows PowerShell:

```powershell
Get-FileHash .\2nd-and-3rd-95-analysis-v1.1.0.zip -Algorithm SHA256
```

Example:

```text
Algorithm Hash                                     Path
--------- ----                                     ----
SHA256    ABC123...                                update.zip
```

Copy the hash into:

```json
"sha256": "ABC123..."
```

The included release preparation tooling can also be used to calculate the hash automatically.

---

# 14. Step 6 — Separate Updater

Create:

```text
updater/updater.py
```

The updater is deliberately separate from Flask.

It performs:

```text
1. Receive target directory.
2. Receive update ZIP.
3. Wait for main application to close.
4. Extract ZIP to temporary storage.
5. Validate extracted structure.
6. Replace application files.
7. Preserve user data.
8. Clean temporary files.
9. Start the new application.
```

---

# 15. Why a Separate Updater Is Required

Windows normally locks an executable while it is running.

Therefore this is unsafe:

```text
2nd-and-3rd-95-analysis.exe
       |
       +-- tries to replace
             itself
```

Instead:

```text
Main application
       |
       +-- starts updater.exe
       |
       +-- exits
                |
                v
           updater.exe
                |
                +-- replaces application
                |
                +-- starts application
```

---

# 16. Important Windows Permission Issue

If the application is installed under:

```text
C:\Program Files\
```

Windows can require administrator permission to update files.

There are two approaches.

## Option A — Program Files

Use UAC elevation for the updater.

Advantages:

- Traditional Windows installation.
- Shared machine installation.

Disadvantage:

- User may see a Windows permission prompt.

## Option B — Per-user installation

Install under a user-writable directory such as:

```text
%LOCALAPPDATA%\2nd & 3rd 95 Analyzer\
```

Advantages:

- Smooth updates.
- No administrator rights for ordinary updates.

For many desktop utilities, per-user installation is a good choice.

---

# 17. Never Depend on `os.getcwd()`

Do not assume:

```python
os.getcwd()
```

is the application directory.

Windows can start an executable with a different working directory.

For the packaged executable, determine the executable directory from:

```python
Path(sys.executable).resolve().parent
```

Keep application paths based on that location or on an explicitly configured data directory.

---

# 18. Separate Application Files from User Data

This is one of the most important design decisions.

Application files:

```text
2nd & 3rd 95 Analyzer/
    2nd-and-3rd-95-analysis.exe
    updater.exe
    DLLs/
    application resources/
```

User data should preferably live separately:

```text
%APPDATA%\2nd & 3rd 95 Analyzer\
    config/
    database/
    uploads/
    outputs/
    logs/
```

The updater can then replace the entire application directory without touching user data.

This is safer than maintaining a growing list of folders to exclude.

---

# 19. Protect Databases

If your application has SQLite or another local database, do not put the live database inside the GitHub update ZIP.

Bad:

```text
release.zip
    analyzer.db
```

Good:

```text
Installed application
    executable
    DLLs
    resources

User data
    analyzer.db
```

Updates should never replace the user's live database unless the update system explicitly implements database migrations.

---

# 20. Step 7 — Integrate into `run.py`

Your main entry point should coordinate:

```text
Flask
Browser
Tray
Updater
```

Conceptually:

```python
app = create_app()

start Flask in background
start tray
open browser
```

The Flask server should use:

```python
debug=False
use_reloader=False
```

for the packaged application.

Do not use Flask's development reloader in production desktop builds because it can start duplicate processes.

---

# 21. Automatic Update Check

A recommended startup sequence is:

```text
Application starts
       |
       v
License initialization
       |
       v
Flask starts
       |
       v
Browser opens
       |
       v
Tray starts
       |
       v
Update check runs in background
```

Do not block application startup waiting for GitHub.

If GitHub takes 20 seconds to respond, the application should still open immediately.

---

# 22. Recommended Update Frequency

For a local analyzer, reasonable options are:

- once at startup
- manual check from tray
- manual check from About/Settings

You can later add a periodic check such as every 6–12 hours.

Avoid checking GitHub every few seconds.

---

# 23. User Update Flow

When no update exists:

```text
Version 1.0.0
✓ You are using the latest version.
```

When an update exists:

```text
Update Available

Current version: 1.0.0
New version:     1.1.0

[ Update Now ] [ Later ]
```

The update should not begin automatically without user confirmation unless the application is specifically configured for unattended updates.

---

# 24. Mandatory Updates

The manifest can contain:

```json
"mandatory": true
```

For example:

```text
A critical update is required.

Version 1.1.0 must be installed before continuing.

[ Update Now ]
```

Use this sparingly.

Optional updates should normally use:

```json
"mandatory": false
```

---

# 25. Release ZIP Structure

The GitHub Release ZIP should contain the contents required by the packaged application.

Example:

```text
2nd-and-3rd-95-analysis-v1.1.0.zip
│
├── 2nd-and-3rd-95-analysis.exe
├── updater.exe
├── application DLLs
├── app/
├── static/
├── templates/
└── other Nuitka resources
```

Do not include:

```text
uploads/
outputs/
live database
logs
temporary files
```

unless those files are genuinely part of the application distribution.

---

# 26. Building with Nuitka

The exact Nuitka command depends on the project's dependencies.

A typical main application build is:

```powershell
python -m nuitka `
  --msvc=latest `
  --standalone `
  --windows-console-mode=disable `
  --enable-plugin=tk-inter `
  --include-data-dir=app/templates=app/templates `
  --include-data-dir=app/static=app/static `
  run.py
```

Adjust this to the actual resources used by the application.

For the updater, build a separate standalone executable.

The final build process should place the updater into the application distribution in a controlled way.

Do not blindly copy a second standalone environment into the main distribution.

---

# 27. Why the Updater Should Be Small

The updater does not need:

- Flask
- pandas
- NumPy
- Chart.js
- application business logic
- database libraries

Ideally it only needs the Python standard library plus the minimum Windows functionality required.

This means it remains independent of changes to the main application's dependencies.

---

# 28. Inno Setup

Inno Setup remains the installer for:

```text
First installation
```

It should not be confused with the normal update mechanism.

Initial user:

```text
Inno Setup
    |
    v
Install application
```

Existing user:

```text
Application
    |
    v
GitHub update
    |
    v
updater.exe
```

This gives you two separate workflows.

---

# 29. First-Time Installation

The normal process remains:

```text
Download installer.exe
       |
       v
Run installer
       |
       v
Install application
       |
       v
Create Start Menu / shortcut
       |
       v
Launch analyzer
```

After that, users should normally receive updates inside the application.

---

# 30. When You Still Need the Installer

Use a new Inno Setup installer when:

- The application cannot start because of a severe packaging issue.
- The updater architecture itself changes.
- The updater executable is missing or broken.
- Major installation requirements change.
- A major migration requires administrator-level installation.
- You want to provide a clean installation on a new computer.

For ordinary feature and bug-fix releases, use the updater.

---

# 31. GitHub Repository Setup

Create or use a repository such as:

```text
https://github.com/netocodez/2nd-and-3rd-95-analysis
```

The repository can contain:

```text
source code
build scripts
installer configuration
update.json
documentation
```

Do not commit large generated `run.dist` folders to normal source control unless there is a specific reason to do so.

Use GitHub Releases for compiled distribution packages.

---

# 32. GitHub Release Process

For version:

```text
1.1.0
```

create:

```text
v1.1.0
```

Git tag/release.

Upload:

```text
2nd-and-3rd-95-analysis-v1.1.0.zip
```

to the GitHub Release.

The release URL will resemble:

```text
https://github.com/OWNER/REPOSITORY/releases/download/v1.1.0/FILE.zip
```

Use the exact generated URL in `update.json`.

---

# 33. Update Manifest Workflow

After creating the GitHub Release:

1. Build ZIP.
2. Calculate SHA-256.
3. Create/update `update.json`.
4. Set the new version.
5. Set the exact Release download URL.
6. Set the calculated SHA-256.
7. Add release notes.
8. Commit `update.json`.
9. Push to GitHub.

Existing users then discover the new release.

---

# 34. Example `update.json`

```json
{
    "version": "1.1.0",
    "release_date": "2026-08-28",
    "mandatory": false,
    "download_url": "https://github.com/OWNER/REPOSITORY/releases/download/v1.1.0/application-v1.1.0.zip",
    "sha256": "REAL_SHA256_HASH",
    "release_notes": [
        "Improved analyzer performance",
        "Fixed report generation issue",
        "Improved user interface"
    ]
}
```

Never use a placeholder hash in production.

---

# 35. Complete Release Checklist

Before publishing:

```text
[ ] Update version.py
[ ] Test application normally
[ ] Test login/license
[ ] Test uploads
[ ] Test report generation
[ ] Test database
[ ] Build with Nuitka
[ ] Confirm executable starts
[ ] Confirm Flask starts
[ ] Confirm browser opens
[ ] Confirm tray icon appears
[ ] Confirm tray Quit works
[ ] Confirm updater.exe exists
[ ] Create release ZIP
[ ] Ensure user data is excluded
[ ] Calculate SHA-256
[ ] Create GitHub Release
[ ] Upload ZIP
[ ] Update update.json
[ ] Commit update.json
[ ] Push to GitHub
[ ] Test update from previous version
```

---

# 36. Most Important Test

Do not only test:

```text
v1.1.0 -> v1.1.0
```

Install an actual older build:

```text
v1.0.0
```

Then publish:

```text
v1.1.0
```

Run the old application.

Verify:

```text
GitHub detects v1.1.0
       |
       v
User clicks Update
       |
       v
ZIP downloads
       |
       v
SHA-256 passes
       |
       v
Application closes
       |
       v
Updater replaces files
       |
       v
Application restarts
       |
       v
Version shows 1.1.0
```

Then verify the user's data still exists.

---

# 37. Test Update Failure

Also test:

- Internet disconnected.
- GitHub unavailable.
- Invalid `update.json`.
- Incorrect SHA-256.
- Interrupted download.
- Corrupt ZIP.
- User closes the updater.
- Application cannot be restarted.
- Insufficient permissions.
- Existing user data.

The application should fail safely and remain usable.

---

# 38. Recommended Rollback Strategy

For production software, an updater should ideally keep a backup of the previous application version.

Conceptually:

```text
Before update:

application/
backup/
```

During update:

```text
application/
       |
       +-- backup old files
       |
       +-- install new files
```

If installation fails:

```text
restore backup
```

This is particularly useful for commercial deployments.

---

# 39. Security Recommendations

The minimum system should use:

```text
HTTPS
+
SHA-256
```

For stronger production security, add:

```text
HTTPS
+
SHA-256
+
digitally signed update/package
+
code-signed Windows executables
```

SHA-256 confirms file integrity but does not independently prove who published the file.

---

# 40. GitHub Repository Security

Keep secrets out of:

```text
version.py
update.json
source code
```

Do not put:

```text
GitHub personal access tokens
Paystack secret keys
API secrets
private signing keys
```

into the application.

The client only needs public release information.

---

# 41. Reusing This System in Another Python Application

For another Flask/Nuitka application:

### Copy

```text
desktop/
updater/
version.py
prepare_release.py
build_windows.bat
```

### Change

```text
APP_NAME
UPDATE_MANIFEST_URL
executable name
GitHub repository
user-data directory
application-specific resources
```

Then integrate the tray and checker into that application's `run.py`.

The architecture remains the same.

---

# 42. Generic Version File

For another application:

```python
__version__ = "1.0.0"

APP_NAME = "My Application"

UPDATE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/"
    "OWNER/REPOSITORY/main/update.json"
)
```

---

# 43. Generic Manifest

```json
{
    "version": "1.1.0",
    "release_date": "2026-08-28",
    "mandatory": false,
    "download_url": "https://github.com/OWNER/REPOSITORY/releases/download/v1.1.0/application-v1.1.0.zip",
    "sha256": "HASH",
    "release_notes": [
        "New features",
        "Bug fixes"
    ]
}
```

---

# 44. Generic Application Architecture

Any Python desktop application can use:

```text
main.py
   |
   +-- Application
   |
   +-- Flask/FastAPI/etc.
   |
   +-- Browser/Desktop UI
   |
   +-- Tray
   |
   +-- Update checker
              |
              v
          updater.exe
```

The web framework is not the important part.

The important part is the separation between:

```text
Main application
```

and:

```text
Updater process
```

---

# 45. Common Mistakes to Avoid

## Mistake 1 — Updating while the EXE is running

Do not do:

```text
main.exe -> overwrite main.exe
```

Use `updater.exe`.

## Mistake 2 — Storing user data in the release ZIP

This can overwrite user data.

## Mistake 3 — Using `os.getcwd()`

Use a reliable application/data path.

## Mistake 4 — Replacing the database during updates

Use database migrations when schema changes.

## Mistake 5 — Checking GitHub synchronously during startup

A slow network should not prevent the application from starting.

## Mistake 6 — Treating SHA-256 as publisher authentication

It verifies integrity, not publisher identity.

## Mistake 7 — Updating `update.json` before uploading the Release

Users can receive a manifest that points to a package that does not yet exist.

Publish the Release first, then update the manifest.

## Mistake 8 — Testing only the newest installation

Always test:

```text
old version -> new version
```

---

# 46. Recommended Final Architecture

For a production-quality Python/Nuitka application:

```text
                 GitHub
                   |
           +-------+-------+
           |               |
      update.json       Releases
           |               |
           |             ZIP
           |               |
           +-------+-------+
                   |
                   v
             Main App
                   |
        +----------+----------+
        |                     |
     Flask/UI               Tray
        |                     |
        |              Open / Update / Quit
        |
    Update checker
        |
        v
   Download ZIP
        |
   SHA-256 verify
        |
        v
    updater.exe
        |
   Close Main App
        |
   Backup old files
        |
   Install new files
        |
   Preserve user data
        |
      Restart
```

This is the architecture to reuse across future Python/Nuitka applications.

---

# 47. Final Deployment Model

For the **2nd & 3rd 95 Analyzer**:

### New computer

```text
Inno Setup installer
        ↓
Initial installation
```

### Existing computer

```text
Application
        ↓
GitHub update check
        ↓
Update available
        ↓
User confirms
        ↓
Updater
        ↓
Application restarts
```

### User controls

```text
Taskbar
    → browser/application window

System tray
    → Open
    → Check for Updates
    → Quit
```

The result is a normal desktop-software experience without requiring users to uninstall and reinstall for ordinary updates.
