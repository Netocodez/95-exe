# 2nd & 3rd 95 Analyzer - Windows Updates and System Tray

This project now supports:

- Central application versioning in `version.py`.
- GitHub Release based in-app update notifications.
- SHA-256 verification of downloaded update packages.
- A separate `updater.exe` process so the running application can be replaced safely.
- Windows system-tray controls: Open Analyzer, Check for Updates and Quit.
- User data separation through `utils/paths.py`.
- Inno Setup packaging for the initial installation.

## How an update works

1. The installed application starts.
2. The web UI checks `update.json` on GitHub.
3. If GitHub reports a newer semantic version, the UI shows an update notification.
4. The user clicks **Update Now**.
5. The application downloads the ZIP to a writable staging directory under `%LOCALAPPDATA%`.
6. The SHA-256 hash is checked against `update.json`.
7. `updater.exe` is started with the installation directory, update ZIP and current process ID.
8. The main application closes.
9. `updater.exe` waits for the main process to release file locks.
10. The ZIP is safely extracted and application files are replaced.
11. User data is not replaced.
12. The updated executable is restarted.

## GitHub Release workflow

For version `1.1.0`:

```text
1. Change version.py:
   __version__ = "1.1.0"

2. Run:
   build_windows.bat

3. This creates:
   2nd-and-3rd-95-analysis-v1.1.0.zip

4. Create GitHub Release:
   Tag: v1.1.0

5. Upload the ZIP.

6. Calculate the SHA-256 hash:
   certutil -hashfile 2nd-and-3rd-95-analysis-v1.1.0.zip SHA256

7. Update update.json:
   {
     "version": "1.1.0",
     "release_date": "YYYY-MM-DD",
     "mandatory": false,
     "download_url": "https://github.com/netocodez/2nd-and-3rd-95-analysis/releases/download/v1.1.0/2nd-and-3rd-95-analysis-v1.1.0.zip",
     "sha256": "THE_EXACT_SHA256_HASH",
     "release_notes": ["...", "..."]
   }

8. Commit and push update.json to main.
```

## Important packaging rule

The update ZIP deliberately excludes `updater.exe`. The updater cannot safely overwrite the executable that is currently running. The updater is therefore shipped/updated through the Inno Setup installer.

If the updater implementation itself changes, publish a new installer as well as the application update package.

## User data

The application already uses `utils/paths.py` to place writable data in:

```text
Windows:
%LOCALAPPDATA%\2NDAND95\
    outputs\
    uploads\
    temp\
    logs\

Other environments:
<working-directory>\data\
```

The updater also excludes common user-data directories (`uploads`, `outputs`, `config`, `data`, `logs`) as a safety measure.

Do not put a database, user configuration, uploads or generated reports inside the GitHub update ZIP.

## System tray

On Windows desktop mode, the application creates a notification-area icon. Right-clicking it provides:

- Open Analyzer
- Check for Updates
- Quit

The browser remains visible on the Windows taskbar as normal. The tray provides the reliable background-app **Quit** action.

## Development testing

You can test update detection without publishing a real release by temporarily changing `update.json` to a higher version and pointing `download_url` at a test ZIP with a correct SHA-256 hash.

Do not use a fake SHA-256 value: the client intentionally rejects packages whose hash does not match.

## Initial installer

`installer.iss` is still the recommended mechanism for first-time installation. The automatic updater is for existing installations and does not require uninstall/reinstall.

## Automatic manifest generation

After uploading the ZIP to GitHub Releases, you can generate the exact SHA-256 and update `update.json` with:

```powershell
python prepare_release.py 2nd-and-3rd-95-analysis-v1.1.0.zip `
  --download-url "https://github.com/netocodez/2nd-and-3rd-95-analysis/releases/download/v1.1.0/2nd-and-3rd-95-analysis-v1.1.0.zip" `
  --note "Improved 2nd 95 processing" `
  --note "Improved 3rd 95 processing" `
  --note "Bug fixes"
```

If the release is mandatory, add `--mandatory`.
