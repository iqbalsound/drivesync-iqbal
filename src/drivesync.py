#!/usr/bin/env python3
"""DriveSync by Iqbal - Google Drive <-> local folder sync for Linux."""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

APP_NAME = "DriveSync by Iqbal"          # <- change the app name here
APP_ID = "drivesync-iqbal"
SCOPES = ["https://www.googleapis.com/auth/drive"]
CFG_DIR = Path.home() / ".config" / APP_ID
TOKEN_FILE, CLIENT_FILE, SETTINGS_FILE = (CFG_DIR / n for n in
                                          ("token.json", "credentials.json", "settings.json"))
FOLDER_MIME = "application/vnd.google-apps.folder"
DEFAULTS = {"local": str(Path.home() / "GoogleDrive"), "drive_folder": "root",
            "interval": 15, "theme": "Light"}


# ---------------------------------------------------------------- settings
def load_settings():
    try:
        return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text())}
    except Exception:
        return dict(DEFAULTS)


def save_settings(s):
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(s, indent=2))


# ------------------------------------------------------------------- theme
def apply_theme(app, mode):
    app.setStyle("Fusion")
    if mode == "Dark":
        p, C = QtGui.QPalette(), QtGui.QColor
        p.setColor(p.Window, C(37, 37, 38));      p.setColor(p.WindowText, C(230, 230, 230))
        p.setColor(p.Base, C(30, 30, 30));        p.setColor(p.AlternateBase, C(45, 45, 48))
        p.setColor(p.Text, C(230, 230, 230));     p.setColor(p.Button, C(51, 51, 55))
        p.setColor(p.ButtonText, C(230, 230, 230)); p.setColor(p.ToolTipBase, C(60, 60, 60))
        p.setColor(p.ToolTipText, C(230, 230, 230)); p.setColor(p.Highlight, C(66, 133, 244))
        p.setColor(p.HighlightedText, C(255, 255, 255)); p.setColor(p.Link, C(138, 180, 248))
        app.setPalette(p)
    else:
        app.setPalette(app.style().standardPalette())


# ------------------------------------------------------------- sync engine
def iso_to_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def ts_to_iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Syncer:
    """Two-way sync, newest file wins. Deletions are NOT propagated (safe by design)."""

    def __init__(self, service, log):
        self.svc, self.log = service, log

    def children(self, pid):
        out, token = [], None
        while True:
            r = self.svc.files().list(
                q=f"'{pid}' in parents and trashed=false", pageToken=token, pageSize=1000,
                fields="nextPageToken, files(id,name,mimeType,modifiedTime)").execute()
            out += r["files"]
            token = r.get("nextPageToken")
            if not token:
                return {f["name"]: f for f in out}

    def sync(self, pid, local: Path):
        local.mkdir(parents=True, exist_ok=True)
        remote = self.children(pid)
        for name, f in remote.items():
            p = local / name
            if f["mimeType"] == FOLDER_MIME:
                self.sync(f["id"], p)
            elif f["mimeType"].startswith("application/vnd.google-apps"):
                self.log(f"Skipped (Google Doc/Sheet): {name}")
            else:
                rt = iso_to_ts(f["modifiedTime"])
                if not p.exists() or rt > p.stat().st_mtime + 2:
                    self.download(f["id"], p, rt)
                elif p.stat().st_mtime > rt + 2:
                    self.upload(p, pid, f["id"])
        for p in sorted(local.iterdir()):
            if p.name in remote or p.name.startswith("."):
                continue
            if p.is_dir():
                nf = self.svc.files().create(
                    body={"name": p.name, "mimeType": FOLDER_MIME, "parents": [pid]},
                    fields="id").execute()
                self.log(f"Created folder: {p.name}")
                self.sync(nf["id"], p)
            elif p.is_file():
                self.upload(p, pid, None)

    def download(self, fid, path, rt):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            dl = MediaIoBaseDownload(fh, self.svc.files().get_media(fileId=fid))
            done = False
            while not done:
                _, done = dl.next_chunk()
        os.utime(path, (rt, rt))
        self.log(f"Downloaded: {path.name}")

    def upload(self, path, pid, fid):
        body = {"modifiedTime": ts_to_iso(path.stat().st_mtime)}
        media = MediaFileUpload(str(path), resumable=True)
        if fid:
            self.svc.files().update(fileId=fid, body=body, media_body=media).execute()
        else:
            body.update(name=path.name, parents=[pid])
            self.svc.files().create(body=body, media_body=media).execute()
        self.log(f"Uploaded: {path.name}")


def get_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_FILE.exists():
                raise RuntimeError("credentials.json missing - click 'Import credentials.json'.")
            creds = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_FILE), SCOPES).run_local_server(port=0)
        CFG_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())
        TOKEN_FILE.chmod(0o600)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


