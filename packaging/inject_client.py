"""Write the built-in OAuth client from environment variables (used by CI secrets).
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET -> drivesync_iqbal/oauth_client.py"""
import os
import sys
from pathlib import Path

cid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
sec = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
if not cid or not sec:
    print("No OAuth secrets provided - building without built-in sign-in.")
    sys.exit(0)
target = Path(__file__).resolve().parents[1] / "drivesync_iqbal" / "oauth_client.py"
target.write_text(
    f"CLIENT_ID = {cid!r}\nCLIENT_SECRET = {sec!r}\n\n\ndef is_configured():\n    return True\n")
print("Built-in OAuth client injected.")
