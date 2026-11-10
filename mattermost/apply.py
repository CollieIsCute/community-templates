#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def fail(message):
    try:
        if not notice.is_file() or notice.read_text() != message:
            result = subprocess.run(
                ["noctalia", "msg", "notification-show", "Mattermost Theme", message],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
            )
            if result.returncode == 0:
                notice.parent.mkdir(parents=True, exist_ok=True)
                notice.write_text(message)
    except (OSError, subprocess.TimeoutExpired):
        pass
    sys.exit(f"Warning: Mattermost theme: {message}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
cache_home = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
state_home = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
credentials = config_home / "noctalia-mattermost/credentials.json"
theme_path = cache_home / "noctalia/mattermost-theme.json"
notice = cache_home / "noctalia/mattermost-warning"
backup = state_home / "noctalia/mattermost-backup.json"


def save_backup(data):
    backup.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=backup.parent, prefix=".mattermost-")
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(data, handle)
        os.replace(temporary, backup)
    finally:
        Path(temporary).unlink(missing_ok=True)


try:
    if sys.argv[1:] not in ([], ["undo"]):
        fail("usage: python3 apply.py [undo]")
    undo = sys.argv[1:] == ["undo"]
    if undo and not backup.exists():
        sys.exit(0)
    if not credentials.is_file():
        fail(f"configure URL and token in {credentials}; see the template README")
    if not undo:
        theme = json.loads(theme_path.read_text())
        if not isinstance(theme, dict) or not {"sidebarBg", "centerChannelBg", "centerChannelColor"} <= theme.keys():
            fail("generated theme is incomplete")
        if any(not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value)
               for key, value in theme.items() if key not in {"type", "codeTheme"}):
            fail("generated theme contains invalid colors")
    if credentials.stat().st_mode & 0o077:
        fail("credentials.json must have permissions 0600")
    auth = json.loads(credentials.read_text())
    url, token = auth["url"], auth["token"]
    if not isinstance(url, str) or not isinstance(token, str) or not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
        fail("invalid URL or token in credentials.json")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail("URL must be an HTTPS server address")
    opener = urllib.request.build_opener(NoRedirect())

    def request(path, data=None, method=None):
        body = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(
            url.rstrip("/") + "/api/v4" + path,
            data=body,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            method=method or ("GET" if data is None else "PUT"),
        )
        with opener.open(req, timeout=15) as response:
            result = json.load(response)
        if data is not None and (not isinstance(result, dict) or result.get("status") != "OK"):
            fail("API did not confirm the theme update")
        return result

    user_id = request("/users/me")["id"]
    if not isinstance(user_id, str) or not re.fullmatch(r"[a-z0-9]{26}", user_id):
        fail("API returned an invalid user ID")
    path = "/users/" + user_id + "/preferences"
    preferences = request(path + "/theme")
    if not isinstance(preferences, list) or any(not isinstance(item, dict) for item in preferences):
        fail("API returned invalid preferences")
    current = next((item for item in preferences if item.get("category") == "theme" and item.get("name") == ""), None)
    current_theme = json.loads(current["value"]) if current else None
    saved = json.loads(backup.read_text()) if backup.exists() else None
    if saved is not None:
        if not isinstance(saved, dict) or saved.get("url") != url or saved.get("user_id") != user_id:
            fail("backup belongs to another server or account; restore it before changing credentials")
        previous = saved["previous"]
        if not isinstance(saved["applied"], dict) or (previous is not None and (
            not isinstance(previous, dict) or previous.get("user_id") != user_id
            or previous.get("category") != "theme" or previous.get("name") != ""
            or not isinstance(previous.get("value"), str)
        )):
            fail("local theme backup is invalid")
    if undo:
        if current_theme == saved["applied"]:
            if saved["previous"] is None:
                request(path + "/delete", [current], method="POST")
            else:
                request(path, [saved["previous"]])
        else:
            print("Mattermost theme changed elsewhere; leaving it unchanged.")
        backup.unlink()
    elif current_theme != theme:
        if saved is None:
            saved = {"url": url, "user_id": user_id, "previous": current, "applied": theme}
            save_backup(saved)
        request(path, [{"user_id": user_id, "category": "theme", "name": "", "value": json.dumps(theme)}])
        saved["applied"] = theme
        save_backup(saved)
    notice.unlink(missing_ok=True)
except urllib.error.HTTPError as error:
    fail(f"API returned HTTP {error.code}; check credentials.json if the token expired or was revoked")
except urllib.error.URLError:
    fail("could not connect to the configured server")
except FileNotFoundError:
    fail("local credentials or generated theme file is missing")
except (OSError, ValueError, KeyError, TypeError, AttributeError):
    fail("could not read local configuration or API response")

print("Mattermost theme undo finished." if undo else "Mattermost account theme matches Noctalia.")
