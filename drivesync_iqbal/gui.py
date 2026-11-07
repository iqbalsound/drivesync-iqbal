"""Qt GUI for DriveSync by Iqbal."""
import sys
from datetime import datetime
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

from . import __version__, auth, config, treeutil
from .config import APP_ID, APP_NAME
from .syncer import SyncAborted, Syncer, list_folders, safe_name


# ------------------------------------------------------------------- theme
def apply_theme(app, mode):
    app.setStyle("Fusion")
    if mode == "Dark":
        p, C = QtGui.QPalette(), QtGui.QColor
        p.setColor(p.Window, C(37, 37, 38));        p.setColor(p.WindowText, C(230, 230, 230))
        p.setColor(p.Base, C(30, 30, 30));          p.setColor(p.AlternateBase, C(45, 45, 48))
        p.setColor(p.Text, C(230, 230, 230));       p.setColor(p.Button, C(51, 51, 55))
        p.setColor(p.ButtonText, C(230, 230, 230)); p.setColor(p.ToolTipBase, C(60, 60, 60))
        p.setColor(p.ToolTipText, C(230, 230, 230)); p.setColor(p.Highlight, C(66, 133, 244))
        p.setColor(p.HighlightedText, C(255, 255, 255)); p.setColor(p.Link, C(138, 180, 248))
        p.setColor(QtGui.QPalette.Disabled, p.Text, C(120, 120, 120))
        p.setColor(QtGui.QPalette.Disabled, p.ButtonText, C(120, 120, 120))
        app.setPalette(p)
    else:
        app.setPalette(app.style().standardPalette())


def app_icon():
    return QtGui.QIcon.fromTheme(APP_ID, QtGui.QIcon(str(config.ASSETS / f"{APP_ID}.png")))


# ----------------------------------------------------------------- workers
class SyncWorker(QtCore.QThread):
    message = QtCore.pyqtSignal(str)
    items = QtCore.pyqtSignal(list)

    def __init__(self, settings):
        super().__init__()
        self.s, self._stop = settings, False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            self.message.emit("Sync started...")
            syn = Syncer(auth.get_service(), self.message.emit, lambda: self._stop)
            syn.run(self.s["mode"], self.s["local"], self.s["selected"])
            c = syn.counts
            self.items.emit(syn.items)
            self.message.emit(f"Sync finished: {c['downloaded']} downloaded, {c['uploaded']} "
                              f"uploaded, {c['unchanged']} up to date, {c['skipped']} skipped.")
        except SyncAborted:
            self.message.emit("Sync stopped.")
        except Exception as e:
            self.message.emit(f"ERROR: {e}")


class AuthWorker(QtCore.QThread):
    link = QtCore.pyqtSignal(str)
    ok = QtCore.pyqtSignal(str)
    fail = QtCore.pyqtSignal(str)

    def __init__(self, use_link):
        super().__init__()
        self.use_link = use_link

    def run(self):
        try:
            auth.sign_in(self.link.emit if self.use_link else None)
            self.ok.emit(auth.account_email())
        except Exception as e:
            self.fail.emit(str(e))


# ----------------------------------------------------------------- dialogs
class LinkDialog(QtWidgets.QDialog):
    def __init__(self, parent, url):
        super().__init__(parent)
        self.url = url
        self.setWindowTitle("Sign in using a link")
        self.resize(560, 200)
        lay = QtWidgets.QVBoxLayout(self)
        msg = QtWidgets.QLabel(
            "Open this link in any browser or browser profile <b>on this computer</b>, sign in "
            "to Google and allow access. This window closes automatically when you are done.")
        msg.setWordWrap(True)
        box = QtWidgets.QLineEdit(url)
        box.setReadOnly(True)
        copy = QtWidgets.QPushButton("Copy link")
        copy.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(url))
        opn = QtWidgets.QPushButton("Open in default browser")
        opn.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(url)))
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.close)
        row = QtWidgets.QHBoxLayout()
        for b in (copy, opn, close):
            row.addWidget(b)
        for w in (msg, box):
            lay.addWidget(w)
        lay.addLayout(row)


