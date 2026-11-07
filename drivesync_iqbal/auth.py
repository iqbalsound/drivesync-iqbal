"""Google sign-in helpers: one-click browser sign-in, link sign-in, optional own credentials."""
import inspect
import json

from . import config, oauth_client

SCOPES = ["https://www.googleapis.com/auth/drive"]


class AuthError(Exception):
    pass


class NotConfigured(AuthError):
    pass


def using_custom_credentials():
    return config.CUSTOM_CLIENT_FILE.exists()


def is_signed_in():
    return config.TOKEN_FILE.exists()


def _client_config():
    if using_custom_credentials():
        try:
            return json.loads(config.CUSTOM_CLIENT_FILE.read_text(encoding="utf-8"))
        except ValueError as e:
            raise AuthError(f"Your credentials.json is not valid: {e}")
    if not oauth_client.is_configured():
        raise NotConfigured(
            "This build has no built-in Google sign-in yet.\n\n"
            "Maintainer: set CLIENT_ID / CLIENT_SECRET in drivesync_iqbal/oauth_client.py.\n"
            "Advanced users: use the 'Advanced' menu to load your own credentials.json.")
    return {"installed": {
        "client_id": oauth_client.CLIENT_ID,
        "client_secret": oauth_client.CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "redirect_uris": ["http://localhost"],
    }}


class _LinkSink:
    """Passed as 'authorization_prompt_message'; the library calls .format(url=...) on it,
    which lets us capture the sign-in link instead of printing it."""

    def __init__(self, callback):
        self.callback = callback

    def format(self, **kw):
        self.callback(kw["url"])
        return ""


def sign_in(link_callback=None):
    """Interactive Google sign-in. With link_callback the browser is NOT opened; the URL is
    handed to the callback so the user can open it in any browser on this computer."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_config(_client_config(), SCOPES)
    kwargs = dict(port=0, prompt="consent",
                  success_message="Signed in. You can close this tab and return to DriveSync by Iqbal.")
    if "timeout_seconds" in inspect.signature(flow.run_local_server).parameters:
        kwargs["timeout_seconds"] = 180
    if link_callback:
        kwargs.update(open_browser=False, authorization_prompt_message=_LinkSink(link_callback))
    else:
        kwargs.update(open_browser=True, authorization_prompt_message="")
    creds = flow.run_local_server(**kwargs)
    config.secure_write(config.TOKEN_FILE, creds.to_json())


def load_credentials():
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    if not config.TOKEN_FILE.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(config.TOKEN_FILE), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                raise AuthError("Your Google session has expired. Please sign in again.")
            config.secure_write(config.TOKEN_FILE, creds.to_json())
        else:
            return None
    return creds


def get_service():
    from googleapiclient.discovery import build
    creds = load_credentials()
    if creds is None:
        raise AuthError("Not signed in. Please sign in with Google first.")
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def account_email():
    about = get_service().about().get(fields="user(emailAddress)").execute()
    return about["user"]["emailAddress"]


def sign_out():
    try:
        config.TOKEN_FILE.unlink()
    except FileNotFoundError:
        pass
