"""Sync engine. No GUI imports, so it can be tested without Qt."""
import os
from datetime import datetime, timezone
from pathlib import Path

from . import config

FOLDER_MIME = "application/vnd.google-apps.folder"
APPS_PREFIX = "application/vnd.google-apps"
_WIN_BAD = '<>:"/\\|?*'


class SyncAborted(Exception):
    pass


def safe_name(name):
    """Make a Drive name valid as a local file name (Windows is much stricter than Linux)."""
    if config.IS_WIN:
        name = "".join("_" if (c in _WIN_BAD or ord(c) < 32) else c for c in name).rstrip(" .")
    else:
        name = name.replace("/", "_").replace("\x00", "_")
    return name or "_"


def iso_to_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def ts_to_iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def list_folders(svc, parent_id):
    """Return [(id, name)] of the sub-folders of parent_id ('root' = My Drive)."""
    out, token = [], None
    while True:
        r = svc.files().list(
            q=f"'{parent_id}' in parents and mimeType='{FOLDER_MIME}' and trashed=false",
            orderBy="name", pageSize=1000, pageToken=token,
            fields="nextPageToken, files(id,name)").execute()
        out += [(f["id"], f["name"]) for f in r["files"]]
        token = r.get("nextPageToken")
        if not token:
            return out


class Syncer:
    """Two-way sync, newest file wins. Deletions are NOT propagated (safe by design)."""

    def __init__(self, service, log, should_stop=lambda: False):
        self.svc, self.log, self.should_stop = service, log, should_stop
        self.items = []
        self.counts = {"downloaded": 0, "uploaded": 0, "unchanged": 0, "skipped": 0}

    # ---- bookkeeping
    def _check(self):
        if self.should_stop():
            raise SyncAborted()

    def _record(self, rel, kind, status, path=None):
        size = mtime = None
        if path is not None and path.exists():
            st = path.stat()
            size, mtime = (st.st_size, st.st_mtime) if kind == "file" else (None, st.st_mtime)
        self.items.append({"path": rel, "type": kind, "status": status,
                           "size": size, "mtime": mtime})
        if kind == "file":
            self.counts[status] += 1

    # ---- drive access (overridden in tests)
    def children(self, pid):
        out, token = [], None
        while True:
            r = self.svc.files().list(
                q=f"'{pid}' in parents and trashed=false", pageToken=token, pageSize=1000,
                fields="nextPageToken, files(id,name,mimeType,modifiedTime)").execute()
            out += r["files"]
            token = r.get("nextPageToken")
            if not token:
                break
        result = {}
        for f in sorted(out, key=lambda x: x["name"].lower()):
            key = safe_name(f["name"])
            if key in result:                      # Drive allows duplicate names; disk doesn't
                stem, ext = os.path.splitext(key)
                key = f"{stem} ({f['id'][:6]}){ext}"
            result[key] = f
        return result

    def create_folder(self, pid, name):
        return self.svc.files().create(
            body={"name": name, "mimeType": FOLDER_MIME, "parents": [pid]},
            fields="id").execute()["id"]

    def download(self, fid, path, rt):
        from googleapiclient.http import MediaIoBaseDownload
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".dsync-part")
        with open(tmp, "wb") as fh:
            dl = MediaIoBaseDownload(fh, self.svc.files().get_media(fileId=fid))
            done = False
            while not done:
                self._check()
                _, done = dl.next_chunk()
        os.replace(tmp, path)
        os.utime(path, (rt, rt))
        self.log(f"Downloaded: {path.name}")

    def upload(self, path, pid, fid):
        from googleapiclient.http import MediaFileUpload
        body = {"modifiedTime": ts_to_iso(path.stat().st_mtime)}
        media = MediaFileUpload(str(path), resumable=path.stat().st_size > 0)
        if fid:
            self.svc.files().update(fileId=fid, body=body, media_body=media).execute()
        else:
            body.update(name=path.name, parents=[pid])
            self.svc.files().create(body=body, media_body=media).execute()
        self.log(f"Uploaded: {path.name}")

    # ---- main logic
    def run(self, mode, local_root, selected):
        local_root = Path(local_root).expanduser()
        if mode == "selected":
            if not selected:
                self.log("No folders selected - nothing to sync.")
                return
            for s in selected:
                self.sync_folder(s["id"], local_root / s["local"], s["local"])
        else:
            self.sync_folder("root", local_root, "")

    def sync_folder(self, pid, local, rel):
        self._check()
        local.mkdir(parents=True, exist_ok=True)
        if rel:
            self._record(rel, "folder", "synced", local)
        remote = self.children(pid)
        for name, f in remote.items():
            self._check()
            p = local / name
            r = f"{rel}/{name}" if rel else name
            if f["mimeType"] == FOLDER_MIME:
                self.sync_folder(f["id"], p, r)
            elif f["mimeType"].startswith(APPS_PREFIX):
                self.log(f"Skipped (Google Doc/Sheet/Slide): {name}")
                self._record(r, "file", "skipped")
            else:
                rt = iso_to_ts(f["modifiedTime"])
                if not p.exists() or rt > p.stat().st_mtime + 2:
                    self.download(f["id"], p, rt)
                    status = "downloaded"
                elif p.stat().st_mtime > rt + 2:
                    self.upload(p, pid, f["id"])
                    status = "uploaded"
                else:
                    status = "unchanged"
                self._record(r, "file", status, p)
        for p in sorted(local.iterdir(), key=lambda x: x.name.lower()):
            if (p.name in remote or p.name.startswith(".")
                    or p.name.endswith(".dsync-part")):
                continue
            r = f"{rel}/{p.name}" if rel else p.name
            if p.is_dir():
                self.log(f"Creating folder: {p.name}")
                self.sync_folder(self.create_folder(pid, p.name), p, r)
            elif p.is_file():
                self._check()
                self.upload(p, pid, None)
                self._record(r, "file", "uploaded", p)