class FolderPicker(QtWidgets.QDialog):
    """Lazy-loading tree of Drive folders with check boxes (selective sync)."""
    ROLE_ID = Qt.UserRole
    ROLE_LOADED = Qt.UserRole + 1

    def __init__(self, parent, selected):
        super().__init__(parent)
        self.setWindowTitle("Choose folders to sync")
        self.resize(540, 580)
        self.prev_local = {s["id"]: s["local"] for s in selected}
        self.sel = {s["id"]: s["name"] for s in selected}
        self._busy = False
        self.svc = auth.get_service()

        lay = QtWidgets.QVBoxLayout(self)
        hint = QtWidgets.QLabel("Tick the folders you want on this computer. Ticking a folder "
                                "includes everything inside it. Use the arrows to open folders "
                                "and pick sub-folders.")
        hint.setWordWrap(True)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.count = QtWidgets.QLabel()
        box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok |
                                         QtWidgets.QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(hint)
        lay.addWidget(self.tree, 1)
        lay.addWidget(self.count)
        lay.addWidget(box)

        self.tree.itemExpanded.connect(self._load)
        self.tree.itemChanged.connect(self._changed)
        self._busy = True
        root = QtWidgets.QTreeWidgetItem(self.tree, ["My Drive"])
        root.setData(0, self.ROLE_ID, "root")
        root.setData(0, self.ROLE_LOADED, False)
        QtWidgets.QTreeWidgetItem(root, ["Loading..."])
        self._busy = False
        root.setExpanded(True)
        self._update_count()

    def _load(self, item):
        if item.data(0, self.ROLE_LOADED):
            return
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            folders = list_folders(self.svc, item.data(0, self.ROLE_ID))
        except Exception as e:
            QtWidgets.QApplication.restoreOverrideCursor()
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Could not list folders:\n{e}")
            return
        QtWidgets.QApplication.restoreOverrideCursor()
        self._busy = True
        try:
            item.takeChildren()
            for fid, name in folders:
                ch = QtWidgets.QTreeWidgetItem(item, [name])
                ch.setFlags(ch.flags() | Qt.ItemIsUserCheckable)
                ch.setCheckState(0, Qt.Checked if fid in self.sel else Qt.Unchecked)
                ch.setData(0, self.ROLE_ID, fid)
                ch.setData(0, self.ROLE_LOADED, False)
                QtWidgets.QTreeWidgetItem(ch, ["Loading..."])
            if not folders:
                QtWidgets.QTreeWidgetItem(item, ["(no sub-folders)"])
            item.setData(0, self.ROLE_LOADED, True)
        finally:
            self._busy = False

    def _changed(self, item, _col):
        fid = item.data(0, self.ROLE_ID)
        if self._busy or fid in (None, "root"):
            return
        if item.checkState(0) == Qt.Checked:
            self.sel[fid] = item.text(0)
        else:
            self.sel.pop(fid, None)
        self._update_count()

    def _update_count(self):
        self.count.setText(f"{len(self.sel)} folder(s) selected")

    def selected(self):
        used, out = set(), []
        for fid, name in self.sel.items():
            base = safe_name(name)
            loc = self.prev_local.get(fid, base)
            n = 2
            while loc.lower() in used:
                loc = f"{base} ({n})"
                n += 1
            used.add(loc.lower())
            out.append({"id": fid, "name": name, "local": loc})
        return out


