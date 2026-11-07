import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from drivesync_iqbal import config, syncer, treeutil  # noqa: E402

T0 = 1_700_000_000


def folder(i):
    return {"id": i, "mimeType": syncer.FOLDER_MIME, "modifiedTime": syncer.ts_to_iso(T0)}


def fileobj(i, mt=T0, mime="text/plain"):
    return {"id": i, "mimeType": mime, "modifiedTime": syncer.ts_to_iso(mt)}


class FakeSyncer(syncer.Syncer):
    def __init__(self, remote, **kw):
        super().__init__(None, lambda m: None, **kw)
        self.remote, self.uploaded = remote, []

    def children(self, pid):
        return dict(self.remote.get(pid, {}))

    def download(self, fid, path, rt):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 10)
        os.utime(path, (rt, rt))

    def upload(self, path, pid, fid):
        self.uploaded.append(path.name)

    def create_folder(self, pid, name):
        nid = "new-" + name
        self.remote.setdefault(nid, {})
        return nid


def make_remote():
    return {
        "root": {"Docs": folder("d1"), "Pics": folder("p1"), "sheet": fileobj(
            "g1", mime="application/vnd.google-apps.spreadsheet")},
        "d1": {"a.txt": fileobj("f1")},
        "p1": {"b.jpg": fileobj("f2")},
    }


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_selective_only_chosen_folder(self):
        s = FakeSyncer(make_remote())
        s.run("selected", self.root, [{"id": "d1", "local": "Docs"}])
        self.assertTrue((self.root / "Docs" / "a.txt").exists())
        self.assertFalse((self.root / "Pics").exists())
        self.assertEqual(s.counts["downloaded"], 1)

    def test_second_run_is_unchanged(self):
        sel = [{"id": "d1", "local": "Docs"}]
        FakeSyncer(make_remote()).run("selected", self.root, sel)
        s = FakeSyncer(make_remote())
        s.run("selected", self.root, sel)
        self.assertEqual((s.counts["downloaded"], s.counts["unchanged"]), (0, 1))

    def test_all_mode_and_google_docs_skipped(self):
        s = FakeSyncer(make_remote())
        s.run("all", self.root, [])
        self.assertTrue((self.root / "Pics" / "b.jpg").exists())
        self.assertEqual(s.counts["skipped"], 1)

    def test_new_local_file_and_folder_are_uploaded(self):
        sel = [{"id": "d1", "local": "Docs"}]
        FakeSyncer(make_remote()).run("selected", self.root, sel)
        (self.root / "Docs" / "new.txt").write_text("hi")
        (self.root / "Docs" / "sub").mkdir()
        (self.root / "Docs" / "sub" / "c.txt").write_text("c")
        s = FakeSyncer(make_remote())
        s.run("selected", self.root, sel)
        self.assertCountEqual(s.uploaded, ["new.txt", "c.txt"])

    def test_stop_requested(self):
        s = FakeSyncer(make_remote(), should_stop=lambda: True)
        with self.assertRaises(syncer.SyncAborted):
            s.run("all", self.root, [])

    def test_safe_name(self):
        self.assertEqual(syncer.safe_name("a/b"), "a_b")
        old = config.IS_WIN
        config.IS_WIN = True
        try:
            self.assertEqual(syncer.safe_name('r:e?p*o "x".'), "r_e_p_o _x_")
        finally:
            config.IS_WIN = old


class TreeTests(unittest.TestCase):
    ITEMS = [
        {"path": "Docs", "type": "folder", "status": "synced", "size": None, "mtime": T0},
        {"path": "Docs/a.txt", "type": "file", "status": "downloaded", "size": 10, "mtime": T0},
        {"path": "Docs/z", "type": "folder", "status": "synced", "size": None, "mtime": T0},
        {"path": "Docs/z/b.bin", "type": "file", "status": "uploaded", "size": 2048, "mtime": T0},
        {"path": "Docs/sheet", "type": "file", "status": "skipped", "size": None, "mtime": None},
    ]

    def test_text_tree(self):
        expected = (
            "My Drive/\n"
            "└── Docs/  (2 files, 2.0 KB)\n"
            "    ├── z/  (1 file, 2.0 KB)\n"
            "    │   └── b.bin  (2.0 KB)\n"
            "    ├── a.txt  (10 B)\n"
            "    └── sheet  [Google Doc - not synced]\n"
            "\n2 files, 2.0 KB\n")
        self.assertEqual(treeutil.render_text(self.ITEMS), expected)

    def test_csv(self):
        out = treeutil.render_csv(self.ITEMS).splitlines()
        self.assertEqual(out[0], "path,type,status,size_bytes,modified")
        self.assertEqual(len(out), 6)


if __name__ == "__main__":
    unittest.main()
