"""Build the Windows app + installer.   Run on Windows:  python packaging\\windows\\build_windows.py
Requires: pip install -r requirements.txt pyinstaller      and Inno Setup 6 (iscc) for the installer."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
from version import get_version  # noqa: E402

VER = get_version()
assets = ROOT / "drivesync_iqbal" / "assets"

import PyInstaller.__main__ as pyinstaller  # noqa: E402

pyinstaller.run([
    "--noconfirm", "--clean", "--windowed",
    "--name", "DriveSyncIqbal",
    "--icon", str(assets / "drivesync-iqbal.ico"),
    "--paths", str(ROOT),
    "--add-data", f"{assets}{os.pathsep}drivesync_iqbal/assets",
    "--collect-data", "googleapiclient",
    "--distpath", str(ROOT / "build" / "win-dist"),
    "--workpath", str(ROOT / "build" / "win-work"),
    "--specpath", str(ROOT / "build"),
    str(ROOT / "packaging" / "windows" / "run_drivesync.py"),
])

(ROOT / "dist").mkdir(exist_ok=True)
shutil.make_archive(str(ROOT / "dist" / f"DriveSync-Iqbal-{VER}-portable-win64"), "zip",
                    str(ROOT / "build" / "win-dist"), "DriveSyncIqbal")
print("Portable ZIP created.")

iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if Path(iscc).exists() or shutil.which("iscc"):
    subprocess.check_call([iscc, f"/DAppVersion={VER}", str(ROOT / "packaging" / "windows" / "installer.iss")])
    print("Installer created in dist/")
else:
    print("Inno Setup not found - installer skipped (portable ZIP is ready). "
          "Install it from https://jrsoftware.org/isinfo.php")