# ------------------------------------------------------------- main window
class Window(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.s = config.load_settings()
        self.sync_worker = self.auth_worker = self.link_dlg = None
        m = config.load_manifest()
        self.items = m.get("items", [])
        self.manifest_time = m.get("time", "never")
        self.icon = app_icon()
        self.setWindowTitle(f"{APP_NAME}  v{__version__}")
        self.setWindowIcon(self.icon)
        self.resize(760, 620)

        logo = QtWidgets.QLabel()
        logo.setPixmap(self.icon.pixmap(40, 40))
        head = QtWidgets.QHBoxLayout()
        head.addWidget(logo)
        head.addWidget(QtWidgets.QLabel(f"<h2>{APP_NAME}</h2>"), 1)
        head.addWidget(QtWidgets.QLabel(f"v{__version__}"))

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._build_sync_tab(), "Sync")
        self.tabs.addTab(self._build_files_tab(), "Synced files")
        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(head)
        lay.addWidget(self.tabs)

        self._build_tray()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(lambda: self.sync_now(auto=True))
        self.timer.start(self.s["interval"] * 60000)
        self.update_account_ui()
        self.update_mode_ui()
        self.refresh_tree()

    # ---- UI construction
    def _build_sync_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)

        acct = QtWidgets.QGroupBox("Google account")
        self.acct_label = QtWidgets.QLabel()
        self.btn_in = QtWidgets.QPushButton("Sign in with Google")
        self.btn_in.clicked.connect(lambda: self.sign_in(False))
        self.btn_link = QtWidgets.QPushButton("Sign in using a link")
        self.btn_link.setToolTip("Shows the sign-in link so you can open it in any browser "
                                 "or profile on this computer.")
        self.btn_link.clicked.connect(lambda: self.sign_in(True))
        self.btn_out = QtWidgets.QPushButton("Sign out")
        self.btn_out.clicked.connect(self.sign_out)
        adv = QtWidgets.QToolButton()
        adv.setText("Advanced")
        adv.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(adv)
        menu.addAction("Use my own credentials.json...", self.import_creds)
        menu.addAction("Remove my credentials.json", self.remove_creds)
        adv.setMenu(menu)
        r = QtWidgets.QHBoxLayout()
        for b in (self.btn_in, self.btn_link, self.btn_out, adv):
            r.addWidget(b)
        v = QtWidgets.QVBoxLayout(acct)
        v.addWidget(self.acct_label)
        v.addLayout(r)
        lay.addWidget(acct)

        box = QtWidgets.QGroupBox("What to sync")
        self.local = QtWidgets.QLineEdit(self.s["local"])
        browse = QtWidgets.QPushButton("Browse...")
        browse.clicked.connect(self.pick_local)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.local)
        row.addWidget(browse)
        self.rb_sel = QtWidgets.QRadioButton("Selected folders only")
        self.rb_all = QtWidgets.QRadioButton("Entire My Drive")
        (self.rb_sel if self.s["mode"] == "selected" else self.rb_all).setChecked(True)
        self.rb_sel.toggled.connect(lambda _checked: self.update_mode_ui())
        self.btn_choose = QtWidgets.QPushButton("Choose folders...")
        self.btn_choose.clicked.connect(self.choose_folders)
        self.sel_label = QtWidgets.QLabel()
        self.sel_label.setWordWrap(True)
        mrow = QtWidgets.QHBoxLayout()
        mrow.addWidget(self.rb_sel)
        mrow.addWidget(self.btn_choose)
        mrow.addWidget(self.rb_all)
        mrow.addStretch(1)
        self.interval = QtWidgets.QSpinBox()
        self.interval.setRange(1, 1440)
        self.interval.setSuffix(" min")
        self.interval.setValue(self.s["interval"])
        self.theme = QtWidgets.QComboBox()
        self.theme.addItems(["Light", "Dark"])
        self.theme.setCurrentText(self.s["theme"])
        self.theme.currentTextChanged.connect(self.change_theme)
        form = QtWidgets.QFormLayout()
        form.addRow("Local folder:", row)
        form.addRow("Mode:", mrow)
        form.addRow("", self.sel_label)
        form.addRow("Auto-sync every:", self.interval)
        form.addRow("Theme:", self.theme)
        box.setLayout(form)
        lay.addWidget(box)

        self.btn_sync = QtWidgets.QPushButton("Sync Now")
        self.btn_sync.clicked.connect(lambda: self.sync_now())
        self.btn_stop = QtWidgets.QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(lambda: self.sync_worker and self.sync_worker.stop())
        brow = QtWidgets.QHBoxLayout()
        brow.addWidget(self.btn_sync)
        brow.addWidget(self.btn_stop)
        lay.addLayout(brow)
        self.logbox = QtWidgets.QPlainTextEdit()
        self.logbox.setReadOnly(True)
        lay.addWidget(self.logbox, 1)
        return w

    def _build_files_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        self.files_info = QtWidgets.QLabel()
        self.files = QtWidgets.QTreeWidget()
        self.files.setHeaderLabels(["Name", "Status", "Size", "Modified"])
        self.files.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.files.setColumnWidth(1, 90)
        self.files.setColumnWidth(2, 170)
        self.files.setColumnWidth(3, 130)
        self.files.itemDoubleClicked.connect(self.open_item)
        row = QtWidgets.QHBoxLayout()
        for text, fn in (("Expand all", self.files.expandAll),
                         ("Collapse all", self.files.collapseAll),
                         ("Copy as text tree", self.copy_tree),
                         ("Export...", self.export_tree)):
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        lay.addWidget(self.files_info)
        lay.addWidget(self.files, 1)
        lay.addLayout(row)
        return w

    def _build_tray(self):
        self.tray = QtWidgets.QSystemTrayIcon(self.icon, self)
        menu = QtWidgets.QMenu()
        menu.addAction("Open", self.showNormal)
        menu.addAction("Sync Now", lambda: self.sync_now())
        menu.addSeparator()
        menu.addAction("Quit", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(lambda r: self.showNormal()
                                    if r == QtWidgets.QSystemTrayIcon.Trigger else None)
        self.tray.show()

    # ---- helpers
    def log(self, text):
        self.logbox.appendPlainText(f"[{datetime.now():%H:%M:%S}] {text}")

    def persist(self):
        self.s.update(local=self.local.text(), interval=self.interval.value(),
                      theme=self.theme.currentText(),
                      mode="selected" if self.rb_sel.isChecked() else "all")
        config.save_settings(self.s)
        self.timer.start(self.s["interval"] * 60000)

    def pick_local(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose local folder", self.local.text())
        if d:
            self.local.setText(d)

    def change_theme(self, mode):
        apply_theme(self.app, mode)
        self.persist()

    # ---- account
    def update_account_ui(self):
        signed = auth.is_signed_in()
        if signed:
            text = f"Signed in as <b>{self.s.get('account') or 'your Google account'}</b>"
        else:
            text = "Not signed in"
        if auth.using_custom_credentials():
            text += "  (using your own credentials.json)"
        self.acct_label.setText(text)
        self.btn_in.setEnabled(not signed)
        self.btn_link.setEnabled(not signed)
        self.btn_out.setEnabled(signed)

    def sign_in(self, use_link):
        if self.auth_worker and self.auth_worker.isRunning():
            return
        self.auth_worker = AuthWorker(use_link)
        self.auth_worker.link.connect(self.show_link)
        self.auth_worker.ok.connect(self.signed_in)
        self.auth_worker.fail.connect(self.sign_failed)
        self.auth_worker.start()
        self.log("Waiting for Google sign-in (3 minute limit)...")

    def show_link(self, url):
        self.link_dlg = LinkDialog(self, url)
        self.link_dlg.show()

    def _close_link(self):
        if self.link_dlg:
            self.link_dlg.close()
            self.link_dlg = None

    def signed_in(self, email):
        self._close_link()
        self.s["account"] = email
        config.save_settings(self.s)
        self.log(f"Signed in as {email}")
        self.update_account_ui()

    def sign_failed(self, msg):
        self._close_link()
        self.log(f"Sign-in failed: {msg}")
        QtWidgets.QMessageBox.warning(self, APP_NAME, f"Sign-in failed:\n\n{msg}")

    def sign_out(self):
        auth.sign_out()
        self.s["account"] = ""
        config.save_settings(self.s)
        self.log("Signed out.")
        self.update_account_ui()

    def import_creds(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select credentials.json", "", "JSON (*.json)")
        if f:
            config.secure_write(config.CUSTOM_CLIENT_FILE, Path(f).read_text(encoding="utf-8"))
            auth.sign_out()
            self.log("Custom credentials.json loaded - please sign in again.")
            self.update_account_ui()

    def remove_creds(self):
        try:
            config.CUSTOM_CLIENT_FILE.unlink()
        except FileNotFoundError:
            pass
        auth.sign_out()
        self.log("Custom credentials.json removed - using the built-in sign-in.")
        self.update_account_ui()

    # ---- selective sync
    def update_mode_ui(self):
        sel = self.rb_sel.isChecked()
        self.btn_choose.setEnabled(sel)
        self.sel_label.setVisible(sel)
        names = [s["name"] for s in self.s["selected"]]
        self.sel_label.setText(("Selected: " + ", ".join(names)) if names
                               else "No folders selected yet - click 'Choose folders...'")

    def choose_folders(self):
        if not auth.is_signed_in():
            QtWidgets.QMessageBox.information(self, APP_NAME, "Please sign in with Google first.")
            return False
        try:
            dlg = FolderPicker(self, self.s["selected"])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Could not open Google Drive:\n{e}")
            return False
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return False
        self.s["selected"] = dlg.selected()
        config.save_settings(self.s)
        self.update_mode_ui()
        return True

    # ---- sync
    def sync_now(self, auto=False):
        if self.sync_worker and self.sync_worker.isRunning():
            return
        if not auth.is_signed_in():
            if not auto:
                self.log("Please sign in with Google first.")
            return
        self.persist()
        if self.s["mode"] == "selected" and not self.s["selected"]:
            if auto or not self.choose_folders() or not self.s["selected"]:
                return
        self.btn_sync.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.sync_worker = SyncWorker(dict(self.s))
        self.sync_worker.message.connect(self.on_message)
        self.sync_worker.items.connect(self.on_items)
        self.sync_worker.finished.connect(self.on_sync_done)
        self.sync_worker.start()

    def on_message(self, text):
        self.log(text)
        if text.startswith("ERROR") or text.startswith("Sync finished"):
            if not self.isVisible():
                self.tray.showMessage(APP_NAME, text, QtWidgets.QSystemTrayIcon.Information, 4000)

    def on_items(self, items):
        self.items = items
        self.manifest_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        config.save_manifest({"time": self.manifest_time, "root": self.s["local"],
                              "mode": self.s["mode"], "items": items})
        self.refresh_tree()

    def on_sync_done(self):
        self.btn_sync.setEnabled(True)
        self.btn_stop.setEnabled(False)

    # ---- synced files tree
    def refresh_tree(self):
        self.files.clear()
        if not self.items:
            self.files_info.setText("Nothing synced yet. Run a sync and your files will be listed here.")
            return
        root = treeutil.build_tree(self.items)
        st = self.style()
        dir_icon = st.standardIcon(QtWidgets.QStyle.SP_DirIcon)
        file_icon = st.standardIcon(QtWidgets.QStyle.SP_FileIcon)

        def add(parent, node):
            for n in node.sorted_children():
                info = n.info or {}
                if n.is_dir:
                    cols = [n.name, "", f"{treeutil.plural(n.files, 'file')}, {treeutil.human(n.bytes)}", ""]
                else:
                    cols = [n.name, info.get("status", ""), treeutil.human(info.get("size")),
                            treeutil.fmt_time(info.get("mtime"))]
                it = QtWidgets.QTreeWidgetItem(parent, cols)
                it.setIcon(0, dir_icon if n.is_dir else file_icon)
                it.setData(0, Qt.UserRole, n.path)
                if n.is_dir:
                    add(it, n)

        add(self.files, root)
        self.files.expandToDepth(0)
        self.files_info.setText(f"{treeutil.plural(root.files, 'file')}, "
                                f"{treeutil.human(root.bytes)} - last sync: {self.manifest_time}")

    def open_item(self, item, _col):
        rel = item.data(0, Qt.UserRole)
        base = Path(config.load_manifest().get("root", self.s["local"]))
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(base / rel)))

    def copy_tree(self):
        QtWidgets.QApplication.clipboard().setText(treeutil.render_text(self.items))

    def export_tree(self):
        if not self.items:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Nothing to export yet - run a sync first.")
            return
        fn, flt = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export synced files", str(Path.home() / "drive-tree.txt"),
            "Text tree (*.txt);;CSV spreadsheet (*.csv)")
        if not fn:
            return
        csv_mode = flt.startswith("CSV") or fn.lower().endswith(".csv")
        data = treeutil.render_csv(self.items) if csv_mode else treeutil.render_text(self.items)
        with open(fn, "w", encoding="utf-8-sig" if csv_mode else "utf-8", newline="") as fh:
            fh.write(data)
        self.log(f"Exported file list to {fn}")

    # ---- window / app lifecycle
    def closeEvent(self, e):
        if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            e.ignore()
            self.hide()
        else:
            self.quit()

    def quit(self):
        self.persist()
        self.tray.hide()
        self.app.quit()


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    apply_theme(app, config.load_settings()["theme"])
    w = Window(app)
    w.show()
    sys.exit(app.exec_())
