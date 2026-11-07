"""Build and export the 'synced files' tree (text in `tree` style, or CSV)."""
import csv
import io
from datetime import datetime


def human(n):
    if n is None:
        return ""
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def fmt_time(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


class Node:
    def __init__(self, name, is_dir, path):
        self.name, self.is_dir, self.path = name, is_dir, path
        self.info, self.children = {}, {}
        self.files = self.bytes = 0

    def sorted_children(self):
        return sorted(self.children.values(), key=lambda n: (not n.is_dir, n.name.lower()))


def _summarize(node):
    if not node.is_dir:
        if node.info.get("status") == "skipped":     # listed, but not on disk
            node.files = node.bytes = 0
        else:
            node.files, node.bytes = 1, (node.info.get("size") or 0)
        return
    node.files = node.bytes = 0
    for c in node.children.values():
        _summarize(c)
        node.files += c.files
        node.bytes += c.bytes


def build_tree(items):
    root = Node("", True, "")
    for it in items:
        parts = [p for p in it["path"].split("/") if p]
        node = root
        for i, part in enumerate(parts):
            last = i == len(parts) - 1
            child = node.children.get(part)
            if child is None:
                child = Node(part, (not last) or it["type"] == "folder", "/".join(parts[:i + 1]))
                node.children[part] = child
            node = child
        if parts:
            node.info = it
    _summarize(root)
    return root


def render_text(items, root_label="My Drive", details=True):
    root = build_tree(items)
    lines = [f"{root_label}/"]

    def walk(node, prefix):
        kids = node.sorted_children()
        for i, k in enumerate(kids):
            last = i == len(kids) - 1
            label = k.name
            if k.is_dir:
                label += "/"
                if details:
                    label += f"  ({plural(k.files, 'file')}, {human(k.bytes)})"
            elif details:
                if k.info.get("status") == "skipped":
                    label += "  [Google Doc - not synced]"
                else:
                    label += f"  ({human(k.bytes)})"
            lines.append(prefix + ("└── " if last else "├── ") + label)
            if k.is_dir:
                walk(k, prefix + ("    " if last else "│   "))

    walk(root, "")
    lines += ["", f"{plural(root.files, 'file')}, {human(root.bytes)}"]
    return "\n".join(lines) + "\n"


def render_csv(items):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["path", "type", "status", "size_bytes", "modified"])
    for it in sorted(items, key=lambda i: i["path"].casefold()):
        w.writerow([it["path"], it["type"], it.get("status", ""),
                    "" if it.get("size") is None else it["size"],
                    fmt_time(it.get("mtime"))])
    return buf.getvalue()