class Worker(QtCore.QThread):
    message = QtCore.pyqtSignal(str)

    def __init__(self, settings):
        super().__init__()
        self.s = settings

    def run(self):
        try:
            self.message.emit("Sync started...")
            Syncer(get_service(), self.message.emit).sync(
                self.s["drive_folder"], Path(self.s["local"]).expanduser())
            self.message.emit("Sync finished.")
        except Exception as e:
            self.message.emit(f"ERROR: {e}")


# --------------------------------------------------------------------- GUI
class Window(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app, self.s, self.worker = app, load_settings(), None
        self.setWindowTitle(APP_NAME)
        fallback = Path(__file__).resolve().parent.parent / "assets" / f"{APP_ID}.svg"
        self.icon = QtGui.QIcon.fromTheme(APP_ID, QtGui.QIcon(str(fallback)))
        self.setWindowIcon(self.icon)
        self.resize(640, 480)

        title = QtWidgets.QLabel(f"<h2>{APP_NAME}</h2>")
        logo = QtWidgets.QLabel(); logo.setPixmap(self.icon.pixmap(40, 40))
        head = QtWidgets.QHBoxLayout(); head.addWidget(logo); head.addWidget(title, 1)

        self.local = QtWidgets.QLineEdit(self.s["local"])
        browse = QtWidgets.QPushButton("Browse..."); browse.clicked.connect(self.pick)
        row = QtWidgets.QHBoxLayout(); row.addWidget(self.local); row.addWidget(browse)
        self.folder = QtWidgets.QLineEdit(self.s["drive_folder"])
        self.folder.setToolTip("'root' = My Drive, or paste a Drive folder ID")
        self.interval = QtWidgets.QSpinBox(); self.interval.setRange(1, 1440)
        self.interval.setSuffix(" min"); self.interval.setValue(self.s["interval"])
        self.theme = QtWidgets.QComboBox(); self.theme.addItems(["Light", "Dark"])
        self.theme.setCurrentText(self.s["theme"])
        self.theme.currentTextChanged.connect(self.change_theme)

        form = QtWidgets.QFormLayout()
        form.addRow("Local folder:", row); form.addRow("Drive folder ID:", self.folder)
        form.addRow("Auto-sync every:", self.interval); form.addRow("Theme:", self.theme)

        b1 = QtWidgets.QPushButton("Import credentials.json"); b1.clicked.connect(self.import_creds)
        self.syncbtn = QtWidgets.QPushButton("Sync Now"); self.syncbtn.clicked.connect(self.sync_now)
        btns = QtWidgets.QHBoxLayout(); btns.addWidget(b1); btns.addWidget(self.syncbtn)
        self.logbox = QtWidgets.QPlainTextEdit(); self.logbox.setReadOnly(True)

        lay = QtWidgets.QVBoxLayout(self)
        for item in (head, form, btns):
            lay.addLayout(item)
        lay.addWidget(self.logbox)

        self.tray = QtWidgets.QSystemTrayIcon(self.icon, self)
        menu = QtWidgets.QMenu()
        menu.addAction("Open", self.showNormal); menu.addAction("Sync Now", self.sync_now)
        menu.addSeparator(); menu.addAction("Quit", self.quit)
        self.tray.setContextMenu(menu); self.tray.setToolTip(APP_NAME); self.tray.show()
        self.tray.activated.connect(lambda r: self.showNormal()
                                    if r == QtWidgets.QSystemTrayIcon.Trigger else None)
        self.timer = QtCore.QTimer(self); self.timer.timeout.connect(self.sync_now)
        self.timer.start(self.s["interval"] * 60000)

    def log(self, text):
        self.logbox.appendPlainText(f"[{datetime.now():%H:%M:%S}] {text}")

    def pick(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose local folder", self.local.text())
        if d:
            self.local.setText(d)

    def import_creds(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select credentials.json", "", "JSON (*.json)")
        if f:
            CFG_DIR.mkdir(parents=True, exist_ok=True)
            CLIENT_FILE.write_bytes(Path(f).read_bytes()); CLIENT_FILE.chmod(0o600)
            self.log("credentials.json imported.")

    def change_theme(self, mode):
        apply_theme(self.app, mode); self.persist()

    def persist(self):
        self.s.update(local=self.local.text(), drive_folder=self.folder.text() or "root",
                      interval=self.interval.value(), theme=self.theme.currentText())
        save_settings(self.s)
        self.timer.start(self.s["interval"] * 60000)

    def sync_now(self):
        if self.worker and self.worker.isRunning():
            return
        self.persist()
        self.syncbtn.setEnabled(False)
        self.worker = Worker(dict(self.s))
        self.worker.message.connect(self.log)
        self.worker.finished.connect(lambda: self.syncbtn.setEnabled(True))
        self.worker.start()

    def closeEvent(self, e):          # keep running in the tray
        e.ignore(); self.hide()

    def quit(self):
        self.persist(); self.tray.hide(); self.app.quit()


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)
    apply_theme(app, load_settings()["theme"])
    w = Window(app); w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
