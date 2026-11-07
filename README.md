# DriveSync by Iqbal

Google Drive sync client for **Linux** (DEB, RPM) and **Windows** (installer, portable ZIP).

## Features
- Selective sync: choose exactly which Drive folders to keep on your computer
- One-click "Sign in with Google" (no JSON file needed), or sign in via a link
- "Synced files" tab: tree view, copy / export as text tree or CSV
- Light and dark themes, system tray, auto-sync, Stop button

## Install
| System | File | Command |
|---|---|---|
| Debian / Ubuntu / Mint | `drivesync-iqbal_<ver>_all.deb` | `sudo apt install ./drivesync-iqbal_<ver>_all.deb` |
| Fedora / RHEL / Rocky | `drivesync-iqbal-<ver>-1.noarch.rpm` | `sudo dnf install ./drivesync-iqbal-<ver>-1.noarch.rpm` |
| Windows 10/11 | `DriveSync-Iqbal-<ver>-Setup.exe` (or the portable ZIP) | double-click |

## Using it
1. Click **Sign in with Google** and allow access.
2. Choose **Selected folders only** -> **Choose folders...** and tick folders (or pick **Entire My Drive**).
3. Click **Sync Now**. Open the **Synced files** tab to browse or export the list.

Sync rules: newest file wins; deletions are never propagated; Google Docs/Sheets/Slides are listed but not downloaded.

## For the maintainer
1. Create one OAuth client ("Desktop app") in Google Cloud Console with the Drive API enabled.
2. Put its ID/secret in `drivesync_iqbal/oauth_client.py`, **or** add the GitHub secrets
   `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` so CI injects them at build time.
3. Note: while the OAuth consent screen is in *Testing* mode, only listed test users can sign in and
   Google expires their sign-in after 7 days. Public use of the full-Drive scope requires Google's app
   verification. Power users can always load their own `credentials.json` (Advanced menu).

## Build
    python3 -m unittest discover -s tests          # tests
    ./packaging/linux/build_deb.sh                  # -> dist/*.deb
    ./packaging/linux/build_rpm.sh                  # -> dist/*.rpm   (needs rpmbuild)
    packaging\windows\build_windows.bat             # -> dist\*Setup.exe + portable ZIP (on Windows)

Or push a tag (`git tag -a v2.0.0 -m "v2.0.0" && git push origin v2.0.0`) and GitHub Actions builds
everything and attaches it to the release.

## Adding the Repo
	curl -fsSL https://YOUR_USERNAME.github.io/drivesync-apt/drivesync-iqbal.gpg \ | sudo tee /usr/share/keyrings/drivesync-iqbal.gpg > /dev/null

	echo "deb [signed-by=/usr/share/keyrings/drivesync-iqbal.gpg] https://YOUR_USERNAME.github.io/drivesync-apt stable main" \ | sudo tee /etc/apt/sources.list.d/drivesync-iqbal.list

	sudo apt update && sudo apt install drivesync-iqbal
