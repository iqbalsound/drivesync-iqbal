"""Print the app version (single source of truth: drivesync_iqbal/__init__.py)."""
import re
from pathlib import Path


def get_version():
    text = (Path(__file__).resolve().parents[1] / "drivesync_iqbal" / "__init__.py").read_text()
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


if __name__ == "__main__":
    print(get_version())
