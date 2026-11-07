"""Built-in Google OAuth client used by the one-click "Sign in with Google" button.

The maintainer creates ONE "Desktop app" OAuth client in Google Cloud Console and puts
its ID/secret here (or injects them at build time, see packaging/inject_client.py).
For desktop apps Google does not treat the secret as confidential.
Users then never have to touch a credentials.json file.
"""
import os

CLIENT_ID = os.environ.get("DRIVESYNC_CLIENT_ID", "YOUR_CLIENT_ID.apps.googleusercontent.com")
CLIENT_SECRET = os.environ.get("DRIVESYNC_CLIENT_SECRET", "YOUR_CLIENT_SECRET")


def is_configured():
    return not CLIENT_ID.startswith("YOUR_") and not CLIENT_SECRET.startswith("YOUR_")
