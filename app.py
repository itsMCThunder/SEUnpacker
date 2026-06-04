import csv
import json
import os
import re
import shutil
import subprocess
import webbrowser
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
import uuid
import threading
import zipfile
import http.server
from datetime import datetime
from io import BytesIO, StringIO
from html import escape as html_escape
from pathlib import Path
from tkinter import (
    Tk,
    StringVar,
    END,
    filedialog,
    messagebox,
    Button,
    Label,
    Entry,
    Frame,
    PhotoImage,
    Toplevel,
    Canvas,
    Checkbutton,
)
from tkinter.scrolledtext import ScrolledText

try:
    import webview
except Exception:
    webview = None


APP_NAME = "SEUnpacker"
APP_VERSION = "0.8.7"

GITHUB_OWNER = "itsMCThunder"
GITHUB_REPO = "SEUnpacker"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
GITHUB_RELEASE_ASSET_NAME = "SEUnpacker.exe"

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
SUPPORTED_SHORTCUT_EXTENSIONS = {".url"}

DARK_BG = "#0b0f17"
SIDEBAR_BG = "#171b22"
SIDEBAR_ACTIVE = "#10141b"
PANEL_BG = "#111827"
HEADER_BG = "#3c4048"
FIELD_BG = "#020617"
LOG_BG = "#020617"
TEXT_FG = "#f3f4f6"
MUTED_FG = "#9ca3af"
BLUE = "#2563eb"
BLUE_HOVER = "#1d4ed8"
YELLOW = "#facc15"
BORDER = "#1f2937"

TWITCH_DEFAULT_CLIENT_ID = "vk11lzb0xvwd3xq2ylkp4r1p3iu3fm"
TWITCH_REDIRECT_URI = "http://localhost:17654/twitch/callback"
TWITCH_OAUTH_PORT = 17654
TWITCH_OAUTH_SCOPES = [
    "channel:read:subscriptions",
    "bits:read",
    "moderator:read:followers",
    "channel:read:redemptions",
    "channel:read:hype_train",
    "channel:read:polls",
    "channel:read:predictions",
    "chat:read",
    "chat:edit",
    "moderator:read:shoutouts",
    "channel:read:charity",
]


def resource_path(relative_path: str) -> Path:
    try:
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).resolve().parent

    return base_path / relative_path


def get_default_output_folder() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")

    if local_appdata:
        return Path(local_appdata) / "SEUnpacker" / "Output"

    return Path.cwd() / "SEUnpacker_Output"


def get_streamelements_state_folder() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")

    if local_appdata:
        folder = Path(local_appdata) / "SEUnpacker"
    else:
        folder = Path.cwd() / "SEUnpacker_State"

    folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_streamelements_status_file() -> Path:
    return get_streamelements_state_folder() / "streamelements_login_status.json"


def get_streamelements_webview_storage_folder() -> Path:
    folder = get_streamelements_state_folder() / "StreamElementsWebView"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_twitch_direct_feed_config_file() -> Path:
    return get_streamelements_state_folder() / "twitch_direct_feed.json"


def get_minimal_event_rotator_config_file() -> Path:
    return get_streamelements_state_folder() / "minimal_event_rotator_config.json"


def get_default_minimal_event_rotator_config() -> dict:
    return {
        "show_follower_count": True,
        "show_sub_months": True,
        "show_single_gift_sub": True,
        "show_community_gift_count": True,
        "show_cheer_bits": True,
        "show_raid_viewers": True,
        "show_tip_amount": True,
        "show_redemptions": True,
    }


def read_minimal_event_rotator_config() -> dict:
    config = get_default_minimal_event_rotator_config()
    try:
        path = get_minimal_event_rotator_config_file()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key in config:
                    if key in data:
                        config[key] = bool(data[key])
    except Exception:
        pass
    return config


def write_minimal_event_rotator_config(config: dict):
    final = get_default_minimal_event_rotator_config()
    if isinstance(config, dict):
        for key in final:
            if key in config:
                final[key] = bool(config[key])
    path = get_minimal_event_rotator_config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(final, indent=2), encoding="utf-8")



def read_twitch_direct_feed_config() -> dict:
    try:
        path = get_twitch_direct_feed_config_file()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def write_twitch_direct_feed_config(config: dict):
    path = get_twitch_direct_feed_config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(config or {}), indent=2), encoding="utf-8")


def clear_twitch_direct_feed_config():
    path = get_twitch_direct_feed_config_file()
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def get_twitch_direct_feed_status_text() -> str:
    config = read_twitch_direct_feed_config()
    if config.get("enabled") and config.get("client_id") and config.get("access_token") and config.get("broadcaster_user_id"):
        channel = config.get("channel_login") or config.get("broadcaster_user_id")
        return f"Twitch Direct Feed: Enabled for {channel}"
    if config.get("client_id") or config.get("access_token") or config.get("broadcaster_user_id"):
        return "Twitch Direct Feed: Incomplete setup"
    return "Twitch Direct Feed: Not configured"


def validate_twitch_token(client_id: str, access_token: str) -> tuple[bool, str, dict]:
    client_id = (client_id or "").strip()
    access_token = (access_token or "").strip()
    if not client_id or not access_token:
        return False, "Client ID and access token are required.", {}
    try:
        req = urllib.request.Request(
            "https://api.twitch.tv/helix/users",
            headers={
                "Client-Id": client_id,
                "Authorization": f"Bearer {access_token}",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        users = payload.get("data") or []
        if not users:
            return False, "Twitch token validated, but no user data was returned.", {}
        user = users[0]
        return True, f"Connected as {user.get('display_name') or user.get('login') or user.get('id')}", user
    except Exception as exc:
        return False, f"Twitch validation failed: {exc}", {}


def run_twitch_one_click_authorization(client_id: str, log_func=None, timeout_seconds: int = 180) -> tuple[bool, str, dict]:
    client_id = (client_id or TWITCH_DEFAULT_CLIENT_ID).strip()
    if not client_id:
        return False, "Twitch Client ID is required.", {}

    state = uuid.uuid4().hex
    done = threading.Event()
    result = {"ok": False, "message": "Twitch authorization did not complete.", "token_payload": {}}

    def log(message: str):
        if log_func:
            try:
                log_func(message)
            except Exception:
                pass

    class TwitchOAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def _send_html(self, html: str):
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/twitch/callback":
                self.send_response(404)
                self.end_headers()
                return

            query = urllib.parse.parse_qs(parsed.query or "")
            if "error" in query:
                result["ok"] = False
                result["message"] = "Twitch authorization failed: " + (query.get("error_description") or query.get("error") or ["unknown error"])[0]
                done.set()
                self._send_html("<html><body style='font-family:Segoe UI;background:#111;color:#fff;padding:24px'><h2>SEUnpacker Twitch authorization failed.</h2><p>You can close this window.</p></body></html>")
                return

            # Twitch implicit OAuth returns the access token in the URL fragment.
            # Browsers do not send fragments to the local server, so this tiny page
            # reads location.hash and POSTs it back to SEUnpacker.
            self._send_html("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>SEUnpacker Twitch Authorization</title>
</head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#0b0f17;color:#f3f4f6;padding:24px;">
<h2>Finishing Twitch authorization...</h2>
<p>This window should close automatically after SEUnpacker captures the Twitch token.</p>
<script>
(function() {
  const hash = (window.location.hash || '').replace(/^#/, '');
  if (!hash) {
    document.body.insertAdjacentHTML('beforeend', '<p style="color:#fca5a5">No Twitch token was returned. You can close this window and try again.</p>');
    return;
  }
  fetch('/twitch/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: hash
  }).then(function() {
    document.body.innerHTML = '<h2>Twitch connected to SEUnpacker.</h2><p>You can close this window.</p>';
    setTimeout(function() { window.close(); }, 750);
  }).catch(function(err) {
    document.body.insertAdjacentHTML('beforeend', '<p style="color:#fca5a5">Could not send token back to SEUnpacker: ' + err + '</p>');
  });
})();
</script>
</body>
</html>""")

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/twitch/token":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            payload = {k: v[0] if v else "" for k, v in urllib.parse.parse_qs(body).items()}
            if payload.get("state") != state:
                result["ok"] = False
                result["message"] = "Twitch authorization failed: state mismatch."
                done.set()
            elif not payload.get("access_token"):
                result["ok"] = False
                result["message"] = "Twitch authorization failed: no access token returned."
                done.set()
            else:
                result["ok"] = True
                result["message"] = "Twitch authorization token captured."
                result["token_payload"] = payload
                done.set()

            data = b"OK"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    class ReusableHTTPServer(http.server.ThreadingHTTPServer):
        allow_reuse_address = True

    try:
        server = ReusableHTTPServer(("127.0.0.1", TWITCH_OAUTH_PORT), TwitchOAuthCallbackHandler)
    except Exception as exc:
        return False, f"Could not start local Twitch callback server on port {TWITCH_OAUTH_PORT}: {exc}", {}

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    params = {
        "response_type": "token",
        "client_id": client_id,
        "redirect_uri": TWITCH_REDIRECT_URI,
        "scope": " ".join(TWITCH_OAUTH_SCOPES),
        "state": state,
    }
    auth_url = "https://id.twitch.tv/oauth2/authorize?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    log("Opening Twitch authorization page...")
    webbrowser.open(auth_url)

    try:
        if not done.wait(timeout_seconds):
            return False, "Twitch authorization timed out. Try again and complete the Twitch prompt.", {}

        if not result.get("ok"):
            return False, result.get("message", "Twitch authorization failed."), {}

        token_payload = result.get("token_payload") or {}
        access_token = token_payload.get("access_token", "")
        ok, msg, user = validate_twitch_token(client_id, access_token)
        if not ok:
            return False, msg, {}

        payload = {
            "enabled": True,
            "client_id": client_id,
            "access_token": access_token,
            "broadcaster_user_id": str(user.get("id", "")),
            "moderator_user_id": str(user.get("id", "")),
            "channel_login": str(user.get("login") or user.get("display_name") or ""),
            "display_name": str(user.get("display_name") or user.get("login") or ""),
            "scope": token_payload.get("scope", ""),
            "expires_in": token_payload.get("expires_in", ""),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        write_twitch_direct_feed_config(payload)
        return True, msg, payload
    finally:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass


def write_streamelements_login_status(status: str, url: str = "", message: str = ""):
    payload = {
        "status": status,
        "url": url,
        "message": message,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        path = get_streamelements_status_file()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def read_streamelements_login_status() -> dict:
    try:
        path = get_streamelements_status_file()
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass

    return {"status": "unknown", "url": "", "message": "Not checked", "updated_at": ""}


def looks_like_streamelements_logged_in_url(url: str) -> bool:
    lowered = (url or "").lower()
    if "streamelements.com" not in lowered:
        return False
    if "/login" in lowered or "/signup" in lowered or "/oauth" in lowered:
        return False
    return "/dashboard" in lowered or "/overlays" in lowered


def looks_like_streamelements_login_url(url: str) -> bool:
    lowered = (url or "").lower()
    return "streamelements.com" in lowered and ("/login" in lowered or "/signup" in lowered or "/oauth" in lowered)


def get_appdata_firebot_resources() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA environment variable was not found.")

    return Path(appdata) / "Firebot" / "v5" / "overlay-resources" / "SEUnpacker"


def get_firebot_main_profile_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA environment variable was not found.")

    return Path(appdata) / "Firebot" / "v5" / "profiles" / "Main"


def get_firebot_profile_dir() -> Path:
    """Backward-compatible alias used by Firebot history backfill."""
    return get_firebot_main_profile_path()


def get_firebot_events_json_path() -> Path:
    return get_firebot_main_profile_path() / "events" / "events.json"


def get_firebot_overlay_widgets_json_path() -> Path:
    return get_firebot_main_profile_path() / "overlay-widgets.json"


def get_firebot_preset_effect_lists_json_path() -> Path:
    return get_firebot_main_profile_path() / "effects" / "preset-effect-lists.json"


def timestamp_string() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_file(file_path: Path, backup_folder_name: str) -> Path:
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("{}", encoding="utf-8")

    backup_dir = file_path.parent / backup_folder_name
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_path = backup_dir / f"{file_path.stem}_backup_{timestamp_string()}{file_path.suffix}"
    shutil.copy2(file_path, backup_path)

    return backup_path


def load_json_file(path: Path, default_value):
    if not path.exists():
        return default_value

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return default_value


def save_json_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def load_firebot_events_file(events_path: Path) -> dict:
    data = load_json_file(events_path, {"mainEvents": []})

    if not isinstance(data, dict):
        data = {"mainEvents": []}

    if "mainEvents" not in data or not isinstance(data["mainEvents"], list):
        data["mainEvents"] = []

    return data


def save_firebot_events_file(events_path: Path, data: dict):
    save_json_file(events_path, data)


def normalize_firebot_overlay_widget_record(widget: dict) -> dict:
    """
    Normalize widget records before Firebot reads them.

    SEUnpacker v0.4.1 wrote its persistent widget as type "custom". Firebot's
    overlay widget registry expects the Custom Widget type id to be
    "firebot:custom". Leaving it as "custom" makes Firebot show a broken /
    missing type widget row.
    """
    if not isinstance(widget, dict):
        return widget

    name = str(widget.get("name", ""))

    if name.startswith("SEUnpacker - "):
        widget["type"] = "firebot:custom"

        if "active" not in widget:
            widget["active"] = True

        if "enabled" not in widget:
            widget["enabled"] = True

        if "settings" not in widget or not isinstance(widget["settings"], dict):
            widget["settings"] = {}

    return widget


def load_firebot_overlay_widgets_file(widgets_path: Path) -> list:
    """
    Load Firebot overlay-widgets.json in the safest shape SEUnpacker can handle.

    Firebot should receive a raw list of widget records from SEUnpacker. Older
    SEUnpacker builds could leave behind wrapper objects or malformed records,
    so this loader unwraps those where possible and normalizes the SEUnpacker
    widget type before saving the corrected raw list back out.
    """
    data = load_json_file(widgets_path, [])

    if isinstance(data, list):
        return [
            normalize_firebot_overlay_widget_record(widget)
            for widget in data
            if isinstance(widget, dict)
        ]

    if isinstance(data, dict):
        if "widgets" in data and isinstance(data["widgets"], list):
            return [
                normalize_firebot_overlay_widget_record(widget)
                for widget in data["widgets"]
                if isinstance(widget, dict)
            ]

        # Some helper builds stored widgets as an id-keyed dictionary. Convert
        # that into the list shape SEUnpacker now writes.
        values = [value for value in data.values() if isinstance(value, dict)]
        if values:
            return [normalize_firebot_overlay_widget_record(widget) for widget in values]

        # If the file itself is a single widget record, keep it instead of
        # throwing it away.
        if "name" in data or "type" in data:
            return [normalize_firebot_overlay_widget_record(data)]

    return []


def save_firebot_overlay_widgets_file(widgets_path: Path, widgets: list):
    save_json_file(widgets_path, widgets)


def load_firebot_preset_effect_lists_file(preset_path: Path) -> list:
    """
    Firebot preset effect lists are stored as a list-like collection.

    Older empty files may contain {}. We normalize that to [].
    """
    data = load_json_file(preset_path, [])

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        if "presetEffectLists" in data and isinstance(data["presetEffectLists"], list):
            return data["presetEffectLists"]

    return []


def save_firebot_preset_effect_lists_file(preset_path: Path, preset_lists: list):
    save_json_file(preset_path, preset_lists)


def safe_slug(name: str) -> str:
    name = Path(name).stem
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    return name or "unpacked-pack"


def safe_firebot_display_name(text: str, max_length: int = 50) -> str:
    """Return a Firebot-safe display name that stays under Firebot's limit.

    Firebot allows normal readable names, including spaces and hyphens, but the
    overlay widget name field rejects names longer than 50 characters. Keep
    resource folder slugs separate because those are paths, not UI names.
    """
    text = str(text or "").strip()
    text = re.sub(r"[^A-Za-z0-9 _-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_")

    if not text:
        text = "Widget"

    if len(text) > max_length:
        text = text[:max_length].rstrip(" -_")

    return text or "Widget"


def pack_display_name_for_firebot(pack_info: dict) -> str:
    source_zip = str(pack_info.get("source_zip", "")).strip()
    if source_zip:
        base_name = Path(source_zip).stem
    else:
        base_name = str(pack_info.get("pack_slug", "unpacked pack"))

    # Drop Windows duplicate suffixes like "(2)" and turn slugs into readable names.
    base_name = re.sub(r"\s*\(\d+\)\s*$", "", base_name).strip()
    base_name = base_name.replace("_", " ").replace("-", " ")
    return safe_firebot_display_name(base_name, max_length=50)


def run_hidden(command: list[str]) -> subprocess.CompletedProcess:
    creationflags = 0

    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        creationflags=creationflags,
    )


def get_running_processes() -> list[dict]:
    try:
        result = run_hidden(["tasklist", "/FO", "CSV", "/NH"])

        if result.returncode != 0:
            return []

        reader = csv.reader(StringIO(result.stdout))
        processes = []

        for row in reader:
            if len(row) < 2:
                continue

            processes.append(
                {
                    "image_name": row[0].strip(),
                    "pid": row[1].strip(),
                }
            )

        return processes

    except Exception:
        return []


def is_firebot_process_name(image_name: str) -> bool:
    name = image_name.lower().strip()

    if "seunpacker" in name:
        return False

    if name in {"python.exe", "pythonw.exe"}:
        return False

    return "firebot" in name


def get_running_firebot_processes() -> list[dict]:
    return [
        process
        for process in get_running_processes()
        if is_firebot_process_name(process.get("image_name", ""))
    ]


def is_firebot_running() -> tuple[bool, str]:
    firebot_processes = get_running_firebot_processes()

    if firebot_processes:
        names = [
            f"{process['image_name']} PID {process['pid']}"
            for process in firebot_processes
        ]

        return True, "Detected Firebot process: " + ", ".join(names)

    return False, "No Firebot process detected. Stale port 7472 entries are ignored."




def find_firebot_executable() -> Path | None:
    """Find the Firebot desktop executable in common Windows install locations."""
    candidates = []

    local_appdata = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("PROGRAMFILES", "")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "")

    if local_appdata:
        candidates.extend([
            Path(local_appdata) / "Programs" / "Firebot" / "Firebot.exe",
            Path(local_appdata) / "Programs" / "firebot" / "Firebot.exe",
            Path(local_appdata) / "Firebot" / "Firebot.exe",
        ])
    if program_files:
        candidates.extend([
            Path(program_files) / "Firebot" / "Firebot.exe",
            Path(program_files) / "firebot" / "Firebot.exe",
        ])
    if program_files_x86:
        candidates.extend([
            Path(program_files_x86) / "Firebot" / "Firebot.exe",
            Path(program_files_x86) / "firebot" / "Firebot.exe",
        ])

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def launch_firebot_desktop() -> tuple[bool, str]:
    exe_path = find_firebot_executable()
    if exe_path:
        try:
            subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, f"Launched Firebot: {exe_path}"
        except Exception as exc:
            return False, f"Found Firebot at {exe_path}, but could not launch it: {exc}"

    try:
        os.startfile("firebot://")  # type: ignore[attr-defined]
        return True, "Sent launch request to the Firebot URL protocol."
    except Exception:
        return False, "Could not find Firebot.exe in common install folders."

def get_netstat_entries_for_port(port: int) -> list[dict]:
    entries = []

    try:
        result = run_hidden(["netstat", "-ano"])

        if result.returncode != 0:
            return entries

        for line in result.stdout.splitlines():
            stripped = line.strip()

            if not stripped.lower().startswith("tcp"):
                continue

            if f":{port}" not in stripped:
                continue

            parts = stripped.split()

            if len(parts) < 5:
                continue

            entries.append(
                {
                    "protocol": parts[0],
                    "local_address": parts[1],
                    "foreign_address": parts[2],
                    "state": parts[3],
                    "pid": parts[4],
                    "raw": stripped,
                }
            )

    except Exception:
        pass

    return entries


def get_process_name_by_pid(pid: str) -> str:
    try:
        result = run_hidden(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"])

        if result.returncode != 0:
            return ""

        reader = csv.reader(StringIO(result.stdout))
        for row in reader:
            if len(row) >= 2 and row[1].strip() == str(pid):
                return row[0].strip()

    except Exception:
        pass

    return ""


def get_firebot_port_diagnostic(port: int = 7472) -> str:
    entries = get_netstat_entries_for_port(port)

    if not entries:
        return f"No netstat entries found for port {port}."

    lines = []

    for entry in entries:
        pid = entry.get("pid", "")
        process_name = get_process_name_by_pid(pid)
        state = entry.get("state", "")
        raw = entry.get("raw", "")

        if process_name:
            lines.append(f"{state} PID {pid} {process_name} | {raw}")
        else:
            lines.append(f"{state} PID {pid} | {raw}")

    return "\n".join(lines)


def read_text_from_bytes(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def read_url_text(text: str) -> str:
    for line in text.splitlines():
        if line.lower().startswith("url="):
            return line.split("=", 1)[1].strip()

    return ""


def is_streamelements_share_url(url: str) -> bool:
    lowered = (url or "").lower()
    return "streamelements.com" in lowered and "/dashboard/overlays/share/" in lowered


def shortcut_entry_score_for_primary(shortcut: dict, pack_slug: str) -> int:
    file_name = str(shortcut.get("file", ""))
    url = str(shortcut.get("url", ""))
    combined = f"{file_name} {url}".lower()
    score = 0

    if is_streamelements_share_url(url):
        score += 100
    else:
        score -= 100

    if "twitch" in combined:
        score += 30
    if "youtube" in combined:
        score -= 10
    if "streamlabs" in combined:
        score -= 50
    if "setup" in combined or "guide" in combined or "help" in combined or "contact" in combined:
        score -= 25

    for token in pack_slug.split("-"):
        if len(token) >= 4 and token in combined:
            score += 6

    if "streamelements - twitch widget" in combined:
        score -= 5

    return score


def choose_primary_streamelements_share_url(shortcuts: list[dict], pack_slug: str) -> str:
    candidates = [item for item in shortcuts if is_streamelements_share_url(str(item.get("url", "")))]

    if not candidates:
        return ""

    candidates.sort(key=lambda item: shortcut_entry_score_for_primary(item, pack_slug), reverse=True)
    return str(candidates[0].get("url", ""))


def is_url_only_stream_elements_widget(pack_info: dict) -> bool:
    if not isinstance(pack_info, dict):
        return False

    return (
        pack_info.get("pack_type") == "stream_elements_widget"
        and not pack_info.get("widget_bundle")
        and bool(pack_info.get("primary_share_url"))
    )


def normalize_user_url(url: str) -> str:
    return (url or "").strip().strip('"').strip("'")


def looks_like_browser_source_url(url: str) -> bool:
    cleaned = normalize_user_url(url).lower()

    if not cleaned:
        return False

    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        return False

    if "streamelements.com/dashboard/overlays/share/" in cleaned:
        return False

    return True

def url_to_safe_asset_name(url: str, used_names: set[str]) -> str:
    parsed = urllib.parse.urlparse(url)
    base = Path(parsed.path).name or "asset"
    base = urllib.parse.unquote(base)
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-") or "asset"

    if "." not in base:
        base = base + ".bin"

    candidate = base
    counter = 1
    while candidate.lower() in used_names:
        stem = Path(base).stem
        suffix = Path(base).suffix or ".bin"
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1

    used_names.add(candidate.lower())
    return candidate


def make_absolute_url(base_url: str, maybe_url: str) -> str:
    maybe_url = (maybe_url or "").strip()
    if not maybe_url:
        return ""
    if maybe_url.startswith("data:") or maybe_url.startswith("blob:") or maybe_url.startswith("javascript:"):
        return ""
    return urllib.parse.urljoin(base_url, maybe_url)


def download_url_bytes(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 SEUnpacker/0.5",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()



def get_render_capture_file() -> Path:
    return app_data_dir() / "streamelements-render-capture.json"


def capture_rendered_overlay_html_with_webview(final_overlay_url: str, log_func=None, wait_seconds: int = 8) -> tuple[bool, str, str]:
    """Capture the rendered DOM of a StreamElements browser-source URL."""
    if webview is None:
        return False, "Embedded browser support is not installed, so rendered DOM capture is unavailable.", ""

    def log(message: str):
        if log_func:
            try:
                log_func(message)
            except Exception:
                pass

    output_path = get_render_capture_file()
    try:
        if output_path.exists():
            output_path.unlink()
    except Exception:
        pass

    try:
        width, height = get_half_screen_size()
    except Exception:
        width, height = 900, 720

    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--se-capture-rendered",
        final_overlay_url,
        str(width),
        str(height),
        str(output_path),
        str(wait_seconds),
    ]

    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    except Exception:
        creationflags = 0

    try:
        log("Opening embedded browser to capture rendered StreamElements widget source...")
        process = subprocess.Popen(command, creationflags=creationflags)
        deadline = time.time() + max(20, wait_seconds + 18)
        while time.time() < deadline:
            if output_path.exists():
                break
            if process.poll() is not None and not output_path.exists():
                break
            time.sleep(0.25)

        if process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass

        if not output_path.exists():
            return False, "Rendered capture helper did not return HTML.", ""

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        if not payload.get("success"):
            return False, payload.get("message", "Rendered capture failed."), ""

        html = payload.get("html", "") or ""
        if len(html.strip()) < 300:
            return False, "Rendered capture returned too little HTML to be useful.", html

        return True, payload.get("message", "Captured rendered StreamElements DOM."), html
    except Exception as exc:
        return False, f"Rendered capture failed: {exc}", ""


def looks_like_shell_only_capture(html: str) -> bool:
    """Return True when the capture looks like the SE app shell, not widget content."""
    lowered = (html or "").lower()
    if not lowered.strip():
        return True

    shell_markers = [
        'id="root"',
        "streamelements.com/z/s.js",
        "/z/s.js",
        "vendor-react",
        "index-",
    ]
    widget_markers = [
        "rotator",
        "event",
        "alert",
        "widget",
        "seunpacker",
        "overlay",
        "canvas",
        "video",
        "img",
    ]

    body_match = re.search(r"(?is)<body[^>]*>(.*?)</body>", html or "")
    body_text = body_match.group(1).strip() if body_match else lowered
    stripped_body = re.sub(r"(?is)<script.*?</script>", "", body_text)
    stripped_body = re.sub(r"(?is)<style.*?</style>", "", stripped_body)
    visibleish = re.sub(r"<[^>]+>", "", stripped_body).strip()

    if 'id="root"' in lowered and len(visibleish) < 20:
        return True

    if any(marker in lowered for marker in shell_markers) and not any(marker in stripped_body.lower() for marker in widget_markers):
        return True

    return False


def localize_html_assets(source_url: str, html: str, pack_dir: Path, log_func=None) -> tuple[str, int]:
    """Download and rewrite common remote assets referenced by the given HTML."""
    def log(message: str):
        if log_func:
            try:
                log_func(message)
            except Exception:
                pass

    capture_dir = pack_dir / "captured-assets"
    capture_dir.mkdir(parents=True, exist_ok=True)

    used_names = set()
    replacements = {}
    asset_candidates = []

    patterns = [
        r'''(?i)(?:src|href|poster)\s*=\s*["']([^"']+)["']''',
        r'''(?i)url\(\s*["']?([^"')]+)["']?\s*\)''',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, html or ""):
            asset_candidates.append(match.group(1).strip())

    for original in asset_candidates:
        absolute = make_absolute_url(source_url, original)
        if not absolute:
            continue
        parsed = urllib.parse.urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if absolute in replacements:
            continue

        if looks_like_browser_source_url(absolute):
            log(f"Skipped hosted overlay dependency: {absolute}")
            continue

        try:
            asset_bytes = download_url_bytes(absolute, timeout=20)
            local_name = url_to_safe_asset_name(absolute, used_names)
            local_path = capture_dir / local_name
            local_path.write_bytes(asset_bytes)
            local_ref = f"captured-assets/{local_name}"
            replacements[original] = local_ref
            replacements[absolute] = local_ref
            log(f"Captured asset: {local_name}")
        except Exception as exc:
            log(f"Skipped remote asset: {absolute} ({exc})")

    localized_html = html or ""
    for old, new in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        localized_html = localized_html.replace(old, new)

    return localized_html, max(1, len(replacements) // 2) if replacements else 0

def capture_stream_elements_overlay_to_local(final_overlay_url: str, pack_dir: Path, log_func=None) -> tuple[bool, str, str]:
    """Try to localize a StreamElements browser-source URL into widget.html.

    v0.6.3 changes the order of operations: first capture the rendered DOM from
    the embedded StreamElements browser session, then only fall back to the raw
    network shell. This prevents URL widgets like Minimal Event Rotator from
    becoming blank after the original StreamElements overlay is removed.
    """
    url = normalize_user_url(final_overlay_url)
    if not looks_like_browser_source_url(url):
        return False, "URL does not look like a browser-source URL.", ""

    def log(message: str):
        if log_func:
            try:
                log_func(message)
            except Exception:
                pass

    pack_dir.mkdir(parents=True, exist_ok=True)
    capture_dir = pack_dir / "captured-assets"
    if capture_dir.exists():
        try:
            shutil.rmtree(capture_dir)
        except Exception:
            pass
    capture_dir.mkdir(parents=True, exist_ok=True)

    html = ""
    capture_source = ""
    rendered_ok, rendered_message, rendered_html = capture_rendered_overlay_html_with_webview(
        url,
        log_func=log,
        wait_seconds=10,
    )

    if rendered_ok and rendered_html and not looks_like_shell_only_capture(rendered_html):
        html = rendered_html
        capture_source = "rendered"
        (pack_dir / "streamelements-rendered.html").write_text(html, encoding="utf-8")
        log(rendered_message)
        log("Rendered capture included widget DOM. Localizing rendered overlay instead of the raw StreamElements shell.")
    else:
        if rendered_message:
            log(f"Rendered capture was not usable: {rendered_message}")
        if rendered_html:
            try:
                (pack_dir / "streamelements-rendered-shell.html").write_text(rendered_html, encoding="utf-8")
            except Exception:
                pass

        try:
            log("Capturing StreamElements overlay page...")
            raw = download_url_bytes(url, timeout=25)
            html = raw.decode("utf-8", errors="replace")
            (pack_dir / "streamelements-original.html").write_text(html, encoding="utf-8")
            capture_source = "static"
        except Exception as exc:
            return False, f"Could not download the StreamElements overlay page: {exc}", ""

    localized_html, asset_count = localize_html_assets(url, html, pack_dir, log_func=log)

    if "</head>" in localized_html.lower():
        transparent_css = """
<style id=\"seunpacker-local-overlay-fix\">
html, body {
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    height: 100% !important;
    background: transparent !important;
    overflow: hidden !important;
}
</style>
"""
        localized_html = re.sub(r"(?i)</head>", transparent_css + "</head>", localized_html, count=1)

    if looks_like_shell_only_capture(localized_html):
        widget_path = pack_dir / "widget.html"
        blank_html = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SEUnpacker Capture Failed</title>
<style>html,body{margin:0;padding:0;width:100%;height:100%;background:transparent;overflow:hidden;}</style>
</head>
<body></body>
</html>
'''
        widget_path.write_text(blank_html, encoding="utf-8")
        return False, "Local capture only found the StreamElements runtime shell, not the actual widget payload.", blank_html

    widget_path = pack_dir / "widget.html"
    widget_path.write_text(localized_html, encoding="utf-8")

    if capture_source == "rendered":
        return True, f"Captured rendered overlay locally with {asset_count} assets.", localized_html
    if asset_count:
        return True, f"Captured static overlay locally with {asset_count} assets.", localized_html
    return True, "Captured overlay page locally. No external static assets were found.", localized_html


def is_dashboard_share_url(url: str) -> bool:
    return is_streamelements_share_url(normalize_user_url(url))


def is_forced_url_widget_pack(zip_path: Path, shortcut_entries: list[dict], images: list[str], audio: list[str], video: list[str]) -> bool:
    pack_name = safe_slug(zip_path.name).lower()
    joined_shortcuts = " ".join(str(item.get("file", "")) for item in shortcut_entries).lower()
    joined_urls = " ".join(str(item.get("url", "")) for item in shortcut_entries).lower()
    combined = f"{pack_name} {joined_shortcuts} {joined_urls}"

    has_media = bool(images or audio or video)
    has_streamelements_share = any(
        is_streamelements_share_url(str(item.get("url", "")))
        for item in shortcut_entries
    )

    if not shortcut_entries or not has_streamelements_share:
        return False

    # Hard override for known widget-style StreamElements share-link packs.
    # Minimal Event Rotator has only .url shortcuts and no local media, so it must
    # become an overlay widget. It should never enter the alert generator.
    strong_widget_markers = [
        "minimal event rotator",
        "minimal-event-rotator",
        "event rotator",
        "event-rotator",
        "event bar",
        "event-bar",
        "2. widget",
        "/widget/",
        "\\widget\\",
        "streamelements - twitch widget",
        "streamelements - youtube widget",
        "twitch widget",
        "youtube widget",
    ]

    if any(marker in combined for marker in strong_widget_markers):
        return True

    if not has_media and "widget" in combined:
        return True

    if not has_media and "rotator" in combined:
        return True

    return False


def classify_shortcut_pack(zip_path: Path, shortcut_entries: list[dict], images: list[str], audio: list[str], video: list[str]) -> str:
    pack_name = safe_slug(zip_path.name).lower()
    joined_shortcuts = " ".join(str(item.get("file", "")) for item in shortcut_entries).lower()
    joined_urls = " ".join(str(item.get("url", "")) for item in shortcut_entries).lower()
    combined = f"{pack_name} {joined_shortcuts} {joined_urls}"

    has_media = bool(images or audio or video)
    has_shortcuts = bool(shortcut_entries)
    has_streamelements_share = any(is_streamelements_share_url(str(item.get("url", ""))) for item in shortcut_entries)

    if is_forced_url_widget_pack(zip_path, shortcut_entries, images, audio, video):
        return "stream_elements_widget"

    widget_keywords = [
        "widget",
        "rotator",
        "event rotator",
        "event-rotator",
        "event bar",
        "event-bar",
        "goal",
        "slider",
        "overlay",
    ]
    alert_keywords = [
        "alert",
        "alerts",
        "/alerts/",
        "alert install",
        "alert box",
        "alert_box",
    ]

    has_widget_keyword = any(word in combined for word in widget_keywords)
    has_alert_keyword = any(word in combined for word in alert_keywords)

    if has_shortcuts and has_streamelements_share and not has_media and has_widget_keyword:
        return "stream_elements_widget"

    if has_shortcuts and has_streamelements_share and has_alert_keyword:
        return "alert_pack"

    if has_shortcuts and has_streamelements_share and not has_media:
        return "stream_elements_widget"

    if has_shortcuts and not has_media and has_widget_keyword:
        return "stream_elements_widget"

    if not has_streamelements_share:
        return "alert_pack"

    alert_score = 0
    widget_score = 0

    if has_alert_keyword:
        alert_score += 10
    if has_media:
        alert_score += 6

    for word in widget_keywords:
        if word in combined:
            widget_score += 5

    if not has_media:
        widget_score += 8

    return "stream_elements_widget" if widget_score > alert_score else "alert_pack"


def firebot_record_is_seunpacker(record) -> bool:
    if not isinstance(record, dict):
        return False

    name = str(record.get("name", ""))
    if name.startswith("SEUnpacker - "):
        return True

    metadata = record.get("metadata")
    if isinstance(metadata, dict) and str(metadata.get("createdBy", "")) == "SEUnpacker":
        return True

    try:
        raw = json.dumps(record)
    except Exception:
        raw = str(record)

    return "SEUnpacker" in raw or "seunpacker" in raw


def firebot_record_matches_seunpacker_pack(record, pack_slug: str) -> bool:
    """Return True only for SEUnpacker records belonging to the selected pack.

    v0.5.1 removed every SEUnpacker widget/preset during install. That made a
    new widget replace the previous one. v0.5.2 only replaces records for the
    same pack slug, so multiple overlay widgets can coexist.
    """
    if not isinstance(record, dict) or not pack_slug:
        return False

    expected_prefix = f"SEUnpacker - {pack_slug} - "
    safe_pack_name = safe_firebot_display_name(pack_slug)
    legacy_space_pack_name = re.sub(r"[^A-Za-z0-9_ ]+", " ", str(pack_slug).replace("-", " "))
    legacy_space_pack_name = re.sub(r"\s+", " ", legacy_space_pack_name).strip()
    expected_safe_prefix = f"SEUnpacker_{safe_pack_name}_"
    expected_legacy_space_prefix = f"SEUnpacker {legacy_space_pack_name} "
    current_display_name = safe_firebot_display_name(legacy_space_pack_name, max_length=50)
    name = str(record.get("name", ""))
    if (
        name == current_display_name
        or name.startswith(expected_prefix)
        or name.startswith(expected_safe_prefix)
        or name.startswith(expected_legacy_space_prefix)
    ):
        return True

    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        if str(metadata.get("createdBy", "")) == "SEUnpacker" and str(metadata.get("packSlug", "")) == pack_slug:
            return True

    try:
        raw = json.dumps(record)
    except Exception:
        raw = str(record)

    resource_hint = f"SEUnpacker/{pack_slug}/"
    resource_hint_alt = f"SEUnpacker\\{pack_slug}\\"
    return (
        expected_prefix in raw
        or expected_safe_prefix in raw
        or expected_legacy_space_prefix in raw
        or resource_hint in raw
        or resource_hint_alt in raw
    )


def cleanup_seunpacker_firebot_json_records(pack_slug: str = "", include_widgets: bool = False, include_presets: bool = False) -> dict:
    """Clean Firebot JSON records safely.

    By default this only cleans old SEUnpacker events. Widget and preset cleanup
    is intentionally opt-in and pack-specific so installing one overlay widget
    does not delete another SEUnpacker overlay widget that the user wants to keep.
    """
    result = {
        "events_removed": 0,
        "widgets_removed": 0,
        "presets_removed": 0,
        "backups": [],
    }

    events_path = get_firebot_events_json_path()
    if events_path.exists():
        backup_path = backup_file(events_path, "SEUnpacker_Backups")
        result["backups"].append(str(backup_path))
        events_data = load_firebot_events_file(events_path)
        before = len(events_data.get("mainEvents", []))

        if pack_slug:
            events_data["mainEvents"] = [
                event for event in events_data.get("mainEvents", [])
                if not firebot_record_matches_seunpacker_pack(event, pack_slug)
            ]
        else:
            events_data["mainEvents"] = [
                event for event in events_data.get("mainEvents", [])
                if not firebot_record_is_seunpacker(event)
            ]

        result["events_removed"] = before - len(events_data["mainEvents"])
        save_firebot_events_file(events_path, events_data)

    if include_widgets:
        widgets_path = get_firebot_overlay_widgets_json_path()
        if widgets_path.exists():
            backup_path = backup_file(widgets_path, "SEUnpacker_Backups")
            result["backups"].append(str(backup_path))
            widgets = load_firebot_overlay_widgets_file(widgets_path)
            before = len(widgets)
            if pack_slug:
                widgets = [widget for widget in widgets if not firebot_record_matches_seunpacker_pack(widget, pack_slug)]
            else:
                widgets = [widget for widget in widgets if not firebot_record_is_seunpacker(widget)]
            result["widgets_removed"] = before - len(widgets)
            save_firebot_overlay_widgets_file(widgets_path, widgets)

    if include_presets:
        presets_path = get_firebot_preset_effect_lists_json_path()
        if presets_path.exists():
            backup_path = backup_file(presets_path, "SEUnpacker_Backups")
            result["backups"].append(str(backup_path))
            presets = load_firebot_preset_effect_lists_file(presets_path)
            before = len(presets)
            if pack_slug:
                presets = [preset for preset in presets if not firebot_record_matches_seunpacker_pack(preset, pack_slug)]
            else:
                presets = [preset for preset in presets if not firebot_record_is_seunpacker(preset)]
            result["presets_removed"] = before - len(presets)
            save_firebot_preset_effect_lists_file(presets_path, presets)

    return result


def readable_pack_name_from_slug(pack_slug: str) -> str:
    text = str(pack_slug or "").strip()
    text = re.sub(r"[-_]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return safe_firebot_display_name(text.title() if text else "Unknown Pack", max_length=50)


def extract_seunpacker_pack_slugs_from_record(record) -> set[str]:
    slugs = set()

    if not isinstance(record, dict):
        return slugs

    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        pack_slug = str(metadata.get("packSlug", "")).strip()
        if pack_slug:
            slugs.add(pack_slug)

    name = str(record.get("name", ""))
    match = re.search(r"SEUnpacker\s*-\s*([A-Za-z0-9_-]+)\s*-", name)
    if match:
        slugs.add(match.group(1))

    try:
        raw = json.dumps(record)
    except Exception:
        raw = str(record)

    for match in re.finditer(r"SEUnpacker[/\\]([A-Za-z0-9_-]+)[/\\]", raw):
        slugs.add(match.group(1))

    for match in re.finditer(r"overlay-resources[/\\]SEUnpacker[/\\]([A-Za-z0-9_-]+)[/\\]", raw):
        slugs.add(match.group(1))

    return {slug for slug in slugs if slug}


def discover_installed_seunpacker_packs() -> list[dict]:
    packs: dict[str, dict] = {}

    def ensure_pack(slug: str):
        if not slug:
            return None
        if slug not in packs:
            packs[slug] = {
                "pack_slug": slug,
                "display_name": readable_pack_name_from_slug(slug),
                "has_resources": False,
                "events": 0,
                "widgets": 0,
                "presets": 0,
            }
        return packs[slug]

    resources_root = get_appdata_firebot_resources()
    if resources_root.exists():
        for child in resources_root.iterdir():
            if child.is_dir():
                pack = ensure_pack(child.name)
                if pack:
                    pack["has_resources"] = True

    events_path = get_firebot_events_json_path()
    if events_path.exists():
        events_data = load_firebot_events_file(events_path)
        for event in events_data.get("mainEvents", []):
            if not firebot_record_is_seunpacker(event):
                continue
            for slug in extract_seunpacker_pack_slugs_from_record(event):
                pack = ensure_pack(slug)
                if pack:
                    pack["events"] += 1

    widgets_path = get_firebot_overlay_widgets_json_path()
    if widgets_path.exists():
        for widget in load_firebot_overlay_widgets_file(widgets_path):
            if not firebot_record_is_seunpacker(widget):
                continue
            for slug in extract_seunpacker_pack_slugs_from_record(widget):
                pack = ensure_pack(slug)
                if pack:
                    pack["widgets"] += 1

    presets_path = get_firebot_preset_effect_lists_json_path()
    if presets_path.exists():
        for preset in load_firebot_preset_effect_lists_file(presets_path):
            if not firebot_record_is_seunpacker(preset):
                continue
            for slug in extract_seunpacker_pack_slugs_from_record(preset):
                pack = ensure_pack(slug)
                if pack:
                    pack["presets"] += 1

    return sorted(packs.values(), key=lambda item: item["display_name"].lower())


def uninstall_seunpacker_pack(pack_slug: str) -> dict:
    running, reason = is_firebot_running()
    if running:
        raise RuntimeError(
            "Firebot appears to be running.\n\n"
            f"{reason}\n\n"
            "Close Firebot completely before uninstalling SEUnpacker packs."
        )

    if not pack_slug:
        raise RuntimeError("No pack was selected for uninstall.")

    result = cleanup_seunpacker_firebot_json_records(
        pack_slug=pack_slug,
        include_widgets=True,
        include_presets=True,
    )

    resources_removed = False
    resources_path = get_appdata_firebot_resources() / pack_slug
    if resources_path.exists():
        shutil.rmtree(resources_path)
        resources_removed = True

    result["resources_removed"] = resources_removed
    result["resources_path"] = str(resources_path)
    return result


def nuke_all_seunpacker_installs() -> dict:
    running, reason = is_firebot_running()
    if running:
        raise RuntimeError(
            "Firebot appears to be running.\n\n"
            f"{reason}\n\n"
            "Close Firebot completely before removing SEUnpacker installs."
        )

    result = cleanup_seunpacker_firebot_json_records(
        pack_slug="",
        include_widgets=True,
        include_presets=True,
    )

    resources_root = get_appdata_firebot_resources()
    resources_removed = 0
    if resources_root.exists():
        for child in list(resources_root.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
                resources_removed += 1
            elif child.is_file():
                child.unlink()
                resources_removed += 1
        try:
            resources_root.rmdir()
        except Exception:
            pass

    result["resources_removed"] = resources_removed
    result["resources_path"] = str(resources_root)
    return result


def normalize_zip_name(name: str) -> str:
    return name.replace("\\", "/").strip("/")


def collect_zip_items(zip_path: Path) -> list[dict]:
    collected = []

    with zipfile.ZipFile(zip_path, "r") as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue

            name = normalize_zip_name(item.filename)
            data = archive.read(item)

            collected.append(
                {
                    "name": name,
                    "data": data,
                    "source": "outer",
                }
            )

            if name.lower().endswith(".zip"):
                try:
                    nested_bytes = BytesIO(data)
                    with zipfile.ZipFile(nested_bytes, "r") as nested_archive:
                        for nested_item in nested_archive.infolist():
                            if nested_item.is_dir():
                                continue

                            nested_name = normalize_zip_name(nested_item.filename)
                            nested_data = nested_archive.read(nested_item)

                            collected.append(
                                {
                                    "name": f"{Path(name).stem}/{nested_name}",
                                    "data": nested_data,
                                    "source": f"nested:{name}",
                                }
                            )
                except Exception:
                    pass

    return collected


def get_lower_basename(name: str) -> str:
    return Path(name).name.lower()


def parse_json_text(text: str, default_value):
    try:
        return json.loads(text)
    except Exception:
        return default_value


def sanitize_widget_html_fragment(raw_html: str) -> str:
    cleaned = raw_html
    cleaned = re.sub(r"(?is)</body\s*>", "", cleaned)
    cleaned = re.sub(r"(?is)</html\s*>", "", cleaned)
    return cleaned.strip()


def find_stream_elements_widget_bundle(items: list[dict]) -> dict | None:
    grouped = {}

    for item in items:
        name = normalize_zip_name(item["name"])
        folder = str(Path(name).parent).replace("\\", "/")
        base = get_lower_basename(name)

        grouped.setdefault(folder, {})
        grouped[folder][base] = item

    required = {"html.txt", "css.txt", "js.txt", "fields.txt", "data.txt", "widget.ini"}

    best_folder = None
    best_score = -1

    for folder, files in grouped.items():
        score = sum(1 for req in required if req in files)

        if score > best_score:
            best_score = score
            best_folder = folder

    if best_folder is None or best_score < 4:
        return None

    files = grouped[best_folder]

    return {
        "folder": best_folder,
        "html": read_text_from_bytes(files["html.txt"]["data"]) if "html.txt" in files else "",
        "css": read_text_from_bytes(files["css.txt"]["data"]) if "css.txt" in files else "",
        "js": read_text_from_bytes(files["js.txt"]["data"]) if "js.txt" in files else "",
        "fields": read_text_from_bytes(files["fields.txt"]["data"]) if "fields.txt" in files else "{}",
        "data": read_text_from_bytes(files["data.txt"]["data"]) if "data.txt" in files else "{}",
        "widget_ini": read_text_from_bytes(files["widget.ini"]["data"]) if "widget.ini" in files else "",
        "score": best_score,
    }


def analyze_zip(zip_path: Path) -> dict:
    items = collect_zip_items(zip_path)
    widget_bundle = find_stream_elements_widget_bundle(items)

    result = {
        "pack_type": "alert_pack",
        "images": [],
        "audio": [],
        "video": [],
        "shortcuts": [],
        "shortcut_urls": [],
        "widget_files": [],
        "other": [],
        "nested_zips": [],
    }

    for item in items:
        name = item["name"]
        ext = Path(name).suffix.lower()
        base = get_lower_basename(name)

        if ext == ".zip":
            result["nested_zips"].append(name)
        elif ext in SUPPORTED_IMAGE_EXTENSIONS:
            result["images"].append(name)
        elif ext in SUPPORTED_AUDIO_EXTENSIONS:
            result["audio"].append(name)
        elif ext in SUPPORTED_VIDEO_EXTENSIONS:
            result["video"].append(name)
        elif ext in SUPPORTED_SHORTCUT_EXTENSIONS:
            result["shortcuts"].append(name)
            result["shortcut_urls"].append(
                {
                    "file": name,
                    "url": read_url_text(read_text_from_bytes(item["data"])),
                }
            )
        elif base in {"html.txt", "css.txt", "js.txt", "fields.txt", "data.txt", "widget.ini"}:
            result["widget_files"].append(name)
        else:
            result["other"].append(name)

    if widget_bundle is not None:
        result["pack_type"] = "stream_elements_widget"
    else:
        result["pack_type"] = classify_shortcut_pack(
            zip_path=zip_path,
            shortcut_entries=result["shortcut_urls"],
            images=result["images"],
            audio=result["audio"],
            video=result["video"],
        )

    return result

def extract_pack(zip_path: Path, output_root: Path) -> dict:
    pack_slug = safe_slug(zip_path.name)
    pack_dir = output_root / pack_slug
    assets_dir = pack_dir / "assets"
    source_dir = pack_dir / "source"

    pack_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    items = collect_zip_items(zip_path)
    analysis = analyze_zip(zip_path)
    widget_bundle = find_stream_elements_widget_bundle(items)

    extracted_images = []
    extracted_audio = []
    extracted_video = []
    shortcut_urls = []
    widget_source_files = []

    supported_asset_extensions = (
        SUPPORTED_IMAGE_EXTENSIONS
        | SUPPORTED_AUDIO_EXTENSIONS
        | SUPPORTED_VIDEO_EXTENSIONS
        | SUPPORTED_SHORTCUT_EXTENSIONS
    )

    expected_asset_names = set()
    expected_source_names = set()

    for item in items:
        source_name = item["name"]
        source_path = Path(source_name)
        ext = source_path.suffix.lower()
        base = get_lower_basename(source_name)

        if ext in supported_asset_extensions:
            clean_name = source_path.name
            target_path = assets_dir / clean_name
            expected_asset_names.add(clean_name)

            with open(target_path, "wb") as dst:
                dst.write(item["data"])

            if ext in SUPPORTED_IMAGE_EXTENSIONS:
                extracted_images.append(clean_name)
            elif ext in SUPPORTED_AUDIO_EXTENSIONS:
                extracted_audio.append(clean_name)
            elif ext in SUPPORTED_VIDEO_EXTENSIONS:
                extracted_video.append(clean_name)
            elif ext in SUPPORTED_SHORTCUT_EXTENSIONS:
                url = read_url_text(read_text_from_bytes(item["data"]))
                shortcut_urls.append(
                    {
                        "file": clean_name,
                        "url": url,
                    }
                )

        if base in {"html.txt", "css.txt", "js.txt", "fields.txt", "data.txt", "widget.ini"}:
            clean_source_name = base
            target_source_path = source_dir / clean_source_name
            expected_source_names.add(clean_source_name)

            with open(target_source_path, "wb") as dst:
                dst.write(item["data"])

            widget_source_files.append(clean_source_name)

    for existing_file in assets_dir.iterdir():
        if existing_file.is_file() and existing_file.name not in expected_asset_names:
            try:
                existing_file.unlink()
            except PermissionError:
                pass

    for existing_file in source_dir.iterdir():
        if existing_file.is_file() and existing_file.name not in expected_source_names:
            try:
                existing_file.unlink()
            except PermissionError:
                pass

    final_pack_type = analysis["pack_type"]
    if is_forced_url_widget_pack(zip_path, analysis.get("shortcut_urls", []), analysis.get("images", []), analysis.get("audio", []), analysis.get("video", [])):
        final_pack_type = "stream_elements_widget"
        analysis["pack_type"] = "stream_elements_widget"

    return {
        "pack_slug": pack_slug,
        "source_zip": str(zip_path.resolve()),
        "source_zip_mtime": zip_path.stat().st_mtime,
        "pack_dir": pack_dir,
        "assets_dir": assets_dir,
        "source_dir": source_dir,
        "pack_type": final_pack_type,
        "images": extracted_images,
        "audio": extracted_audio,
        "video": extracted_video,
        "shortcuts": shortcut_urls,
        "primary_share_url": choose_primary_streamelements_share_url(shortcut_urls, pack_slug),
        "widget_bundle": widget_bundle,
        "widget_source_files": sorted(set(widget_source_files)),
        "analysis": analysis,
    }


def generate_alert_html(pack_info: dict) -> str:
    images = pack_info["images"]
    image_array = ",\n        ".join([f'"assets/{name}"' for name in images])

    if not image_array:
        image_array = '"assets/placeholder.png"'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>SEUnpacker Firebot Alert</title>
<style>
    html, body {{
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
        background: transparent;
        overflow: hidden;
        font-family: Arial, Helvetica, sans-serif;
    }}

    .alert-wrap {{
        position: fixed;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        pointer-events: none;
    }}

    .alert-card {{
        min-width: 520px;
        max-width: 760px;
        padding: 28px 38px;
        border-radius: 28px;
        background: rgba(20, 10, 30, 0.92);
        border: 3px solid rgba(255, 160, 55, 0.95);
        box-shadow:
            0 0 30px rgba(255, 120, 20, 0.55),
            0 0 80px rgba(120, 30, 180, 0.45);
        text-align: center;
        animation: popIn 0.55s ease-out forwards, floaty 3s ease-in-out infinite;
        transform: scale(0.8);
        opacity: 0;
    }}

    .icon {{
        width: 150px;
        height: 150px;
        object-fit: contain;
        margin-bottom: 8px;
        animation: wiggle 1.1s ease-in-out infinite;
        filter: drop-shadow(0 0 18px rgba(255, 170, 40, 0.75));
    }}

    .title {{
        color: #ffb13b;
        font-size: 34px;
        font-weight: 900;
        letter-spacing: 2px;
        text-transform: uppercase;
        text-shadow: 0 0 12px rgba(255, 120, 20, 0.8);
        margin-top: 6px;
    }}

    .username {{
        color: #ffffff;
        font-size: 54px;
        font-weight: 900;
        line-height: 1.08;
        margin-top: 8px;
        text-shadow:
            0 0 10px rgba(255, 255, 255, 0.9),
            0 0 24px rgba(190, 80, 255, 0.85);
        word-break: break-word;
    }}

    .subtext {{
        color: #d8b8ff;
        font-size: 24px;
        font-weight: 700;
        margin-top: 12px;
    }}

    .sparkle {{
        position: absolute;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #ffb13b;
        box-shadow: 0 0 16px #ffb13b;
        animation: sparkle 1.8s ease-out forwards;
    }}

    @keyframes popIn {{
        0% {{
            transform: scale(0.55) rotate(-4deg);
            opacity: 0;
        }}
        70% {{
            transform: scale(1.08) rotate(2deg);
            opacity: 1;
        }}
        100% {{
            transform: scale(1) rotate(0deg);
            opacity: 1;
        }}
    }}

    @keyframes floaty {{
        0%, 100% {{
            translate: 0 0;
        }}
        50% {{
            translate: 0 -12px;
        }}
    }}

    @keyframes wiggle {{
        0%, 100% {{
            transform: rotate(-3deg) scale(1);
        }}
        50% {{
            transform: rotate(4deg) scale(1.06);
        }}
    }}

    @keyframes sparkle {{
        0% {{
            transform: translate(0, 0) scale(0.4);
            opacity: 0;
        }}
        25% {{
            opacity: 1;
        }}
        100% {{
            transform: translate(var(--x), var(--y)) scale(1.2);
            opacity: 0;
        }}
    }}

    .fade-out {{
        animation: fadeOut 0.65s ease-in forwards;
    }}

    @keyframes fadeOut {{
        to {{
            opacity: 0;
            transform: scale(0.92);
        }}
    }}
</style>
</head>
<body>
<div class="alert-wrap">
    <div class="alert-card" id="alertCard">
        <img class="icon" id="alertIcon" src="" alt="" />
        <div class="title" id="alertTitle">NEW FOLLOWER</div>
        <div class="username" id="alertUser">Someone</div>
        <div class="subtext" id="alertSubtext">triggered the alert</div>
    </div>
</div>

<script>
    const ALERT_TITLE = "NEW FOLLOWER";
    const ALERT_USER = "$username";
    const ALERT_SUBTEXT = "triggered the alert";

    const DISPLAY_SECONDS = 7;

    const IMAGES = [
        {image_array}
    ];

    function pickRandom(items) {{
        return items[Math.floor(Math.random() * items.length)];
    }}

    function createSparkle() {{
        const sparkle = document.createElement("div");
        sparkle.className = "sparkle";

        const startX = window.innerWidth / 2 + (Math.random() * 300 - 150);
        const startY = window.innerHeight / 2 + (Math.random() * 200 - 100);

        sparkle.style.left = startX + "px";
        sparkle.style.top = startY + "px";
        sparkle.style.setProperty("--x", (Math.random() * 420 - 210) + "px");
        sparkle.style.setProperty("--y", (Math.random() * 300 - 150) + "px");

        document.body.appendChild(sparkle);

        setTimeout(() => sparkle.remove(), 2000);
    }}

    function startAlert() {{
        document.getElementById("alertTitle").textContent = ALERT_TITLE;
        document.getElementById("alertUser").textContent = ALERT_USER;
        document.getElementById("alertSubtext").textContent = ALERT_SUBTEXT;
        document.getElementById("alertIcon").src = pickRandom(IMAGES);

        const sparkleTimer = setInterval(() => {{
            for (let i = 0; i < 4; i++) {{
                createSparkle();
            }}
        }}, 250);

        setTimeout(() => {{
            clearInterval(sparkleTimer);
            document.getElementById("alertCard").classList.add("fade-out");
        }}, DISPLAY_SECONDS * 1000);
    }}

    startAlert();
</script>
</body>
</html>
"""
    return html



MINIMAL_EVENT_ROTATOR_HTML = '<div class="widget-container">\n    <div class="wrapper">\n        <div class="events">\n            <div class="text">\n                Placeholder <span class="highlight">#404</span>\n            </div>\n        </div>\n        <div class="train">\n            <div class="empty">0</div>\n            <div class="fill">0</div>\n        </div>\n    </div>\n</div>'
MINIMAL_EVENT_ROTATOR_CSS = "@import url('https://fonts.googleapis.com/css2?family={design_font}:wght@100;200;300;400;500;600;700;800;900&display=swap');\n\n:root {\n    --primary-color: {{design_background_color}};\n    --font-color: {{design_font_color}};\n    --font-size: {{design_font_size}}px;\n    --font-weight: {{font_weight}};\n    --highlight-weight: {{highlight_font_weight}};\n    --event-align: flex-start;\n    --padding: {{design_padding}}px;\n    --train-fill-color: {{design_train_fill_color}};\n    --train-fill-font-color: {{design_train_fill_font_color}};\n    --train-empty-color: {{design_train_empty_color}};\n    --train-empty-font-color: {{design_train_empty_font_color}};\n    --train-font-size: {{design_train_font_size}}px;\n    --border-radius: {{design_border_radius}}px;\n    --icon-size: {{design_icon_size}}px;\n    --icon-text-spacing: {{icon_text_spacing}}px;\n}\n\nbody {\n    margin: 0;\n    padding: 0;\n    width: 100%;\n    height: 100%;\n}\n\n.widget-container {\n    width: 100%;\n    height: 100%;\n    font-family: '{design_font}', cursive !important;\n    font-weight: {{font_weight}};\n}\n\n.widget-container .wrapper {\n    width: 100%;\n    height: 100%;\n    display: flex;\n    border-radius: var(--border-radius);\n    overflow: hidden;\n}\n\n.widget-container .wrapper .events {\n    height: 100%;\n    padding-left: var(--padding);\n    padding-right: var(--padding);\n    color: var(--font-color);\n    font-size: var(--font-size);\n    background: var(--primary-color);\n    overflow: hidden;\n    display: flex;\n    justify-content: var(--event-align);\n    align-items: center;\n}\n\n.widget-container .wrapper .events .text {\n    width: 100%;\n    white-space: nowrap;\n    display: flex;\n    align-items: center;\n    gap: var(--icon-text-spacing);\n    background: linear-gradient(90deg, var(--font-color) 90%, transparent 100%);\n    -webkit-background-clip: text;\n    -webkit-text-fill-color: transparent;\n}\n\n.widget-container .wrapper .events .text .icon {\n    width: var(--icon-size);\n    height: var(--icon-size);\n    display: flex;\n    justify-content: center;\n    align-items: center;\n}\n\n.widget-container .wrapper .events .text .icon img {\n    max-width: var(--icon-size);\n    max-height: var(--icon-size);\n}\n\n.widget-container .wrapper .events .text .icon.overlay {\n    position: absolute;\n}\n\n.widget-container .wrapper .events .highlight {\n    font-weight: {{highlight_font_weight}};\n}\n\n.widget-container .wrapper .train {\n    position: relative;\n    display: flex;\n    justify-content: center;\n    align-items: center;\n    overflow: hidden;\n}\n\n.widget-container .wrapper .train .fill,\n.widget-container .wrapper .train .empty {\n    position: absolute;\n    width: 100%;\n    height: 100%;\n    font-size: var(--train-font-size);\n    font-weight: bold;\n    display: flex;\n    justify-content: center;\n    align-items: center;\n}\n\n.widget-container .wrapper .train .fill {\n    background: var(--train-fill-color);\n    color: var(--train-fill-font-color);\n}\n\n.widget-container .wrapper .train .empty {\n    background: var(--train-empty-color);\n    color: var(--train-empty-font-color);\n}\n"
MINIMAL_EVENT_ROTATOR_JS = 'const h = $(".widget-container").height();\nconst w = $(".widget-container").width();\n\nlet state = {};\n\nlet train_state = {\n    active: false,\n    count: 0,\n    animated_count: 0,\n    duration: 300,\n};\n\nlet keys = [];\nlet pos = 0;\n\nconst ROTATE_DURATION = 1.5;\nconst ROTATE_INTERVAL = 5;\nlet TRAIN_EVENT = \'\';\n\nlet currency = \'$\';\n\nconst settings = {\n\t"follower-latest": {},\n    "subscriber-latest": {},\n    "cheer-latest": {},\n    "tip-latest": {},\n    "raid-latest": {},\n  \t\n}\n\nlet enable_icons = true;\n\nconst events = [\'follower-latest\', \'subscriber-latest\', \'tip-latest\', \'cheer-latest\', \'raid-latest\'];\nlet enabled_events = [];\n\nconst update_state = (s) => {  \n  \tconsole.log(\'update_state\', s)\n  \n  \t// Loop over events\n  \tfor (const event of enabled_events) {\n    \tlet res = settings[event].template.replaceAll(\'<<\', \'<span class="highlight">\').replaceAll(\'>>\', \'</span>\');\n      \n      \tconst name = s[event].name;\n      \tlet amount = `${s[event].amount}`;\n      \tif (event == \'follower-latest\') amount = s[\'follower-total\'].count\n      \tconst plural_amount = amount ? (amount != 1 ? settings[event].plurals[1] : settings[event].plurals[0]) : settings[event].plurals[0];\n      \n      \tconst template = Handlebars.compile(res);\n      \t\n      \tres = template({\n        \tname, amount, plural_amount, currency\n        })\n      \n      \tstate[event] = `${enable_icons ? `<div class="icon overlay" style="background: ${settings[event].icon_overlay}; mask-size: cover; -webkit-mask-size: cover; mask-image: url(${settings[event].icon}); -webkit-mask-image: url(${settings[event].icon});"></div><div class="icon"><img src="${settings[event].icon}" /></div>` : \'\'}<div class="text-inner">${res}</div>`;\n    }\n}\n\nconst rotate = () => {\n    gsap.to(".events .text", {\n        y: h / 2 + $(".events .text").height(),\n        duration: ROTATE_DURATION / 2,\n        ease: "expo.in",\n        onComplete: () => {\n            // Update text\n            $(".events .text").html(state[keys[pos]]);\n            pos++;\n            if (pos == keys.length) pos = 0;\n\n            gsap.fromTo(\n                ".events .text",\n                {\n                    y: -(h / 2 + $(".events .text").height()),\n                },\n                {\n                    y: 0,\n                    duration: ROTATE_DURATION / 2,\n                    ease: "expo.out",\n                }\n            );\n        },\n    });\n};\n\nconst train_tl = gsap.timeline();\nconst update_train = (c) => {\n    train_tl.clear();\n\n    train_state.count += c;\n\n    if (!train_state.active) {\n        $(".train .empty").text(train_state.count);\n        $(".train .fill").text(train_state.count);\n\n        train_state.animated_count = train_state.count;\n\n        gsap.set(".train .fill", {\n            clipPath: "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)",\n        });\n\n        // Animate Train Block In\n        gsap.to(".train", {\n            width: h,\n            ease: "expo.inOut",\n            duration: 1,\n        });\n\n        gsap.to(\n            ".events",\n            {\n                width: "-=" + h,\n                ease: "expo.inOut",\n                duration: 1,\n            },\n            "<"\n        );\n    }\n\n    if (train_state.active) {\n        // Animate Fill\n        train_tl.to(".train .fill", {\n            clipPath: "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)",\n            duration: 1,\n            ease: "expo.inOut",\n        });\n\n        train_tl.to(\n            train_state,\n            {\n                animated_count: train_state.count,\n                duration: 1,\n                ease: "expo.inOut",\n                onUpdate: () => {\n                    $(".train .empty").text(\n                        Math.round(train_state.animated_count)\n                    );\n                    $(".train .fill").text(\n                        Math.round(train_state.animated_count)\n                    );\n                },\n            },\n            "<"\n        );\n    }\n\n    train_tl.to(".train .fill", {\n        clipPath: "polygon(0% 100%, 100% 100%, 100% 100%, 0% 100%)",\n        duration: train_state.duration,\n        ease: "linear",\n        onComplete: () => {\n            train_state.active = false;\n            train_state.count = 0;\n            train_state.animated_count = 0;\n\n            train_tl.to(".train", {\n                width: 0,\n                duration: 1,\n                ease: "expo.inOut",\n            });\n\n            train_tl.to(\n                ".events",\n                {\n                    width: "+=" + h,\n                    duration: 1,\n                    ease: "expo.inOut",\n                },\n                "<"\n            );\n        },\n    });\n\n    train_state.active = true;\n};\n\nconst load = (session_data) => {\n    // Update width and height of train.\n    $(".train").width(h);\n    $(".train").height(h);\n\n    $(".events").width(w - h);\n\n    gsap.set(".train", {\n        width: 0,\n    });\n\n    gsap.set(".events", {\n        width: "+=" + h,\n    });\n\n    // TODO: Update State\n  \tupdate_state(session_data);\n    keys = Object.keys(state);\n\n    // Start Rotator\n    rotate();\n    setInterval(rotate, ROTATE_INTERVAL * 1000);\n};\n\nconst fixBody = () => {\n\tconst style = $(\'body\').attr(\'style\');\n  \tif (style == undefined) return;\n  \tlet styles = style.split(\';\');\n  \tstyles = styles.filter((s) => s.startsWith(\'width\') || s.startsWith(\'height\'));\n  \t\n  \tfor (let style of styles) {\n    \tconst amount = style.split(\':\')[1];\n      \tif (!amount.endsWith(\'px\')) {\n        \t$(\'body\').css(style.split(\':\')[0], amount + \'px\');\n        }\n    }\n}\n\nwindow.addEventListener(\'onWidgetLoad\', (obj) => {\n  \tfixBody();\n  \n  \tcurrency = obj.detail.currency.symbol;\n  \n  \tconst fd = obj.detail.fieldData;\n  \t\n  \tenable_icons = fd[\'enable_icons\'];\n  \n  \tconsole.log(fd[`event-follower-latest-enable`])\n  \n  \tTRAIN_EVENT = fd[\'train-event\'];\n  \ttrain_state.duration = fd[\'train-duration\'];\n  \n  \tfor (const event of events) {\n    \tif (fd[`event-${event}-enable`] == true) {\n        \tenabled_events.push(event);\n          \n          \tsettings[event].template = fd[`event-${event}-template`]\n          \tsettings[event].plurals = [fd[`event-${event}-single`], fd[`event-${event}-multi`]]\n          \tsettings[event].icon = fd[`event-${event}-icon`]\n          \tsettings[event].icon_overlay = fd[`event-${event}-icon-overlay`]\n        }\n    }\n  \n  \tconsole.log(enabled_events, settings);\n  \n  \tload(obj.detail.session.data)\n})\n\nwindow.addEventListener(\'onEventReceived\', (obj) => {\n\tconst listener = obj.detail.listener;\n  \n  \tif (listener == TRAIN_EVENT) {\n    \tif (listener == \'follower-latest\') {\n        \tupdate_train(1);\n        } else if (listener == \'subscriber-latest\') {\n        \tif (obj.detail.event.gifted) return;\n        \n            if (obj.detail.event.amount == \'gift\') obj.detail.event.amount = 1;\n\n            // Check if event is gifted sub\n            if (obj.detail.event.bulkGifted) {\n                update_train(obj.detail.event.amount);\n            } else {\n                update_train(1);\n            }\n        }\n    }\n})\n\nwindow.addEventListener(\'onSessionUpdate\', (obj) => {\n\tupdate_state(obj.detail.session);\n})\n\nHandlebars.registerHelper(\'highlight\', (options) => {\n\treturn \'<span class="highlight">\' + options.fn(this) + \'</span>\'\n})'
MINIMAL_EVENT_ROTATOR_FIELDS = '{\n  "design_background_color": {\n    "type": "colorpicker",\n    "label": "Background Color",\n    "value": "#8d99ae",\n    "group": "Design"\n  },\n  "design_font": {\n    "type": "googleFont",\n    "label": "Font Name",\n    "group": "Design"\n  },\n  "font_weight": {\n    "type": "dropdown",\n    "label": "Font Weight",\n    "value": "500",\n    "options": {\n      "100": "Thin",\n      "200": "Extra Light",\n      "300": "Light",\n      "400": "Normal",\n      "500": "Medium",\n      "600": "Semi Bold",\n      "700": "Bold",\n      "800": "Extra Bold",\n      "900": "Super Bold"\n    },\n    "group": "Design"\n  },\n  "highlight_font_weight": {\n    "type": "dropdown",\n    "label": "Highlight Font Weight",\n    "value": "500",\n    "options": {\n      "100": "Thin",\n      "200": "Extra Light",\n      "300": "Light",\n      "400": "Normal",\n      "500": "Medium",\n      "600": "Semi Bold",\n      "700": "Bold",\n      "800": "Extra Bold",\n      "900": "Super Bold"\n    },\n    "group": "Design"\n  },\n  "design_font_color": {\n    "type": "colorpicker",\n    "label": "Font Color",\n    "value": "#edf2f4",\n    "group": "Design"\n  },\n  "design_font_size": {\n    "type": "number",\n    "label": "Font Size",\n    "value": 40,\n    "group": "Design"\n  },\n  "design_padding": {\n    "type": "number",\n    "label": "Padding",\n    "value": 18,\n    "group": "Design"\n  },\n  "enable_icons": {\n    "type": "checkbox",\n    "label": "Enable Icons",\n    "value": true,\n    "group": "Design"\n  },\n  "design_icon_size": {\n    "type": "number",\n    "label": "Icon Size",\n    "value": 46,\n    "group": "Design"\n  },\n  "icon_text_spacing": {\n    "type": "number",\n    "label": "Icon Text Spacing",\n    "value": 12,\n    "group": "Design"\n  },\n  "design_train_fill_color": {\n    "type": "colorpicker",\n    "label": "Train Fill Color",\n    "value": "#ef233c",\n    "group": "Design"\n  },\n  "design_train_fill_font_color": {\n    "type": "colorpicker",\n    "label": "Train Fill Font Color",\n    "value": "#2b2d42",\n    "group": "Design"\n  },\n  "design_train_empty_color": {\n    "type": "colorpicker",\n    "label": "Train Empty Color",\n    "value": "#2b2d42",\n    "group": "Design"\n  },\n  "design_train_empty_font_color": {\n    "type": "colorpicker",\n    "label": "Train Empty Font Color",\n    "value": "#edf2f4",\n    "group": "Design"\n  },\n  "design_train_font_size": {\n    "type": "number",\n    "label": "Train-Font Size",\n    "value": 64,\n    "group": "Design"\n  },\n  "design_border_radius": {\n    "type": "number",\n    "label": "Corner Roundness",\n    "value": 0,\n    "group": "Design"\n  },\n  "train-event": {\n    "type": "dropdown",\n    "label": "Train Trigger Event",\n    "value": "subscriber-latest",\n    "options": {\n      "subscriber-latest": "Subscribers & Gifts",\n      "follower-latest": "Followers",\n      "disabled": "Disabled"\n    },\n    "group": "Train Options"\n  },\n  "train-duration": {\n    "type": "number",\n    "label": "Train Duration (Seconds)",\n    "value": 300,\n    "group": "Train Options"\n  },\n  "event-follower-latest-enable": {\n    "type": "checkbox",\n    "label": "Enable Follower Event",\n    "value": true,\n    "group": "Event - Follower"\n  },\n  "event-follower-latest-template": {\n    "type": "text",\n    "label": "Follower Event Template",\n    "value": "{{name}} <<#{{amount}}>>",\n    "group": "Event - Follower"\n  },\n  "event-follower-latest-icon": {\n    "type": "image-input",\n    "label": "Follower Event Icon",\n    "group": "Event - Follower"\n  },\n  "event-follower-latest-icon-overlay": {\n    "type": "colorpicker",\n    "label": "Follower Event Icon Overlay",\n    "group": "Event - Follower"\n  },\n  "event-subscriber-latest-enable": {\n    "type": "checkbox",\n    "label": "Enable Subscriber Event",\n    "value": true,\n    "group": "Event - Subscriber"\n  },\n  "event-subscriber-latest-template": {\n    "type": "text",\n    "label": "Subscriber Event Template",\n    "value": "{{name}} <<{{amount}} {{plural_amount}}>>",\n    "group": "Event - Subscriber"\n  },\n  "event-subscriber-latest-icon": {\n    "type": "image-input",\n    "label": "Subscriber Event Icon",\n    "group": "Event - Subscriber"\n  },\n  "event-subscriber-latest-icon-overlay": {\n    "type": "colorpicker",\n    "label": "Subscriber Event Icon Overlay",\n    "group": "Event - Subscriber"\n  },\n  "event-subscriber-latest-single": {\n    "type": "text",\n    "label": "Subscriber Pluralization Single",\n    "value": "Month",\n    "group": "Event - Subscriber"\n  },\n  "event-subscriber-latest-multi": {\n    "type": "text",\n    "label": "Subscriber Pluralization Multiple",\n    "value": "Months",\n    "group": "Event - Subscriber"\n  },\n  "event-cheer-latest-enable": {\n    "type": "checkbox",\n    "label": "Enable Cheer Event",\n    "value": true,\n    "group": "Event - Cheer"\n  },\n  "event-cheer-latest-template": {\n    "type": "text",\n    "label": "Cheer Event Template",\n    "value": "{{name}} <<{{amount}} {{plural_amount}}>>",\n    "group": "Event - Cheer"\n  },\n  "event-cheer-latest-icon": {\n    "type": "image-input",\n    "label": "Cheer Event Icon",\n    "group": "Event - Cheer"\n  },\n  "event-cheer-latest-icon-overlay": {\n    "type": "colorpicker",\n    "label": "Cheer Event Icon Overlay",\n    "group": "Event - Cheer"\n  },\n  "event-cheer-latest-single": {\n    "type": "text",\n    "label": "Cheer Pluralization Single",\n    "value": "Bit",\n    "group": "Event - Cheer"\n  },\n  "event-cheer-latest-multi": {\n    "type": "text",\n    "label": "Cheer Pluralization Multiple",\n    "value": "Bits",\n    "group": "Event - Cheer"\n  },\n  "event-tip-latest-enable": {\n    "type": "checkbox",\n    "label": "Enable Tip Event",\n    "value": true,\n    "group": "Event - Tip"\n  },\n  "event-tip-latest-template": {\n    "type": "text",\n    "label": "Follower Tip Template",\n    "value": "{{name}} <<${{amount}}>>",\n    "group": "Event - Tip"\n  },\n  "event-tip-latest-icon": {\n    "type": "image-input",\n    "label": "Tip Event Icon",\n    "group": "Event - Tip"\n  },\n  "event-tip-latest-icon-overlay": {\n    "type": "colorpicker",\n    "label": "Tip Event Icon Overlay",\n    "group": "Event - Tip"\n  },\n  "event-tip-latest-single": {\n    "type": "text",\n    "label": "Tip Pluralization Single",\n    "value": "Dollar",\n    "group": "Event - Tip"\n  },\n  "event-tip-latest-multi": {\n    "type": "text",\n    "label": "Tip Pluralization Multiple",\n    "value": "Dollars",\n    "group": "Event - Tip"\n  },\n  "event-raid-latest-enable": {\n    "type": "checkbox",\n    "label": "Enable Raid Event",\n    "value": true,\n    "group": "Event - Raid"\n  },\n  "event-raid-latest-template": {\n    "type": "text",\n    "label": "Follower Raid Template",\n    "value": "{{name}} <<{{amount}} {{plural_amount}}>>",\n    "group": "Event - Raid"\n  },\n  "event-raid-latest-icon": {\n    "type": "image-input",\n    "label": "Raid Event Icon",\n    "group": "Event - Raid"\n  },\n  "event-raid-latest-icon-overlay": {\n    "type": "colorpicker",\n    "label": "Raid Event Icon Overlay",\n    "group": "Event - Raid"\n  },\n  "event-raid-latest-single": {\n    "type": "text",\n    "label": "Raid Pluralization Single",\n    "value": "Raider",\n    "group": "Event - Raid"\n  },\n  "event-raid-latest-multi": {\n    "type": "text",\n    "label": "Raid Pluralization Multiple",\n    "value": "Raiders",\n    "group": "Event - Raid"\n  }\n}'
MINIMAL_EVENT_ROTATOR_DATA = '{\n  "eventsLimit": 5,\n  "includeFollowers": "yes",\n  "includeRedemptions": "yes",\n  "includeHosts": "yes",\n  "minHost": 1,\n  "includeRaids": "yes",\n  "minRaid": 1,\n  "includeSubs": "yes",\n  "includeTips": "yes",\n  "minTip": 1,\n  "includeCheers": "yes",\n  "minCheer": 1,\n  "direction": "top",\n  "textOrder": "nameFirst",\n  "fadeoutTime": 999,\n  "fontColor": "rgb(255, 255, 255)",\n  "theme": "texture",\n  "backgroundOpacity": 50,\n  "backgroundColor": "rgba(36, 6, 73, 0.15)",\n  "iconColor": "rgb(255, 255, 255, 255)",\n  "locale": "en-US",\n  "event-follower-latest-enable": true,\n  "event-follower-latest-template": "{{name}} <<#{{amount}}>>",\n  "event-subscriber-latest-enable": true,\n  "event-subscriber-latest-template": "{{name}} <<{{amount}} {{plural_amount}}>>",\n  "event-subscriber-latest-single": "Month",\n  "event-subscriber-latest-multi": "Months",\n  "event-cheer-latest-enable": true,\n  "event-cheer-latest-template": "{{name}} <<{{amount}} {{plural_amount}}>>",\n  "event-cheer-latest-single": "Bit",\n  "event-cheer-latest-multi": "Bits",\n  "event-tip-latest-enable": true,\n  "event-tip-latest-template": "{{name}} <<{{currency}}{{amount}}>>",\n  "event-tip-latest-single": "Dollar",\n  "event-tip-latest-multi": "Dollars",\n  "event-raid-latest-enable": true,\n  "event-raid-latest-template": "{{name}} <<{{amount}} {{plural_amount}}>>",\n  "event-raid-latest-single": "Raider",\n  "event-raid-latest-multi": "Raiders",\n  "event-host-latest-enable": true,\n  "event-host-latest-template": "{{name}} <<{{amount}} {{plural_amount}}>>",\n  "event-host-latest-single": "Viewer",\n  "event-host-latest-multi": "Viewers",\n  "train-event": "subscriber-latest",\n  "train-duration": 300,\n  "design_background_color": "#003566",\n  "design_font_color": "#ffffff",\n  "design_font_size": 48,\n  "design_train_fill_color": "#ffd60a",\n  "design_padding": 32,\n  "design_train_fill_font_color": "#003566",\n  "design_train_empty_color": "#001d3d",\n  "design_train_empty_font_color": "#ffffff",\n  "design_train_font_size": 52,\n  "font_weight": "500",\n  "design_font": "Montserrat",\n  "highlight_font_weight": "700",\n  "design_border_radius": 0,\n  "event-follower-latest-icon": "https://cdn.streamelements.com/uploads/bd76c169-fb07-432d-8775-411d370f3096.png",\n  "design_icon_size": 56,\n  "event-subscriber-latest-icon": "https://cdn.streamelements.com/uploads/655b8f9f-91ea-4b4e-a4f9-b1a1334907e3.png",\n  "event-cheer-latest-icon": "https://cdn.streamelements.com/uploads/d6d2582b-f2b9-4592-af30-11c6f0d0ce3e.png",\n  "event-tip-latest-icon": "https://cdn.streamelements.com/uploads/2343098e-8886-4440-a6d9-b6e449e48fd7.png",\n  "event-raid-latest-icon": "https://cdn.streamelements.com/uploads/b21e6d76-b2da-4623-acab-f09d98abc0e9.png",\n  "icon_text_spacing": 20,\n  "enable_icons": true,\n  "event-follower-latest-icon-overlay": "rgba(0, 0, 0, 0)",\n  "event-subscriber-latest-icon-overlay": "rgba(0, 0, 0, 0)",\n  "event-cheer-latest-icon-overlay": "rgba(0, 0, 0, 0)",\n  "event-tip-latest-icon-overlay": "rgba(0, 0, 0, 0)",\n  "event-raid-latest-icon-overlay": "rgba(0, 0, 0, 0)"\n}'


def is_minimal_event_rotator_pack(pack_info: dict) -> bool:
    slug = str(pack_info.get("pack_slug", "")).lower()
    source_zip = str(pack_info.get("source_zip", "")).lower()
    primary = str(pack_info.get("primary_share_url", "")).lower()
    return (
        "minimal-event-rotator" in slug
        or "minimal event rotator" in source_zip
        or "648c27594aba75c1b7832435" in primary
    )


def compile_streamelements_template_text(text: str, field_data: dict) -> str:
    compiled = text or ""
    for key, value in sorted(field_data.items(), key=lambda item: len(str(item[0])), reverse=True):
        compiled_value = str(value)
        compiled = compiled.replace("{{" + str(key) + "}}", compiled_value)
        compiled = compiled.replace("{" + str(key) + "}", compiled_value)
    return compiled


def guess_extension_from_url(url: str, fallback: str = ".bin") -> str:
    try:
        path = urllib.parse.urlparse(url).path
        ext = Path(path).suffix.lower()
        if ext and re.fullmatch(r"\.[a-z0-9]{2,5}", ext):
            return ext
    except Exception:
        pass
    return fallback


def download_url_asset(url: str, target_path: Path, log_func=None, timeout: int = 12) -> bool:
    log = log_func or (lambda message: None)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 SEUnpacker"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(response.read())
        return True
    except Exception as exc:
        log(f"Could not download dependency {url}: {exc}")
        return False


def localize_minimal_event_rotator_assets(pack_dir: Path, field_data: dict, log_func=None) -> dict:
    log = log_func or (lambda message: None)
    assets_dir = pack_dir / "assets"
    vendor_dir = assets_dir / "vendor"
    icons_dir = assets_dir / "icons"
    assets_dir.mkdir(parents=True, exist_ok=True)
    vendor_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)

    icon_names = {
        "event-follower-latest-icon": "follower",
        "event-subscriber-latest-icon": "subscriber",
        "event-cheer-latest-icon": "cheer",
        "event-tip-latest-icon": "tip",
        "event-raid-latest-icon": "raid",
    }
    for key, base_name in icon_names.items():
        url = str(field_data.get(key, ""))
        if not url.startswith("http"):
            continue
        ext = guess_extension_from_url(url, ".png")
        target = icons_dir / f"{base_name}{ext}"
        if download_url_asset(url, target, log_func=log):
            field_data[key] = f"assets/icons/{target.name}"
            log(f"Localized icon asset: {target.name}")

    vendor_assets = [
        ("jquery.min.js", "https://code.jquery.com/jquery-3.7.1.min.js"),
        ("gsap.min.js", "https://cdnjs.cloudflare.com/ajax/libs/gsap/3.11.4/gsap.min.js"),
        ("handlebars.min.js", "https://cdn.jsdelivr.net/npm/handlebars@latest/dist/handlebars.min.js"),
    ]
    vendor_paths = {}
    for filename, url in vendor_assets:
        target = vendor_dir / filename
        if target.exists() or download_url_asset(url, target, log_func=log):
            vendor_paths[filename] = f"assets/vendor/{filename}"
            log(f"Localized dependency: {filename}")
        else:
            vendor_paths[filename] = url

    return vendor_paths


def make_minimal_event_rotator_session_data(field_data: dict) -> dict:
    return {
        "follower-latest": {"name": "Latest Follower", "amount": 0, "count": 0},
        "follower-total": {"count": 0},
        "subscriber-latest": {"name": "Latest Subscriber", "amount": 1, "count": 1, "gifted": False},
        "subscriber-total": {"count": 0},
        "tip-latest": {"name": "Latest Tip", "amount": 1},
        "tip-total": {"amount": 0},
        "cheer-latest": {"name": "Latest Cheer", "amount": 0, "count": 0, "kind": "seed_cheer"},
        "cheer-total": {"amount": 0},
        "raid-latest": {"name": "Latest Raid", "amount": 0, "count": 0, "kind": "seed_raid"},
        "raid-total": {"count": 0},
        "host-latest": {"name": "Latest Host", "amount": 1},
        "host-total": {"count": 0},
    }



def _plain_text_from_any(value) -> str:
    try:
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)) or value is None:
            return str(value)
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _iter_recent_firebot_text_blobs(max_files: int = 120, max_chars_per_file: int = 900000):
    """Yield recent Firebot log/json text blobs for local history backfill.

    Firebot does not expose one stable event-history schema across versions and
    profiles, so this reader intentionally scans recent logs plus profile JSON
    using conservative regexes. It only seeds widget history; Twitch EventSub
    remains the live source after install.
    """
    profile_dir = get_firebot_profile_dir()
    candidates = []
    try:
        v5_dir = profile_dir.parent.parent
        roots = [v5_dir / "logs", profile_dir]
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                suffix = path.suffix.lower()
                if suffix not in {".log", ".json", ".txt"}:
                    continue
                # Skip huge backups and generated SEUnpacker widget files.
                lower = str(path).lower()
                if "backup" in lower or "overlay-resources" in lower:
                    continue
                try:
                    size = path.stat().st_size
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if size <= 0 or size > 8_000_000:
                    continue
                candidates.append((mtime, path))
    except Exception:
        return

    for _, path in sorted(candidates, reverse=True)[:max_files]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if text:
            yield str(path), text[-max_chars_per_file:]


def _best_firebot_event(current: dict | None, candidate: dict) -> dict:
    if not current:
        return candidate
    return current


def read_firebot_history_for_minimal_rotator(log_func=None) -> dict:
    """Backfill latest widget events from Firebot's local logs/history.

    This is deliberately best-effort. It prevents Twitch-only mode from showing
    fake 0-bit/0-raid rows when Firebot already has recent activity locally.
    """
    log = log_func or (lambda message: None)
    snapshot = {}
    found_sources = set()

    # Regexes are ordered from more specific to more general. They are designed
    # to match Firebot log text, dashboard-like copied strings, and JSON blobs.
    patterns = [
        ("cheer-latest", re.compile(r'(?is)(?:user[_ -]?name|username|display[_ -]?name|from|user)"?\s*[:=]\s*"?([A-Za-z0-9_][\w.-]{1,40})"?.{0,240}(?:bits|cheer(?:ed)?|amount)"?\s*[:=]?\s*"?(\d{1,9})"?')),
        ("cheer-latest", re.compile(r'(?is)([A-Za-z0-9_][\w.-]{1,40}).{0,80}(?:cheer(?:ed)?|sent|with)\s+(\d{1,9})\s+bits?')),
        ("cheer-latest", re.compile(r'(?is)([A-Za-z0-9_][\w.-]{1,40})\s+(\d{1,9})\s+bits?')),
        ("raid-latest", re.compile(r'(?is)(?:from_broadcaster_user_name|raider|user[_ -]?name|username|display[_ -]?name|from)"?\s*[:=]\s*"?([A-Za-z0-9_][\w.-]{1,40})"?.{0,240}(?:viewers|raiders|amount|count)"?\s*[:=]?\s*"?(\d{1,7})"?')),
        ("raid-latest", re.compile(r'(?is)([A-Za-z0-9_][\w.-]{1,40}).{0,100}(?:raid(?:ed)?|raiders?|viewers?).{0,30}(\d{1,7})')),
        ("raid-latest", re.compile(r'(?is)([A-Za-z0-9_][\w.-]{1,40})\s+(\d{1,7})\s+raiders?')),
        ("subscriber-latest", re.compile(r'(?is)([A-Za-z0-9_][\w.-]{1,40}).{0,80}resubscribed\s+for\s+(\d{1,4})')),
        ("subscriber-latest", re.compile(r'(?is)([A-Za-z0-9_][\w.-]{1,40}).{0,80}(\d{1,4})\s+months?')),
        ("tip-latest", re.compile(r'(?is)([A-Za-z0-9_][\w.-]{1,40}).{0,80}(?:tip(?:ped)?|donat(?:ed|ion)).{0,30}\$?([0-9]+(?:\.[0-9]{1,2})?)')),
        ("follower-latest", re.compile(r'(?is)(?:latest\s+follower|follow(?:er|ed)?).{0,80}([A-Za-z0-9_][\w.-]{1,40})')),
    ]

    def accept(event_key: str, name: str, amount_text: str | None, source: str):
        nonlocal snapshot
        name = (name or "").strip().strip('"\'')
        if not name or name.lower() in {"latest", "follower", "subscriber", "cheer", "raid", "user", "username", "viewer"}:
            return
        try:
            amount = float(amount_text) if amount_text is not None and str(amount_text).strip() else 1
        except Exception:
            amount = 1
        if event_key in {"cheer-latest", "raid-latest", "subscriber-latest"}:
            amount = int(amount)
        if amount < 0:
            return
        # Avoid treating old cumulative bits totals as a latest cheer. Real
        # cheers can be large, but leaderboard-style totals are usually huge.
        if event_key == "cheer-latest" and amount > 100000:
            return
        kind = {
            "cheer-latest": "firebot_history_cheer",
            "raid-latest": "firebot_history_raid",
            "subscriber-latest": "firebot_history_subscriber",
            "tip-latest": "firebot_history_tip",
            "follower-latest": "firebot_history_follower",
        }.get(event_key, "firebot_history")
        event = {"name": name, "amount": amount, "count": amount, "kind": kind, "source": "firebot_history"}
        if event_key == "subscriber-latest":
            event.update({"gifted": False, "bulkGifted": False})
        snapshot[event_key] = _best_firebot_event(snapshot.get(event_key), event)
        found_sources.add(source)

    for source, text in _iter_recent_firebot_text_blobs():
        if all(k in snapshot for k in ["cheer-latest", "raid-latest", "subscriber-latest", "tip-latest", "follower-latest"]):
            break
        # Search newest-looking text first by scanning from the end. Regexes still
        # return left-to-right, so keep the last match in that blob.
        for event_key, regex in patterns:
            if event_key in snapshot:
                continue
            matches = list(regex.finditer(text))
            if not matches:
                continue
            m = matches[-1]
            if event_key == "follower-latest" and len(m.groups()) == 1:
                accept(event_key, m.group(1), "1", source)
            else:
                accept(event_key, m.group(1), m.group(2), source)

    if snapshot:
        labels = []
        for key, value in snapshot.items():
            labels.append(f"{key}: {value.get('name')} {value.get('amount')}")
        log("Firebot history backfill found: " + "; ".join(labels))
    else:
        log("Firebot history backfill found no recent follower/sub/cheer/raid/tip records.")
    return snapshot


def merge_minimal_rotator_firebot_history(session_data: dict, history: dict) -> dict:
    if not history:
        return session_data
    for key, value in history.items():
        if key in session_data:
            session_data[key].update(value)
        else:
            session_data[key] = value
        if key == "follower-latest":
            session_data.setdefault("follower-total", {"count": 0})
            if session_data["follower-total"].get("count", 0) in (0, "0", None):
                session_data["follower-total"]["count"] = int(value.get("count") or value.get("amount") or 1)
        if key == "cheer-latest":
            session_data.setdefault("cheer-total", {"amount": 0})
        if key == "raid-latest":
            session_data.setdefault("raid-total", {"count": 0})
    return session_data


def generate_minimal_event_rotator_local_widget(pack_info: dict, log_func=None) -> tuple[bool, str]:
    # Build Minimal Event Rotator as a true Firebot-local widget.
    # v0.6.4 still embedded the original StreamElements widget JS. That JS can
    # fail in Firebot before anything renders. v0.6.6 converts the same source
    # data into a standalone vanilla-JS version so the overlay is not blank even
    # without StreamElements, jQuery, GSAP, or Handlebars.
    log = log_func or (lambda message: None)
    pack_dir = pack_info["pack_dir"]
    pack_dir.mkdir(parents=True, exist_ok=True)

    field_data = parse_json_text(MINIMAL_EVENT_ROTATOR_DATA, {})
    fields_json = parse_json_text(MINIMAL_EVENT_ROTATOR_FIELDS, {})

    # Keep icon localization, but do not make the whole widget depend on it.
    localize_minimal_event_rotator_assets(pack_dir, field_data, log_func=log)

    compiled_css = compile_streamelements_template_text(MINIMAL_EVENT_ROTATOR_CSS, field_data)
    session_data = make_minimal_event_rotator_session_data(field_data)
    firebot_history = read_firebot_history_for_minimal_rotator(log_func=log)
    session_data = merge_minimal_rotator_firebot_history(session_data, firebot_history)

    field_data_json = json.dumps(field_data)
    fields_json_text = json.dumps(fields_json)
    session_json = json.dumps(session_data)
    twitch_direct_config = read_twitch_direct_feed_config()
    if not (twitch_direct_config.get("enabled") and twitch_direct_config.get("client_id") and twitch_direct_config.get("access_token") and twitch_direct_config.get("broadcaster_user_id")):
        twitch_direct_config = {"enabled": False}
    twitch_direct_json = json.dumps(twitch_direct_config)
    widget_behavior_config = read_minimal_event_rotator_config()
    widget_behavior_json = json.dumps(widget_behavior_config)

    # The original StreamElements HTML includes external blocking <script> tags
    # for GSAP and Handlebars. The vanilla local rebuild does not need those
    # libraries. Leaving them in the body can cause OBS/Firebot to wait on CDN
    # downloads before the widget DOM even exists, which makes the overlay look
    # completely blank. Strip all original script tags before injecting our
    # standalone local runtime.
    minimal_rotator_body_html = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        MINIMAL_EVENT_ROTATOR_HTML,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    widget_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Minimal Event Rotator Widget</title>
<style>
{compiled_css}
html, body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    background: transparent;
    overflow: hidden;
}}
body {{
    display: flex;
    align-items: flex-start;
    justify-content: flex-start;
}}
.widget-container {{
    width: min(100vw, 980px) !important;
    height: min(100vh, 108px) !important;
    min-width: 360px;
    min-height: 72px;
    max-height: 140px;
    opacity: 1 !important;
    visibility: visible !important;
}}
.widget-container .wrapper {{
    width: 100% !important;
    height: 100% !important;
}}
.widget-container .wrapper .events {{
    flex: 1 1 auto;
    min-width: 0;
}}
.widget-container .wrapper .events .text {{
    opacity: 1 !important;
    transform: translateY(0);
    transition: transform 350ms ease, opacity 350ms ease;
}}
.widget-container .wrapper .events .text.seu-slide-out {{
    transform: translateY(100%);
    opacity: 0;
}}
.widget-container .wrapper .events .text.seu-slide-in {{
    transform: translateY(-100%);
    opacity: 0;
}}
.widget-container .wrapper .events .text .text-inner {{
    overflow: hidden;
    text-overflow: ellipsis;
}}
.widget-container .wrapper .train {{
    width: 0;
    height: 100%;
    flex: 0 0 auto;
    transition: width 500ms ease;
}}
.widget-container .wrapper .train.seu-active {{
    width: min(108px, 18vw);
}}
.widget-container .wrapper .train .fill {{
    clip-path: polygon(0% 100%, 100% 100%, 100% 100%, 0% 100%);
    transition: clip-path 500ms ease;
}}
.widget-container .wrapper .train.seu-active .fill {{
    clip-path: polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%);
}}
</style>
</head>
<body>
{minimal_rotator_body_html}

<script>
window.SEUNPACKER_FIELD_DATA = {field_data_json};
window.SEUNPACKER_FIELDS = {fields_json_text};
window.SEUNPACKER_SESSION_DATA = {session_json};
window.SEUNPACKER_TWITCH_DIRECT_CONFIG = {twitch_direct_json};
window.SEUNPACKER_WIDGET_CONFIG = {widget_behavior_json};

(function() {{
    const fd = window.SEUNPACKER_FIELD_DATA || {{}};
    const widgetConfig = Object.assign({{
        show_follower_count: true,
        show_sub_months: true,
        show_single_gift_sub: true,
        show_community_gift_count: true,
        show_cheer_bits: true,
        show_raid_viewers: true,
        show_tip_amount: true,
        show_redemptions: true
    }}, window.SEUNPACKER_WIDGET_CONFIG || {{}});
    const session = window.SEUNPACKER_SESSION_DATA || {{}};
    const packSlug = "{pack_info['pack_slug']}";
    const bridgeChannelName = "SEUnpacker:" + packSlug;
    const bridgeStorageKey = bridgeChannelName + ":lastEvent";
    const persistedSessionKey = bridgeChannelName + ":session";
    try {{
        const savedSession = JSON.parse(localStorage.getItem(persistedSessionKey) || "{{}}");
        if (savedSession && typeof savedSession === "object") Object.assign(session, savedSession);
        // Older SEUnpacker builds incorrectly seeded cheer-latest from Twitch bits leaderboard totals.
        // Drop restored non-live cheer values so cumulative totals are not shown as latest cheer events.
        if (session["cheer-latest"] && !["live_cheer", "firebot_history_cheer"].includes(session["cheer-latest"].kind)) {{
            session["cheer-latest"] = {{ name: "Latest Cheer", amount: 0, count: 0, kind: "seed_cheer" }};
        }}
        // Twitch does not provide a reliable latest raid history endpoint for this widget.
        // Only live EventSub channel.raid notifications should be treated as real raid data.
        if (session["raid-latest"] && !["live_raid", "firebot_history_raid"].includes(session["raid-latest"].kind)) {{
            session["raid-latest"] = {{ name: "Latest Raid", amount: 0, count: 0, kind: "seed_raid" }};
        }}
    }} catch (err) {{
        console.warn("SEUnpacker could not restore persisted widget session", err);
    }}
    function savePersistedSession() {{
        try {{ localStorage.setItem(persistedSessionKey, JSON.stringify(session)); }} catch (err) {{}}
    }}
    const events = ["follower-latest", "subscriber-latest", "tip-latest", "cheer-latest", "raid-latest"];
    const state = {{}};
    let enabledEvents = [];
    let pos = 0;
    let currency = "$";
    let trainEvent = fd["train-event"] || "subscriber-latest";
    let trainCount = 0;
    let trainTimer = null;

    function clone(obj) {{
        return JSON.parse(JSON.stringify(obj || {{}}));
    }}

    function getPlural(eventKey, amount) {{
        const single = fd[`event-${{eventKey}}-single`] || "";
        const multi = fd[`event-${{eventKey}}-multi`] || single;
        return Number(amount) === 1 ? single : multi;
    }}

    function applyTemplate(template, values) {{
        let output = String(template || "");
        output = output.replaceAll("<<", '<span class="highlight">').replaceAll(">>", "</span>");
        const replacements = {{
            name: values.name ?? "Viewer",
            amount: values.amount ?? "0",
            count: values.count ?? values.amount ?? "0",
            plural_amount: values.plural_amount ?? "",
            currency: values.currency ?? currency
        }};
        for (const [key, value] of Object.entries(replacements)) {{
            output = output.split("{{{{" + key + "}}}}").join(String(value));
            output = output.split("{{{{ " + key + " }}}}").join(String(value));
        }}
        return output;
    }}

    function getEventAmount(eventKey, eventData) {{
        if (eventKey === "follower-latest") {{
            return (session["follower-total"] && session["follower-total"].count) || eventData.count || eventData.amount || 0;
        }}
        return eventData.amount ?? eventData.count ?? 0;
    }}

    function buildIconHtml(eventKey) {{
        if (!fd.enable_icons) return "";
        const icon = fd[`event-${{eventKey}}-icon`] || "";
        if (!icon) return "";
        const overlay = fd[`event-${{eventKey}}-icon-overlay`] || "rgba(0,0,0,0)";
        return `<div class="icon overlay" style="background: ${{overlay}}; mask-size: cover; -webkit-mask-size: cover; mask-image: url('${{icon}}'); -webkit-mask-image: url('${{icon}}');"></div><div class="icon"><img src="${{icon}}" /></div>`;
    }}

    function chooseDisplayTemplate(eventKey, eventData) {{
        if (eventKey === "follower-latest" && !widgetConfig.show_follower_count) return "{{{{name}}}}";
        if (eventKey === "subscriber-latest") {{
            if (eventData && eventData.gifted) {{
                if (eventData.bulkGifted) {{
                    return widgetConfig.show_community_gift_count ? "{{{{name}}}} <<{{{{amount}}}} Gift Subs>>" : "{{{{name}}}} <<Community Gift>>";
                }}
                return widgetConfig.show_single_gift_sub ? "{{{{name}}}} <<Gift Sub>>" : "{{{{name}}}}";
            }}
            if (!widgetConfig.show_sub_months) return "{{{{name}}}}";
        }}
        if (eventKey === "cheer-latest" && !widgetConfig.show_cheer_bits) return "{{{{name}}}}";
        if (eventKey === "raid-latest" && !widgetConfig.show_raid_viewers) return "{{{{name}}}}";
        if (eventKey === "tip-latest") {{
            if (eventData && eventData.kind === "redemption" && !widgetConfig.show_redemptions) return "{{{{name}}}}";
            if (!widgetConfig.show_tip_amount) return "{{{{name}}}}";
        }}
        return fd[`event-${{eventKey}}-template`] || "{{{{name}}}} <<{{{{amount}}}}>>";
    }}

    function hasRealEventData(eventKey, eventData) {{
        if (!eventData) return false;
        const kind = String(eventData.kind || "");
        const name = String(eventData.name || eventData.username || eventData.user || "");
        const amount = Number(eventData.amount ?? eventData.count ?? 0);
        if (eventKey === "cheer-latest") {{
            // Twitch does not expose historical/latest cheer events through Helix.
            // Only show cheers once a real live channel.cheer EventSub event has been received.
            return true;
        }}
        if (eventKey === "raid-latest") {{
            // Twitch does not expose historical/latest raid events through Helix.
            // Only show raids once a real live channel.raid EventSub event has been received.
            return true;
        }}
        return true;
    }}

    function rebuildState() {{
        enabledEvents = [];
        for (const eventKey of events) {{
            if (fd[`event-${{eventKey}}-enable`] === true) {{
                const eventData = session[eventKey] || {{ name: "Viewer", amount: 0, count: 0 }};
                if (!hasRealEventData(eventKey, eventData)) {{
                    delete state[eventKey];
                    continue;
                }}
                enabledEvents.push(eventKey);
                const amount = getEventAmount(eventKey, eventData);
                const template = chooseDisplayTemplate(eventKey, eventData);
                const text = applyTemplate(template, {{
                    name: eventData.name || eventData.username || eventData.user || "Viewer",
                    amount: amount,
                    count: eventData.count ?? amount,
                    plural_amount: getPlural(eventKey, amount),
                    currency: eventData.currency !== undefined ? eventData.currency : currency
                }});
                state[eventKey] = `${{buildIconHtml(eventKey)}}<div class="text-inner">${{text}}</div>`;
            }}
        }}
        if (!enabledEvents.length) {{
            enabledEvents = ["follower-latest"];
            state["follower-latest"] = '<div class="text-inner">Waiting for Twitch events <span class="highlight">#0</span></div>';
        }}
        pos = pos % enabledEvents.length;
    }}

    function showCurrent(immediate) {{
        const textEl = document.querySelector(".events .text");
        if (!textEl) return;
        const key = enabledEvents[pos % enabledEvents.length];
        const nextHtml = state[key] || '<div class="text-inner">Waiting for events <span class="highlight">#0</span></div>';
        if (immediate) {{
            textEl.innerHTML = nextHtml;
            return;
        }}
        textEl.classList.add("seu-slide-out");
        setTimeout(() => {{
            textEl.innerHTML = nextHtml;
            textEl.classList.remove("seu-slide-out");
            textEl.classList.add("seu-slide-in");
            requestAnimationFrame(() => {{
                textEl.classList.remove("seu-slide-in");
            }});
        }}, 350);
    }}

    function rotate() {{
        pos = (pos + 1) % enabledEvents.length;
        showCurrent(false);
    }}

    function sameUser(a, b) {{
        const an = String((a && (a.name || a.username || a.user || a.user_login)) || "").toLowerCase();
        const bn = String((b && (b.name || b.username || b.user || b.user_login)) || "").toLowerCase();
        return an && bn && an === bn;
    }}

    function updateTotals(listener, eventData) {{
        const incoming = Object.assign({{}}, eventData || {{}});
        const existing = Object.assign({{}}, session[listener] || {{}});

        // Twitch may send/seed a generic channel.subscribe payload with no cumulative month data.
        // Do not let that overwrite a richer channel.subscription.message payload for the same user.
        if (listener === "subscriber-latest" && incoming.kind === "subscribe_no_months" && sameUser(existing, incoming)) {{
            const existingAmount = Number(existing.amount || existing.count || 0);
            const incomingAmount = Number(incoming.amount || incoming.count || 0);
            if (existingAmount > incomingAmount) {{
                return;
            }}
        }}

        session[listener] = Object.assign({{}}, existing, incoming);
        if (!session[listener].name) session[listener].name = session[listener].username || session[listener].user || "Viewer";
        if (session[listener].amount === undefined && session[listener].count !== undefined) session[listener].amount = session[listener].count;
        if (session[listener].count === undefined && session[listener].amount !== undefined) session[listener].count = session[listener].amount;

        if (listener === "follower-latest") {{
            session["follower-total"] = session["follower-total"] || {{ count: 0 }};
            session["follower-total"].count = Number(session["follower-total"].count || 0) + 1;
        }}
        savePersistedSession();
    }}

    function updateTrain(listener, eventData) {{
        if (listener !== trainEvent || trainEvent === "disabled") return;
        let inc = 1;
        if (listener === "subscriber-latest") {{
            if (eventData && eventData.gifted && !eventData.bulkGifted) return;
            inc = Number(eventData.amount === "gift" ? 1 : (eventData.amount || eventData.count || 1));
        }}
        trainCount += inc;
        const train = document.querySelector(".train");
        const empty = document.querySelector(".train .empty");
        const fill = document.querySelector(".train .fill");
        if (!train || !empty || !fill) return;
        empty.textContent = String(trainCount);
        fill.textContent = String(trainCount);
        train.classList.add("seu-active");
        clearTimeout(trainTimer);
        trainTimer = setTimeout(() => {{
            train.classList.remove("seu-active");
            trainCount = 0;
        }}, Math.max(1, Number(fd["train-duration"] || 300)) * 1000);
    }}

    window.SEUnpackerEventRotator = {{
        pushEvent: function(listener, eventData) {{
            updateTotals(listener, eventData || {{}});
            rebuildState();
            const idx = enabledEvents.indexOf(listener);
            if (idx >= 0) pos = idx;
            showCurrent(true);
            updateTrain(listener, eventData || {{}});
            window.dispatchEvent(new CustomEvent("onSessionUpdate", {{ detail: {{ session: clone(session) }} }}));
        }},
        setSession: function(sessionData) {{
            Object.assign(session, sessionData || {{}});
            savePersistedSession();
            rebuildState();
            showCurrent(true);
        }},
        demo: function() {{
            const samples = [
                ["follower-latest", {{ name: "NewFollower", amount: 1, count: 1 }}],
                ["subscriber-latest", {{ name: "NewSub", amount: 1, count: 1 }}],
                ["cheer-latest", {{ name: "BitBoss", amount: 100, count: 100 }}],
                ["tip-latest", {{ name: "Tipper", amount: 5, count: 5 }}],
                ["raid-latest", {{ name: "Raider", amount: 12, count: 12 }}]
            ];
            const item = samples[Math.floor(Math.random() * samples.length)];
            this.pushEvent(item[0], item[1]);
        }}
    }};

    window.addEventListener("onWidgetLoad", function(obj) {{
        const detail = obj.detail || {{}};
        if (detail.currency && detail.currency.symbol) currency = detail.currency.symbol;
        if (detail.fieldData) Object.assign(fd, detail.fieldData);
        if (detail.session && detail.session.data) Object.assign(session, detail.session.data);
        trainEvent = fd["train-event"] || trainEvent;
        rebuildState();
        showCurrent(true);
    }});

    window.addEventListener("onEventReceived", function(obj) {{
        const detail = obj.detail || {{}};
        if (detail.listener) window.SEUnpackerEventRotator.pushEvent(detail.listener, detail.event || {{}});
    }});

    window.addEventListener("onSessionUpdate", function(obj) {{
        if (obj.detail && obj.detail.session) {{
            Object.assign(session, obj.detail.session);
            rebuildState();
            showCurrent(true);
        }}
    }});

    function receiveBridgePayload(data) {{
        if (!data || data.source !== "SEUnpacker" || data.type !== "event") return;
        if (data.packSlug && data.packSlug !== packSlug) return;
        window.SEUnpackerEventRotator.pushEvent(data.listener, data.event || {{}});
    }}

    window.addEventListener("message", function(messageEvent) {{
        receiveBridgePayload(messageEvent.data || {{}});
    }});

    try {{
        const bridgeChannel = new BroadcastChannel(bridgeChannelName);
        bridgeChannel.onmessage = function(event) {{
            receiveBridgePayload(event.data || {{}});
        }};
    }} catch (err) {{
        console.warn("SEUnpacker BroadcastChannel unavailable", err);
    }}

    window.addEventListener("storage", function(event) {{
        if (event.key !== bridgeStorageKey || !event.newValue) return;
        try {{
            receiveBridgePayload(JSON.parse(event.newValue));
        }} catch (err) {{
            console.warn("SEUnpacker storage bridge parse failed", err);
        }}
    }});

    try {{
        const existingPayload = localStorage.getItem(bridgeStorageKey);
        if (existingPayload) receiveBridgePayload(JSON.parse(existingPayload));
    }} catch (err) {{}}

    function normalizeTwitchEvent(subscriptionType, event) {{
        if (!event) return null;
        if (subscriptionType === "channel.follow") {{
            return ["follower-latest", {{ name: event.user_name || event.user_login || "New Follower", amount: 1, count: 1 }}];
        }}
        if (subscriptionType === "channel.subscribe") {{
            return ["subscriber-latest", {{ name: event.user_name || event.user_login || "New Subscriber", amount: 1, count: 1, gifted: false, bulkGifted: false, kind: "subscribe_no_months" }}];
        }}
        if (subscriptionType === "channel.subscription.gift") {{
            const total = Number(event.total || event.cumulative_total || 1) || 1;
            return ["subscriber-latest", {{ name: event.user_name || event.user_login || "Gift Sub", amount: total, count: total, gifted: true, bulkGifted: total > 1, kind: total > 1 ? "community_gift" : "gift_sub" }}];
        }}
        if (subscriptionType === "channel.subscription.message") {{
            const months = Number(event.cumulative_months || event.duration_months || event.streak_months || event.months || 1) || 1;
            return ["subscriber-latest", {{ name: event.user_name || event.user_login || "Resub", amount: months, count: months, gifted: false, bulkGifted: false, kind: "resub_message" }}];
        }}
        if (subscriptionType === "channel.cheer") {{
            const bits = Number(event.bits || 1) || 1;
            return ["cheer-latest", {{ name: event.user_name || event.user_login || "Cheer", amount: bits, count: bits, kind: "live_cheer" }}];
        }}
        if (subscriptionType === "channel.raid") {{
            const viewers = Number(event.viewers || 1) || 1;
            return ["raid-latest", {{ name: event.from_broadcaster_user_name || event.from_broadcaster_user_login || "Raid", amount: viewers, count: viewers, kind: "live_raid" }}];
        }}
        if (subscriptionType === "channel.channel_points_custom_reward_redemption.add") {{
            const rewardTitle = event.reward && event.reward.title ? event.reward.title : "Redemption";
            return ["tip-latest", {{ name: event.user_name || event.user_login || "Redeemer", amount: rewardTitle, count: 1, currency: "", kind: "redemption" }}];
        }}
        if (subscriptionType === "channel.charity_campaign.donate") {{
            const amount = event.amount && event.amount.value ? Number(event.amount.value) / Math.pow(10, Number(event.amount.decimal_places || 2)) : 1;
            const currencyCode = event.amount && event.amount.currency ? event.amount.currency + " " : "";
            return ["tip-latest", {{ name: event.user_name || event.user_login || "Charity Donor", amount: amount, count: amount, currency: currencyCode, kind: "tip" }}];
        }}
        return null;
    }}

    async function twitchApi(config, path, options) {{
        const response = await fetch("https://api.twitch.tv/helix" + path, Object.assign({{
            headers: {{
                "Client-Id": config.client_id,
                "Authorization": "Bearer " + config.access_token,
                "Content-Type": "application/json"
            }}
        }}, options || {{}}));
        if (!response.ok) {{
            const text = await response.text().catch(() => "");
            throw new Error("Twitch API " + response.status + ": " + text);
        }}
        return response.json().catch(() => ({{}}));
    }}

    async function seedTwitchInitialSnapshot(config) {{
        if (!config || !config.enabled || !config.client_id || !config.access_token || !config.broadcaster_user_id) return;
        const broadcasterId = String(config.broadcaster_user_id);
        const moderatorId = String(config.moderator_user_id || config.broadcaster_user_id);

        try {{
            const followers = await twitchApi(config, "/channels/followers?" + new URLSearchParams({{
                broadcaster_id: broadcasterId,
                moderator_id: moderatorId,
                first: "1"
            }}).toString());
            if (followers && typeof followers.total === "number") {{
                session["follower-total"] = session["follower-total"] || {{}};
                session["follower-total"].count = followers.total;
            }}
            if (followers && followers.data && followers.data.length) {{
                const latest = followers.data[0];
                session["follower-latest"] = {{
                    name: latest.user_name || latest.user_login || "Latest Follower",
                    amount: followers.total || 1,
                    count: followers.total || 1
                }};
            }}
        }} catch (err) {{
            console.warn("SEUnpacker could not seed latest follower from Twitch", err);
        }}

        try {{
            const subs = await twitchApi(config, "/subscriptions?" + new URLSearchParams({{
                broadcaster_id: broadcasterId,
                first: "1"
            }}).toString());
            if (subs && subs.data && subs.data.length) {{
                const latest = subs.data[0];
                if (!session["subscriber-latest"] || !session["subscriber-latest"].name || String(session["subscriber-latest"].name).startsWith("Latest ")) {{
                    session["subscriber-latest"] = {{
                        name: latest.user_name || latest.user_login || "Latest Subscriber",
                        amount: 1,
                        count: 1,
                        gifted: Boolean(latest.is_gift),
                        kind: "api_seed_no_months"
                    }};
                }}
            }}
        }} catch (err) {{
            console.warn("SEUnpacker could not seed latest subscriber from Twitch", err);
        }}

        // Do not seed cheer-latest from /bits/leaderboard.
        // That endpoint returns cumulative leaderboard totals for a user, not the latest cheer event amount.
        // Cheer data should only update from live EventSub channel.cheer events so the amount represents that specific cheer.
        if (session["cheer-latest"] && !["live_cheer", "firebot_history_cheer"].includes(session["cheer-latest"].kind)) {{
            session["cheer-latest"] = {{ name: "Latest Cheer", amount: 0, count: 0, kind: "seed_cheer" }};
        }}
        // Twitch does not provide a reliable latest raid history endpoint for this widget.
        // Only live EventSub channel.raid notifications should be treated as real raid data.
        if (session["raid-latest"] && !["live_raid", "firebot_history_raid"].includes(session["raid-latest"].kind)) {{
            session["raid-latest"] = {{ name: "Latest Raid", amount: 0, count: 0, kind: "seed_raid" }};
        }}

        try {{
            const rewards = await twitchApi(config, "/channel_points/custom_rewards?" + new URLSearchParams({{
                broadcaster_id: broadcasterId
            }}).toString());
            let latestRedemption = null;
            if (rewards && rewards.data && rewards.data.length) {{
                for (const reward of rewards.data.slice(0, 20)) {{
                    try {{
                        const redemptions = await twitchApi(config, "/channel_points/custom_rewards/redemptions?" + new URLSearchParams({{
                            broadcaster_id: broadcasterId,
                            reward_id: reward.id,
                            status: "FULFILLED",
                            sort: "NEWEST",
                            first: "1"
                        }}).toString());
                        if (redemptions && redemptions.data && redemptions.data.length) {{
                            const item = redemptions.data[0];
                            if (!latestRedemption || String(item.redeemed_at || "") > String(latestRedemption.redeemed_at || "")) {{
                                latestRedemption = item;
                            }}
                        }}
                    }} catch (innerErr) {{}}
                }}
            }}
            if (latestRedemption) {{
                const rewardTitle = latestRedemption.reward && latestRedemption.reward.title ? latestRedemption.reward.title : "Redemption";
                session["tip-latest"] = {{
                    name: latestRedemption.user_name || latestRedemption.user_login || "Redeemer",
                    amount: rewardTitle,
                    count: 1,
                    currency: "",
                    kind: "redemption"
                }};
            }}
        }} catch (err) {{
            console.warn("SEUnpacker could not seed channel point redemption data from Twitch", err);
        }}

        savePersistedSession();
        rebuildState();
        showCurrent(true);
    }}

    async function createTwitchSubscription(config, sessionId, type, version, condition) {{
        const payload = {{
            type: type,
            version: version,
            condition: condition,
            transport: {{ method: "websocket", session_id: sessionId }}
        }};
        try {{
            await twitchApi(config, "/eventsub/subscriptions", {{
                method: "POST",
                body: JSON.stringify(payload)
            }});
            console.info("SEUnpacker Twitch subscription active", type);
        }} catch (err) {{
            console.warn("SEUnpacker Twitch subscription failed", type, err);
        }}
    }}

    function startDirectTwitchFeed() {{
        const config = window.SEUNPACKER_TWITCH_DIRECT_CONFIG || {{}};
        if (!config.enabled || !config.client_id || !config.access_token || !config.broadcaster_user_id) return;
        const broadcasterId = String(config.broadcaster_user_id);
        const moderatorId = String(config.moderator_user_id || config.broadcaster_user_id);
        seedTwitchInitialSnapshot(config);
        let socket = null;
        let reconnectTimer = null;

        function connect() {{
            try {{
                socket = new WebSocket("wss://eventsub.wss.twitch.tv/ws?keepalive_timeout_seconds=30");
            }} catch (err) {{
                console.warn("SEUnpacker Twitch Direct Feed could not start", err);
                return;
            }}

            socket.onmessage = async function(event) {{
                let msg = null;
                try {{ msg = JSON.parse(event.data); }} catch (err) {{ return; }}
                const type = msg?.metadata?.message_type;
                if (type === "session_welcome") {{
                    const sessionId = msg?.payload?.session?.id;
                    if (!sessionId) return;
                    const subs = [
                        ["channel.follow", "2", {{ broadcaster_user_id: broadcasterId, moderator_user_id: moderatorId }}],
                        ["channel.subscribe", "1", {{ broadcaster_user_id: broadcasterId }}],
                        ["channel.subscription.message", "1", {{ broadcaster_user_id: broadcasterId }}],
                        ["channel.subscription.gift", "1", {{ broadcaster_user_id: broadcasterId }}],
                        ["channel.cheer", "1", {{ broadcaster_user_id: broadcasterId }}],
                        ["channel.raid", "1", {{ to_broadcaster_user_id: broadcasterId }}],
                        ["channel.channel_points_custom_reward_redemption.add", "1", {{ broadcaster_user_id: broadcasterId }}],
                        ["channel.charity_campaign.donate", "1", {{ broadcaster_user_id: broadcasterId }}]
                    ];
                    for (const sub of subs) await createTwitchSubscription(config, sessionId, sub[0], sub[1], sub[2]);
                }} else if (type === "notification") {{
                    const subType = msg?.payload?.subscription?.type;
                    const mapped = normalizeTwitchEvent(subType, msg?.payload?.event || {{}});
                    if (mapped) window.SEUnpackerEventRotator.pushEvent(mapped[0], mapped[1]);
                }} else if (type === "session_reconnect") {{
                    const url = msg?.payload?.session?.reconnect_url;
                    if (url) {{
                        try {{ socket.close(); }} catch (err) {{}}
                        socket = new WebSocket(url);
                    }}
                }}
            }};

            socket.onclose = function() {{
                clearTimeout(reconnectTimer);
                reconnectTimer = setTimeout(connect, 5000);
            }};
            socket.onerror = function(err) {{
                console.warn("SEUnpacker Twitch Direct Feed socket error", err);
            }};
        }}
        connect();
    }}

    function boot() {{
        window.dispatchEvent(new CustomEvent("onWidgetLoad", {{
            detail: {{
                currency: {{ symbol: "$" }},
                fieldData: fd,
                session: {{ data: clone(session) }}
            }}
        }}));
        setInterval(rotate, 5000);
        startDirectTwitchFeed();
    }}

    if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", boot);
    }} else {{
        boot();
    }}
}})();
</script>
</body>
</html>
'''
    widget_path = pack_dir / "widget.html"
    widget_path.write_text(widget_html, encoding="utf-8")
    pack_info["widget_bundle"] = {
        "folder": "generated:minimal-event-rotator-vanilla",
        "html": MINIMAL_EVENT_ROTATOR_HTML,
        "css": MINIMAL_EVENT_ROTATOR_CSS,
        "js": "generated vanilla Firebot-local rotator",
        "fields": MINIMAL_EVENT_ROTATOR_FIELDS,
        "data": MINIMAL_EVENT_ROTATOR_DATA,
        "widget_ini": "generated=true",
        "score": 8,
    }
    pack_info["captured_local_overlay"] = True
    pack_info["generated_source_widget"] = True
    return True, "Generated Minimal Event Rotator as a standalone Firebot-local vanilla widget."

def generate_widget_html(pack_info: dict) -> str:
    bundle = pack_info.get("widget_bundle") or {}
    primary_share_url = normalize_user_url(pack_info.get("primary_share_url", ""))
    final_overlay_url = normalize_user_url(pack_info.get("final_overlay_url", ""))

    if not bundle and primary_share_url:
        # URL-only StreamElements widget packs must never render the SEUnpacker
        # setup/instructions page inside Firebot or OBS. That helper page was
        # useful while building the flow, but it blocks the actual overlay with
        # a black box. Once the final StreamElements Copy URL is captured, this
        # generated widget is only a transparent wrapper around the real browser
        # source URL. Before the final URL is captured, stay transparent/blank.
        if final_overlay_url:
            iframe_url = html_escape(final_overlay_url)
            return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SEUnpacker StreamElements Widget - {pack_info["pack_slug"]}</title>
<style>
    html, body {{
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
        background: transparent;
        overflow: hidden;
    }}

    iframe {{
        position: fixed;
        inset: 0;
        width: 100vw;
        height: 100vh;
        border: 0;
        margin: 0;
        padding: 0;
        background: transparent;
        overflow: hidden;
    }}
</style>
</head>
<body>
    <iframe src="{iframe_url}" allowtransparency="true"></iframe>
</body>
</html>
'''

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SEUnpacker StreamElements Widget Waiting - {pack_info["pack_slug"]}</title>
<style>
    html, body {{
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
        background: transparent;
        overflow: hidden;
    }}
</style>
</head>
<body></body>
</html>
'''

    raw_html = sanitize_widget_html_fragment(bundle.get("html", ""))
    raw_css = bundle.get("css", "")
    raw_js = bundle.get("js", "")
    raw_data = bundle.get("data", "{}")
    raw_fields = bundle.get("fields", "{}")

    data_json = parse_json_text(raw_data, {})
    fields_json = parse_json_text(raw_fields, {})

    tracking_type = data_json.get("trackingType", "donation")
    initial_value = data_json.get("initialValue", 0)

    session_data = {
        "tip-session": {"amount": initial_value},
        "tip-total": {"amount": initial_value},
        "tip-month": {"amount": initial_value},
        "tip-week": {"amount": initial_value},
        "tip-latest": {"amount": 0},
        "cheer-session": {"amount": initial_value},
        "cheer-total": {"amount": initial_value},
        "cheer-month": {"amount": initial_value},
        "cheer-week": {"amount": initial_value},
        "cheer-latest": {"amount": 0},
        "subscriber-session": {"count": initial_value},
        "subscriber-total": {"count": initial_value},
        "subscriber-month": {"count": initial_value},
        "subscriber-week": {"count": initial_value},
        "subscriber-latest": {"amount": 0, "count": 0},
        "follower-session": {"count": initial_value},
        "follower-total": {"count": initial_value},
        "follower-month": {"count": initial_value},
        "follower-week": {"count": initial_value},
        "follower-latest": {"count": 0},
    }

    data_json_text = json.dumps(data_json)
    fields_json_text = json.dumps(fields_json)
    session_json_text = json.dumps(session_data)
    tracking_type_text = json.dumps(tracking_type)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SEUnpacker Widget - {pack_info["pack_slug"]}</title>
<style>
    html, body {{
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
        background: transparent;
        overflow: hidden;
    }}

    body {{
        background: transparent;
    }}

    {raw_css}
</style>
</head>
<body>
{raw_html}

<script>
    window.SEUNPACKER_FIELD_DATA = {data_json_text};
    window.SEUNPACKER_FIELDS = {fields_json_text};
    window.SEUNPACKER_SESSION_DATA = {session_json_text};
    window.SEUNPACKER_TRACKING_TYPE = {tracking_type_text};

    window.SEUnpackerGoal = {{
        add: function(value) {{
            const event = new CustomEvent("onEventReceived", {{
                detail: {{
                    listener: "tip-latest",
                    event: {{
                        amount: Number(value || 0),
                        count: Number(value || 0)
                    }}
                }}
            }});
            window.dispatchEvent(event);
        }},
        set: function(value) {{
            const amount = Number(value || 0);
            window.SEUNPACKER_SESSION_DATA["tip-session"].amount = amount;
            window.SEUNPACKER_SESSION_DATA["tip-total"].amount = amount;
            window.SEUNPACKER_SESSION_DATA["cheer-session"].amount = amount;
            window.SEUNPACKER_SESSION_DATA["cheer-total"].amount = amount;
            window.SEUNPACKER_SESSION_DATA["subscriber-session"].count = amount;
            window.SEUNPACKER_SESSION_DATA["subscriber-total"].count = amount;
            window.SEUNPACKER_SESSION_DATA["follower-session"].count = amount;
            window.SEUNPACKER_SESSION_DATA["follower-total"].count = amount;

            const loadEvent = new CustomEvent("onWidgetLoad", {{
                detail: {{
                    fieldData: window.SEUNPACKER_FIELD_DATA,
                    session: {{
                        data: window.SEUNPACKER_SESSION_DATA
                    }}
                }}
            }});
            window.dispatchEvent(loadEvent);
        }}
    }};
</script>

<script>
{raw_js}
</script>

<script>
    function seunpackerDispatchLoad() {{
        const loadEvent = new CustomEvent("onWidgetLoad", {{
            detail: {{
                fieldData: window.SEUNPACKER_FIELD_DATA,
                session: {{
                    data: window.SEUNPACKER_SESSION_DATA
                }}
            }}
        }});

        window.dispatchEvent(loadEvent);
    }}

    if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", function() {{
            setTimeout(seunpackerDispatchLoad, 100);
        }});
    }} else {{
        setTimeout(seunpackerDispatchLoad, 100);
    }}
</script>
</body>
</html>
'''

def make_firebot_html_for_event(pack_info: dict, title: str, username_var: str, subtext: str) -> str:
    html = generate_alert_html(pack_info)

    html = html.replace(
        'const ALERT_TITLE = "NEW FOLLOWER";',
        f'const ALERT_TITLE = "{title}";'
    )

    html = html.replace(
        'const ALERT_USER = "$username";',
        f'const ALERT_USER = "{username_var}";'
    )

    html = html.replace(
        'const ALERT_SUBTEXT = "triggered the alert";',
        f'const ALERT_SUBTEXT = "{subtext}";'
    )

    return html

def create_firebot_html_effect(html: str, length: str = "8") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "type": "firebot:html",
        "active": True,
        "enterAnimation": "fadeIn",
        "exitAnimation": "fadeOut",
        "inbetweenAnimation": "none",
        "html": html,
        "length": length,
        "percentWeight": None
    }


def create_firebot_event_object(name: str, event_id: str, html: str) -> dict:
    return {
        "name": name,
        "active": True,
        "cached": True,
        "sortTags": [],
        "eventId": event_id,
        "sourceId": "twitch",
        "filterData": {
            "mode": "exclusive",
            "filters": []
        },
        "effects": {
            "id": str(uuid.uuid4()),
            "list": [
                create_firebot_html_effect(html)
            ],
            "runMode": "all"
        },
        "id": str(uuid.uuid4())
    }


def create_firebot_event_object_with_effect(name: str, event_id: str, effect: dict, metadata: dict | None = None) -> dict:
    event_object = {
        "name": name,
        "active": True,
        "cached": True,
        "sortTags": [],
        "eventId": event_id,
        "sourceId": "twitch",
        "filterData": {
            "mode": "exclusive",
            "filters": []
        },
        "effects": {
            "id": str(uuid.uuid4()),
            "list": [effect],
            "runMode": "all"
        },
        "id": str(uuid.uuid4())
    }
    if metadata:
        event_object["metadata"] = metadata
    return event_object


def js_string(value) -> str:
    return json.dumps(str(value))


def create_widget_bridge_html(pack_info: dict, listener: str, name_candidates: list[str], amount_candidates: list[str], extra_event_data: dict | None = None) -> str:
    """Create a tiny Show HTML effect that feeds a persistent SEUnpacker widget."""
    pack_slug = pack_info["pack_slug"]
    payload_extra = extra_event_data or {}
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SEUnpacker Widget Event Bridge</title>
<style>
    html, body {{
        margin: 0;
        padding: 0;
        width: 1px;
        height: 1px;
        background: transparent;
        overflow: hidden;
    }}
</style>
</head>
<body>
<script>
(function() {{
    const packSlug = {js_string(pack_slug)};
    const listener = {js_string(listener)};
    const nameCandidates = {json.dumps(name_candidates)};
    const amountCandidates = {json.dumps(amount_candidates)};
    const extra = {json.dumps(payload_extra)};
    const channelName = "SEUnpacker:" + packSlug;
    const storageKey = channelName + ":lastEvent";

    function cleanValue(value, fallback) {{
        value = String(value == null ? "" : value).trim();
        if (!value || value.charAt(0) === "$" || value.toLowerCase() === "undefined" || value.toLowerCase() === "null") {{
            return fallback;
        }}
        return value;
    }}

    function firstUsable(values, fallback) {{
        for (const value of values) {{
            const cleaned = cleanValue(value, "");
            if (cleaned) return cleaned;
        }}
        return fallback;
    }}

    function firstNumber(values, fallback) {{
        for (const value of values) {{
            const cleaned = cleanValue(value, "");
            if (!cleaned) continue;
            const match = cleaned.replace(/,/g, "").match(/-?\\d+(?:\\.\\d+)?/);
            if (match) {{
                const parsed = Number(match[0]);
                if (Number.isFinite(parsed)) return parsed;
            }}
        }}
        return fallback;
    }}

    const name = firstUsable(nameCandidates, "Viewer");
    const amount = firstNumber(amountCandidates, 1);
    const payload = {{
        source: "SEUnpacker",
        type: "event",
        packSlug: packSlug,
        listener: listener,
        event: Object.assign({{
            name: name,
            username: name,
            user: name,
            amount: amount,
            count: amount
        }}, extra),
        sentAt: Date.now()
    }};

    try {{
        const channel = new BroadcastChannel(channelName);
        channel.postMessage(payload);
        setTimeout(function() {{ channel.close(); }}, 500);
    }} catch (err) {{}}

    try {{
        localStorage.setItem(storageKey, JSON.stringify(payload));
    }} catch (err) {{}}

    try {{
        window.parent.postMessage(payload, "*");
    }} catch (err) {{}}
}})();
</script>
</body>
</html>'''


def create_widget_bridge_html_effect(html: str) -> dict:
    effect = create_firebot_html_effect(html, length="1")
    effect["enterAnimation"] = "none"
    effect["exitAnimation"] = "none"
    effect["inbetweenAnimation"] = "none"
    return effect


def get_minimal_event_rotator_feeder_configs() -> list[dict]:
    return [
        {"label": "Follow Feeder", "event_id": "follow", "listener": "follower-latest", "name_candidates": ["$username", "$user", "$displayName"], "amount_candidates": ["1"], "extra": {}},
        {"label": "Sub Feeder", "event_id": "sub", "listener": "subscriber-latest", "name_candidates": ["$username", "$user", "$displayName"], "amount_candidates": ["$monthsSubscribed", "$cumulativeMonths", "$amount", "1"], "extra": {"gifted": False, "bulkGifted": False}},
        {"label": "Gift Sub Feeder", "event_id": "subs-gifted", "listener": "subscriber-latest", "name_candidates": ["$giftGiverUsername", "$username", "$user", "$displayName"], "amount_candidates": ["$monthsGifted", "$amount", "1"], "extra": {"gifted": True, "bulkGifted": False}},
        {"label": "Community Gift Feeder", "event_id": "community-subs-gifted", "listener": "subscriber-latest", "name_candidates": ["$giftGiverUsername", "$username", "$user", "$displayName"], "amount_candidates": ["$giftCount", "$subBombCount", "$amount", "1"], "extra": {"gifted": True, "bulkGifted": True}},
        {"label": "Cheer Feeder", "event_id": "cheer", "listener": "cheer-latest", "name_candidates": ["$username", "$user", "$displayName"], "amount_candidates": ["$bits", "$amount", "1"], "extra": {}},
        {"label": "Raid Feeder", "event_id": "raid", "listener": "raid-latest", "name_candidates": ["$username", "$user", "$displayName"], "amount_candidates": ["$viewerCount", "$raidViewerCount", "$amount", "1"], "extra": {}},
    ]


def remove_existing_seunpacker_widget_feeder_events(events_data: dict, pack_slug: str) -> int:
    before_count = len(events_data.get("mainEvents", []))
    events_data["mainEvents"] = [
        event
        for event in events_data.get("mainEvents", [])
        if not (
            firebot_record_matches_seunpacker_pack(event, pack_slug)
            and (
                "Feeder" in str(event.get("name", ""))
                or str(event.get("metadata", {}).get("kind", "")) == "widget-event-feeder"
            )
        )
    ]
    return before_count - len(events_data["mainEvents"])


def create_minimal_event_rotator_firebot_feeder_events(pack_info: dict) -> dict:
    events_path = get_firebot_events_json_path()
    backup_path = backup_file(events_path, "SEUnpacker_Backups")
    events_data = load_firebot_events_file(events_path)

    removed_count = remove_existing_seunpacker_widget_feeder_events(events_data, pack_info["pack_slug"])
    created_events = []
    pack_display_name = safe_firebot_display_name(pack_display_name_for_firebot(pack_info), max_length=34)

    for config in get_minimal_event_rotator_feeder_configs():
        event_name = safe_firebot_display_name(f"{pack_display_name} {config['label']}", max_length=50)
        bridge_html = create_widget_bridge_html(
            pack_info=pack_info,
            listener=config["listener"],
            name_candidates=config["name_candidates"],
            amount_candidates=config["amount_candidates"],
            extra_event_data=config.get("extra", {}),
        )
        effect = create_widget_bridge_html_effect(bridge_html)
        event_object = create_firebot_event_object_with_effect(
            name=event_name,
            event_id=config["event_id"],
            effect=effect,
            metadata={
                "createdBy": "SEUnpacker",
                "kind": "widget-event-feeder",
                "packSlug": pack_info["pack_slug"],
                "listener": config["listener"],
                "createdAt": datetime.now().isoformat(),
            },
        )
        events_data["mainEvents"].append(event_object)
        created_events.append(event_name)

    save_firebot_events_file(events_path, events_data)
    return {"events_path": events_path, "backup_path": backup_path, "removed_count": removed_count, "created_events": created_events}


def get_seunpacker_event_configs() -> list[dict]:
    return [
        {"label": "Follow", "event_id": "follow", "title": "NEW FOLLOWER", "username_var": "$username", "subtext": "just followed"},
        {"label": "Sub / Resub", "event_id": "sub", "title": "NEW SUB", "username_var": "$username", "subtext": "just subscribed"},
        {"label": "Gift Sub", "event_id": "subs-gifted", "title": "GIFT SUB", "username_var": "$giftGiverUsername", "subtext": "gifted a sub"},
        {"label": "Community Gift", "event_id": "community-subs-gifted", "title": "GIFT BOMB", "username_var": "$giftGiverUsername", "subtext": "gifted subs to the community"},
        {"label": "Cheer", "event_id": "cheer", "title": "BITS", "username_var": "$username", "subtext": "sent bits"},
        {"label": "Raid", "event_id": "raid", "title": "RAID", "username_var": "$username", "subtext": "raided the channel"}
    ]

def remove_existing_seunpacker_events(events_data: dict, pack_slug: str = "") -> int:
    before_count = len(events_data.get("mainEvents", []))

    # Alert events share Twitch event IDs, so a new alert install should replace
    # older SEUnpacker alert events. This prevents old alert packs from still
    # firing after a different alert pack is installed.
    events_data["mainEvents"] = [
        event
        for event in events_data.get("mainEvents", [])
        if not firebot_record_is_seunpacker(event)
    ]

    after_count = len(events_data["mainEvents"])
    return before_count - after_count

def create_firebot_events_for_pack(pack_info: dict) -> dict:
    if pack_info.get("pack_type") != "alert_pack":
        raise RuntimeError(
            "This ZIP was detected as a StreamElements widget pack, not an alert event pack.\n\n"
            "Use Create Overlay Widget / Preset instead."
        )

    running, reason = is_firebot_running()

    if running:
        raise RuntimeError(
            "Firebot appears to be running.\n\n"
            f"{reason}\n\n"
            "Close Firebot completely before creating events."
        )

    events_path = get_firebot_events_json_path()
    backup_path = backup_file(events_path, "SEUnpacker_Backups")
    events_data = load_firebot_events_file(events_path)

    removed_count = remove_existing_seunpacker_events(events_data, pack_info["pack_slug"])
    created_events = []

    for config in get_seunpacker_event_configs():
        event_name = f"SEUnpacker - {pack_info['pack_slug']} - {config['label']}"

        html = make_firebot_html_for_event(
            pack_info=pack_info,
            title=config["title"],
            username_var=config["username_var"],
            subtext=config["subtext"],
        )

        event_object = create_firebot_event_object(
            name=event_name,
            event_id=config["event_id"],
            html=html,
        )

        events_data["mainEvents"].append(event_object)
        created_events.append(event_name)

    save_firebot_events_file(events_path, events_data)

    return {
        "events_path": events_path,
        "backup_path": backup_path,
        "removed_count": removed_count,
        "created_events": created_events
    }


def create_overlay_widget_record(pack_info: dict) -> dict:
    pack_display_name = pack_display_name_for_firebot(pack_info)
    widget_name = safe_firebot_display_name(pack_display_name, max_length=50)
    resource_url = f"/overlay-resources/SEUnpacker/{pack_info['pack_slug']}/widget.html"
    iframe_html = (
        f'<iframe src="{resource_url}" '
        'style="position:fixed;inset:0;width:100vw;height:100vh;'
        'border:0;margin:0;padding:0;background:transparent;overflow:hidden;" '
        'allowtransparency="true"></iframe>'
    )

    return {
        "id": str(uuid.uuid4()),
        "name": widget_name,
        "type": "firebot:custom",
        "active": True,
        "enabled": True,
        "sortTags": [],
        "settings": {
            "html": iframe_html,
            "css": "html, body { margin: 0; padding: 0; background: transparent; overflow: hidden; }",
            "js": "",
            "onShowJs": "",
            "onStateUpdateJs": "",
            "onMessageJs": "",
            "htmlFile": f"SEUnpacker/{pack_info['pack_slug']}/widget.html",
            "resourcePath": f"SEUnpacker/{pack_info['pack_slug']}/widget.html",
            "url": resource_url,
            "width": 1920,
            "height": 1080
        },
        "position": {
            "x": 0,
            "y": 0,
            "width": 1920,
            "height": 1080,
            "scale": 1,
            "rotation": 0
        },
        "metadata": {
            "createdBy": "SEUnpacker",
            "createdAt": datetime.now().isoformat(),
            "packSlug": pack_info["pack_slug"],
            "resourceUrl": resource_url
        }
    }


def remove_existing_seunpacker_widgets(widgets: list, pack_slug: str = "") -> tuple[list, int]:
    before_count = len(widgets)

    cleaned = [
        widget
        for widget in widgets
        if not firebot_record_matches_seunpacker_pack(widget, pack_slug)
    ]

    after_count = len(cleaned)
    return cleaned, before_count - after_count

def generate_local_overlay_resource_iframe(pack_info: dict) -> str:
    resource_url = f"/overlay-resources/SEUnpacker/{pack_info['pack_slug']}/widget.html"
    return (
        f'<iframe src="{resource_url}" '
        'style="position:fixed;inset:0;width:100vw;height:100vh;'
        'border:0;margin:0;padding:0;background:transparent;overflow:hidden;" '
        'allowtransparency="true"></iframe>'
    )


def create_widget_preset_effect_list_record(pack_info: dict) -> dict:
    # Important: the preset effect must use the local Firebot overlay resource,
    # not generate_widget_html(pack_info). For URL based StreamElements widgets,
    # generate_widget_html may intentionally fall back to a hosted SE iframe when
    # static capture fails. The persistent widget path was already local, but the
    # preset effect was still pointing at the hosted StreamElements browser URL.
    # This made the preset dependent on the overlay continuing to exist in
    # StreamElements.
    html = generate_local_overlay_resource_iframe(pack_info)
    pack_display_name = pack_display_name_for_firebot(pack_info)
    preset_name = safe_firebot_display_name(pack_display_name, max_length=50)

    return {
        "name": preset_name,
        "effects": {
            "list": [
                create_firebot_html_effect(html, length="3600")
            ],
            "id": str(uuid.uuid4())
        },
        "args": [],
        "sortTags": [],
        "id": str(uuid.uuid4()),
        "metadata": {
            "createdBy": "SEUnpacker",
            "createdAt": datetime.now().isoformat(),
            "packSlug": pack_info["pack_slug"],
            "resourceUrl": f"/overlay-resources/SEUnpacker/{pack_info['pack_slug']}/widget.html"
        }
    }


def remove_existing_seunpacker_preset_lists(preset_lists: list, pack_slug: str = "") -> tuple[list, int]:
    before_count = len(preset_lists)

    cleaned = [
        preset
        for preset in preset_lists
        if not firebot_record_matches_seunpacker_pack(preset, pack_slug)
    ]

    after_count = len(cleaned)
    return cleaned, before_count - after_count

def create_firebot_widget_and_preset_for_pack(pack_info: dict) -> dict:
    if pack_info.get("pack_type") != "stream_elements_widget":
        raise RuntimeError(
            "This ZIP was detected as an alert pack, not a persistent widget pack.\n\n"
            "Use Create Firebot Events for alert packs."
        )

    running, reason = is_firebot_running()

    if running:
        raise RuntimeError(
            "Firebot appears to be running.\n\n"
            f"{reason}\n\n"
            "Close Firebot completely before creating overlay widgets."
        )

    widgets_path = get_firebot_overlay_widgets_json_path()
    presets_path = get_firebot_preset_effect_lists_json_path()

    widgets_backup_path = backup_file(widgets_path, "SEUnpacker_Backups")
    presets_backup_path = backup_file(presets_path, "SEUnpacker_Backups")

    widgets = load_firebot_overlay_widgets_file(widgets_path)
    presets = load_firebot_preset_effect_lists_file(presets_path)

    widgets, removed_widgets_count = remove_existing_seunpacker_widgets(widgets, pack_info["pack_slug"])
    presets, removed_presets_count = remove_existing_seunpacker_preset_lists(presets, pack_info["pack_slug"])

    widget_record = create_overlay_widget_record(pack_info)
    preset_record = create_widget_preset_effect_list_record(pack_info)

    widgets.append(widget_record)
    presets.append(preset_record)

    save_firebot_overlay_widgets_file(widgets_path, widgets)
    save_firebot_preset_effect_lists_file(presets_path, presets)

    feeder_result = None
    if is_minimal_event_rotator_pack(pack_info):
        feeder_result = create_minimal_event_rotator_firebot_feeder_events(pack_info)

    return {
        "widgets_path": widgets_path,
        "presets_path": presets_path,
        "widgets_backup_path": widgets_backup_path,
        "presets_backup_path": presets_backup_path,
        "removed_widgets_count": removed_widgets_count,
        "removed_presets_count": removed_presets_count,
        "created_widget": widget_record["name"],
        "created_preset": preset_record["name"],
        "widget_id": widget_record["id"],
        "preset_id": preset_record["id"],
        "feeder_result": feeder_result,
    }


def generate_readme(pack_info: dict) -> str:
    shortcuts_text = ""
    if pack_info["shortcuts"]:
        for shortcut in pack_info["shortcuts"]:
            shortcuts_text += f"- {shortcut['file']}: {shortcut['url'] or 'No URL found'}\n"
    else:
        shortcuts_text = "- None found\n"

    images_text = "\n".join("- " + item for item in pack_info["images"]) if pack_info["images"] else "- None found"
    audio_text = "\n".join("- " + item for item in pack_info["audio"]) if pack_info["audio"] else "- None found"
    video_text = "\n".join("- " + item for item in pack_info["video"]) if pack_info["video"] else "- None found"
    widget_files_text = "\n".join("- " + item for item in pack_info["widget_source_files"]) if pack_info["widget_source_files"] else "- None found"

    if pack_info["pack_type"] == "stream_elements_widget":
        action_text = """Detected pack type:
StreamElements Custom Widget

Recommended SEUnpacker action:
1. Build
2. Install Assets
3. Create Widget / Preset

Generated files:
- widget.html
- source/html.txt / css.txt / js.txt when included in the source ZIP
- StreamElements share-link iframe widget when the ZIP is URL-only
"""
    else:
        event_names = "\n".join(
            f"- {config['label']} ({config['event_id']})"
            for config in get_seunpacker_event_configs()
        )

        action_text = f"""Detected pack type:
Alert Asset Pack

Recommended SEUnpacker action:
1. Build
2. Install Assets
3. Create Firebot Events

Supported Firebot Events:
{event_names}
"""

    readme = f"""SEUnpacker
Version: {APP_VERSION}

Pack:
{pack_info["pack_slug"]}

{action_text}

Extracted images:
{images_text}

Extracted audio:
{audio_text}

Extracted video:
{video_text}

Widget source files:
{widget_files_text}

Shortcut URLs:
{shortcuts_text}

Important:
This tool does not modify Firebot's application install.
It copies generated files into Firebot's overlay-resources folder.
It backs up Firebot JSON files before writing event, widget, or preset records.
"""
    return readme


def build_firebot_pack(zip_path: Path, output_root: Path) -> dict:
    pack_info = extract_pack(zip_path, output_root)

    if pack_info["pack_type"] == "stream_elements_widget":
        widget_html = generate_widget_html(pack_info)
        widget_path = pack_info["pack_dir"] / "widget.html"
        widget_path.write_text(widget_html, encoding="utf-8")
        pack_info["widget_path"] = widget_path
        pack_info["html_path"] = widget_path
    else:
        alert_html = generate_alert_html(pack_info)
        alert_path = pack_info["pack_dir"] / "alert.html"
        alert_path.write_text(alert_html, encoding="utf-8")
        pack_info["alert_path"] = alert_path
        pack_info["html_path"] = alert_path

    readme = generate_readme(pack_info)
    readme_path = pack_info["pack_dir"] / "README.txt"
    readme_path.write_text(readme, encoding="utf-8")
    pack_info["readme_path"] = readme_path

    return pack_info


def copy_folder_contents_update_only(source_dir: Path, target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)

    for item in source_dir.iterdir():
        target_item = target_dir / item.name

        if item.is_dir():
            copy_folder_contents_update_only(item, target_item)
        elif item.is_file():
            shutil.copy2(item, target_item)


def install_to_firebot_resources(pack_info: dict) -> Path:
    running, reason = is_firebot_running()

    if running:
        raise RuntimeError(
            "Firebot appears to be running.\n\n"
            f"{reason}\n\n"
            "Close Firebot completely before installing resources."
        )

    resources_root = get_appdata_firebot_resources()
    resources_root.mkdir(parents=True, exist_ok=True)

    # Replace only the selected pack folder. Do not delete the whole
    # overlay-resources/SEUnpacker directory, because that would remove other
    # active SEUnpacker widgets such as a StreamElements rotator.
    target_dir = resources_root / pack_info["pack_slug"]
    if target_dir.exists():
        shutil.rmtree(target_dir)

    copy_folder_contents_update_only(pack_info["pack_dir"], target_dir)

    return target_dir


def get_installed_pack_resource_dir(pack_info: dict) -> Path:
    return get_appdata_firebot_resources() / pack_info["pack_slug"]


def validate_local_widget_html(widget_path: Path, pack_info: dict | None = None) -> tuple[bool, list[str]]:
    """Return whether a generated local widget.html looks usable.

    This prevents SEUnpacker from reporting success when it only installed the
    transparent StreamElements waiting shell.
    """
    failures = []
    if not widget_path.exists():
        return False, [f"widget.html does not exist: {widget_path}"]

    try:
        html = widget_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return False, [f"Could not read widget.html: {exc}"]

    lower = html.lower()
    pack_slug = (pack_info or {}).get("pack_slug", "").lower()

    if "streamelements widget waiting" in lower:
        failures.append("widget.html is still the StreamElements waiting placeholder.")
    if re.search(r"<body>\s*</body>", html, flags=re.IGNORECASE):
        failures.append("widget.html body is empty.")
    if "https://streamelements.com/overlay/" in lower or "https://www.streamelements.com/dashboard/overlays/share/" in lower:
        failures.append("widget.html still points at a hosted StreamElements overlay.")
    # Only treat StreamElements placeholders as unresolved when they appear in
    # rendered HTML/CSS outside of script blocks. Minimal Event Rotator stores
    # event templates such as {{name}} and {{amount}} inside JS/JSON on purpose,
    # then replaces them at runtime. The previous check looked at the whole file
    # and falsely failed valid local widgets.
    html_without_scripts = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    unresolved_patterns = [
        r"\{\{\s*[a-zA-Z0-9_\-]+\s*\}\}",
        r"\{design_[a-zA-Z0-9_\-]+\}",
    ]
    if any(re.search(pattern, html_without_scripts) for pattern in unresolved_patterns):
        failures.append("widget.html still contains unresolved StreamElements template placeholders outside the local runtime.")

    # Minimal Event Rotator has a known source profile. Be strict so this pack
    # cannot silently install a blank shell.
    if "minimal-event-rotator" in pack_slug or "minimal event rotator" in lower:
        required_tokens = [
            "widget-container",
            "wrapper",
            "events",
            "train",
            "SEUnpackerEventRotator",
        ]
        for token in required_tokens:
            if token.lower() not in lower:
                failures.append(f"Minimal Event Rotator widget is missing required token: {token}")
        if len(html) < 5000:
            failures.append(f"Minimal Event Rotator widget.html is too small to contain the rebuilt widget ({len(html)} bytes).")

    return len(failures) == 0, failures


def sync_rebuilt_pack_to_firebot_resources(pack_info: dict) -> Path:
    """Copy the rebuilt output pack into Firebot after URL capture/source rebuild.

    The unified install flow installs assets before the StreamElements Copy URL
    is captured. For URL widgets, that means Firebot may still have the earlier
    waiting widget.html unless we sync again after the final local widget is built.
    """
    running, reason = is_firebot_running()
    if running:
        raise RuntimeError(
            "Firebot appears to be running.\n\n"
            f"{reason}\n\n"
            "Close Firebot completely before syncing rebuilt widget resources."
        )

    target_dir = get_installed_pack_resource_dir(pack_info)
    target_dir.mkdir(parents=True, exist_ok=True)
    copy_folder_contents_update_only(pack_info["pack_dir"], target_dir)
    return target_dir



def parse_version_tuple(version_text: str) -> tuple[int, ...]:
    cleaned = str(version_text or "").strip().lower().lstrip("v")
    parts = []
    for piece in re.split(r"[^0-9]+", cleaned):
        if piece == "":
            continue
        try:
            parts.append(int(piece))
        except Exception:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def is_newer_version(remote_version: str, local_version: str) -> bool:
    return parse_version_tuple(remote_version) > parse_version_tuple(local_version)


def github_request_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"{APP_NAME}/{APP_VERSION}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def get_latest_github_release() -> dict:
    return github_request_json(GITHUB_LATEST_RELEASE_API)


def find_release_asset(release: dict, preferred_name: str = GITHUB_RELEASE_ASSET_NAME) -> dict | None:
    assets = release.get("assets") or []
    preferred_lower = preferred_name.lower()
    for asset in assets:
        if str(asset.get("name", "")).lower() == preferred_lower:
            return asset
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if name.endswith(".exe") and "seunpacker" in name:
            return asset
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if name.endswith(".zip") and "seunpacker" in name:
            return asset
    return None


def download_file(url: str, destination: Path, log_func=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=60) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)
    if log_func:
        log_func(f"Downloaded update asset to: {destination}")


def create_windows_self_update_script(downloaded_file: Path, target_exe: Path) -> Path:
    script_path = downloaded_file.parent / "apply_seunpacker_update.bat"
    content = """@echo off
setlocal
set APP_EXE={target_exe}
set NEW_EXE={downloaded_file}
echo Waiting for SEUnpacker to close...
timeout /t 2 /nobreak >nul
:retry
copy /Y "%NEW_EXE%" "%APP_EXE%" >nul
if errorlevel 1 (
  echo SEUnpacker is still running. Retrying...
  timeout /t 1 /nobreak >nul
  goto retry
)
echo Update installed.
start "" "%APP_EXE%"
del "%NEW_EXE%" >nul 2>nul
del "%~f0" >nul 2>nul
""".format(target_exe=str(target_exe), downloaded_file=str(downloaded_file))
    script_path.write_text(content, encoding="utf-8")
    return script_path


class BlueButton(Button):
    def __init__(self, master, text, command=None, width=None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            width=width,
            bg=BLUE,
            fg="white",
            activebackground=BLUE_HOVER,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            **kwargs,
        )

        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, _event):
        self.configure(bg=BLUE_HOVER)

    def on_leave(self, _event):
        self.configure(bg=BLUE)


class SidebarButton(Button):
    def __init__(self, master, text, command=None, active=False, **kwargs):
        bg = SIDEBAR_ACTIVE if active else SIDEBAR_BG

        super().__init__(
            master,
            text=text,
            command=command,
            bg=bg,
            fg=TEXT_FG,
            activebackground=SIDEBAR_ACTIVE,
            activeforeground=TEXT_FG,
            relief="flat",
            bd=0,
            anchor="w",
            padx=18,
            pady=12,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            **kwargs,
        )

        self.default_bg = bg
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def set_active(self, active: bool):
        self.default_bg = SIDEBAR_ACTIVE if active else SIDEBAR_BG
        self.configure(bg=self.default_bg)

    def on_enter(self, _event):
        self.configure(bg=SIDEBAR_ACTIVE)

    def on_leave(self, _event):
        self.configure(bg=self.default_bg)


class SEUnpackerApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1120x720")
        self.root.minsize(980, 620)
        self.root.configure(bg=DARK_BG)

        icon_path = resource_path("assets/icons/seunpacker.ico")
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        self.zip_path_var = StringVar()
        self.output_path_var = StringVar(value=str(get_default_output_folder()))
        self.firebot_resources_var = StringVar(value=str(get_appdata_firebot_resources()))
        self.firebot_events_var = StringVar(value=str(get_firebot_events_json_path()))
        self.firebot_widgets_var = StringVar(value=str(get_firebot_overlay_widgets_json_path()))
        self.firebot_presets_var = StringVar(value=str(get_firebot_preset_effect_lists_json_path()))
        self.stream_elements_overlay_url_var = StringVar()
        self.stream_elements_login_status_var = StringVar(value="StreamElements: Not checked")
        self.stream_elements_login_detail_var = StringVar(value="Click Login to StreamElements before installing URL-based widget packs.")
        self.twitch_direct_status_var = StringVar(value=get_twitch_direct_feed_status_text())

        self.current_pack_info = None
        self.current_tab = "dashboard"
        self.sidebar_buttons = {}
        self.logo_img = None
        self.log = None
        self.se_webview_window = None
        self.se_webview_process = None
        self.se_copy_url_splash = None
        self.se_login_process = None
        self.waiting_for_login_then_import = False
        self.login_poll_active = False

        self.refresh_stream_elements_login_status(write_to_log=False)
        self.build_ui()
        try:
            self.root.after(2500, lambda: self.check_for_updates(silent=True))
        except Exception:
            pass

    def build_ui(self):
        self.app_shell = Frame(self.root, bg=DARK_BG)
        self.app_shell.pack(fill="both", expand=True)

        self.sidebar = Frame(self.app_shell, bg=SIDEBAR_BG, width=250)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.content = Frame(self.app_shell, bg=DARK_BG)
        self.content.pack(side="left", fill="both", expand=True)

        self.build_sidebar()
        self.show_dashboard()

    def build_sidebar(self):
        header = Frame(self.sidebar, bg=SIDEBAR_BG)
        header.pack(fill="x", padx=12, pady=(18, 20))

        logo_path = resource_path("assets/icons/seunpacker-icon-64.png")
        if logo_path.exists():
            try:
                self.logo_img = PhotoImage(file=str(logo_path))
                logo_label = Label(header, image=self.logo_img, bg=SIDEBAR_BG)
                logo_label.pack(side="left", padx=(0, 10))
            except Exception:
                logo_label = Label(header, text="🤖", bg=SIDEBAR_BG, fg=YELLOW, font=("Segoe UI", 22))
                logo_label.pack(side="left", padx=(0, 10))
        else:
            logo_label = Label(header, text="🤖", bg=SIDEBAR_BG, fg=YELLOW, font=("Segoe UI", 22))
            logo_label.pack(side="left", padx=(0, 10))

        title_box = Frame(header, bg=SIDEBAR_BG)
        title_box.pack(side="left", fill="x", expand=True)

        title = Label(
            title_box,
            text="SEUnpacker",
            bg=SIDEBAR_BG,
            fg=TEXT_FG,
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor="w")

        version = Label(
            title_box,
            text=f"v{APP_VERSION}",
            bg=SIDEBAR_BG,
            fg=MUTED_FG,
            font=("Segoe UI", 9),
        )
        version.pack(anchor="w")

        section = Label(
            self.sidebar,
            text="WORKFLOW",
            bg=SIDEBAR_BG,
            fg=MUTED_FG,
            font=("Segoe UI", 9, "bold"),
        )
        section.pack(anchor="w", padx=20, pady=(4, 6))

        self.add_sidebar_button("dashboard", "📡  DASHBOARD", self.show_dashboard)

        section2 = Label(
            self.sidebar,
            text="TOOLS",
            bg=SIDEBAR_BG,
            fg=MUTED_FG,
            font=("Segoe UI", 9, "bold"),
        )
        section2.pack(anchor="w", padx=20, pady=(18, 6))

        self.add_sidebar_button("uninstall", "🧹  UNINSTALL PACKS", self.show_uninstall_packs)
        self.add_sidebar_button("notes", "🧾  SETUP NOTES", self.show_notes)
        self.add_sidebar_button("settings", "⚙  SETTINGS", self.show_settings)

        footer = Frame(self.sidebar, bg=SIDEBAR_BG)
        footer.pack(side="bottom", fill="x", padx=16, pady=16)

        footer_text = Label(
            footer,
            text="StreamElements packs\nrebuilt for Firebot",
            bg=SIDEBAR_BG,
            fg=MUTED_FG,
            justify="left",
            font=("Segoe UI", 9),
        )
        footer_text.pack(anchor="w")

        Button(
            footer,
            text="Launch Firebot",
            command=self.launch_firebot,
            bg=BLUE,
            fg="white",
            activebackground=BLUE_HOVER,
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=8,
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(12, 0))

        Button(
            footer,
            text="Check for Updates",
            command=lambda: self.check_for_updates(silent=False),
            bg="#374151",
            fg="white",
            activebackground="#4b5563",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=8,
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(8, 0))

    def add_sidebar_button(self, key: str, text: str, command):
        btn = SidebarButton(
            self.sidebar,
            text=text,
            command=lambda: command(),
            active=(key == self.current_tab),
        )
        btn.pack(fill="x", padx=8, pady=2)
        self.sidebar_buttons[key] = btn

    def set_active_tab(self, key: str):
        self.current_tab = key

        for button_key, button in self.sidebar_buttons.items():
            button.set_active(button_key == key)

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def make_page(self, title: str, subtitle: str):
        self.clear_content()

        header = Frame(self.content, bg=HEADER_BG, height=92)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_label = Label(
            header,
            text=title,
            bg=HEADER_BG,
            fg=TEXT_FG,
            font=("Segoe UI", 24, "bold"),
        )
        title_label.pack(anchor="w", padx=28, pady=(18, 0))

        subtitle_label = Label(
            header,
            text=subtitle,
            bg=HEADER_BG,
            fg="#d1d5db",
            font=("Segoe UI", 10),
        )
        subtitle_label.pack(anchor="w", padx=30, pady=(2, 0))

        body = Frame(self.content, bg=DARK_BG)
        body.pack(fill="both", expand=True, padx=18, pady=18)

        return body

    def make_panel(self, parent, title_text: str) -> Frame:
        panel = Frame(parent, bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="x", pady=(0, 14))

        title = Label(
            panel,
            text=title_text,
            bg=PANEL_BG,
            fg=TEXT_FG,
            font=("Segoe UI", 11, "bold"),
        )
        title.pack(anchor="w", padx=14, pady=(12, 6))

        return panel

    def make_entry(self, parent, textvariable: StringVar) -> Entry:
        entry = Entry(
            parent,
            textvariable=textvariable,
            bg=FIELD_BG,
            fg=TEXT_FG,
            insertbackground=TEXT_FG,
            relief="flat",
            highlightbackground=BORDER,
            highlightcolor=BLUE,
            highlightthickness=1,
            font=("Segoe UI", 10),
        )

        return entry

    def make_log_panel(self, parent):
        panel = Frame(parent, bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True)

        title = Label(
            panel,
            text="SEUnpacker Log",
            bg=PANEL_BG,
            fg=TEXT_FG,
            font=("Segoe UI", 11, "bold"),
        )
        title.pack(anchor="w", padx=14, pady=(12, 6))

        self.log = ScrolledText(
            panel,
            wrap="word",
            height=18,
            bg=LOG_BG,
            fg=TEXT_FG,
            insertbackground=TEXT_FG,
            relief="flat",
            highlightbackground=BORDER,
            highlightcolor=BLUE,
            highlightthickness=1,
            font=("Consolas", 10),
        )
        self.log.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def refresh_twitch_direct_feed_status(self):
        status_text = get_twitch_direct_feed_status_text()
        self.twitch_direct_status_var.set(status_text)
        self.write_log(status_text)
        self.update_connection_flash_buttons()

    def is_twitch_connected(self) -> bool:
        config = read_twitch_direct_feed_config()
        return bool(config.get("enabled") and config.get("client_id") and config.get("access_token") and config.get("broadcaster_user_id"))

    def is_stream_elements_connected(self) -> bool:
        status = read_streamelements_login_status()
        return status.get("status") == "logged_in"

    def update_connection_flash_buttons(self):
        try:
            buttons = [
                (getattr(self, "stream_elements_connect_button", None), self.is_stream_elements_connected()),
                (getattr(self, "twitch_connect_button", None), self.is_twitch_connected()),
            ]
            for btn, connected in buttons:
                if not btn:
                    continue
                if connected:
                    btn.configure(bg=BLUE, fg="white", activebackground=BLUE_HOVER, activeforeground="white")
                else:
                    flash_on = bool(getattr(self, "connection_flash_on", False))
                    btn.configure(
                        bg=YELLOW if flash_on else BLUE,
                        fg="#111827" if flash_on else "white",
                        activebackground=YELLOW,
                        activeforeground="#111827",
                    )
        except Exception:
            pass

    def schedule_connection_flash(self):
        self.connection_flash_on = not bool(getattr(self, "connection_flash_on", False))
        self.update_connection_flash_buttons()
        try:
            self.root.after(1100, self.schedule_connection_flash)
        except Exception:
            pass

    def connect_twitch_one_click(self):
        self.write_log("Opening Twitch authorization...")
        self.twitch_direct_status_var.set("Twitch: Connecting...")
        self.update_connection_flash_buttons()

        def worker():
            ok, msg, payload = run_twitch_one_click_authorization(TWITCH_DEFAULT_CLIENT_ID, log_func=self.write_log)

            def finish():
                if ok:
                    channel = payload.get("display_name") or payload.get("channel_login") or payload.get("broadcaster_user_id", "")
                    self.twitch_direct_status_var.set(f"Twitch: Connected as {channel}")
                    self.write_log("Twitch connected. Future local widgets will use Twitch as the data source.")
                else:
                    self.twitch_direct_status_var.set(get_twitch_direct_feed_status_text())
                    self.write_log(msg)
                    messagebox.showerror(APP_NAME, msg)
                self.update_connection_flash_buttons()

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def clear_twitch_auth_status(self):
        confirm = messagebox.askyesno(
            APP_NAME,
            "Clear saved Twitch authorization for SEUnpacker?\n\nThis removes the stored Twitch token and connected channel from the app. You can reconnect with the Connect to Twitch button."
        )
        if not confirm:
            return
        clear_twitch_direct_feed_config()
        try:
            self.twitch_direct_status_var.set(get_twitch_direct_feed_status_text())
        except Exception:
            pass
        self.write_log("Cleared saved Twitch authorization status.")
        self.update_connection_flash_buttons()
        messagebox.showinfo(APP_NAME, "Twitch authorization was cleared. Use Connect to Twitch to authorize again.")

    def open_twitch_direct_feed_settings(self):
        config = read_twitch_direct_feed_config()
        win = Toplevel(self.root)
        win.title("Twitch Direct Feed")
        win.geometry("720x520")
        win.configure(bg=DARK_BG)
        win.transient(self.root)
        win.grab_set()

        enabled_var = StringVar(value="yes" if config.get("enabled") else "no")
        client_id_var = StringVar(value=str(config.get("client_id") or TWITCH_DEFAULT_CLIENT_ID))
        token_var = StringVar(value=str(config.get("access_token", "")))
        broadcaster_var = StringVar(value=str(config.get("broadcaster_user_id", "")))
        channel_var = StringVar(value=str(config.get("channel_login", "")))
        status_var = StringVar(value="Click Authorize Twitch to connect. Manual token entry remains available for troubleshooting.")

        def label(parent, text):
            Label(parent, text=text, bg=DARK_BG, fg=TEXT_FG, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(10, 3))

        def entry(parent, var, show=None):
            e = Entry(parent, textvariable=var, bg=FIELD_BG, fg=TEXT_FG, insertbackground=TEXT_FG, relief="flat", highlightbackground=BORDER, highlightcolor=BLUE, highlightthickness=1, font=("Segoe UI", 10), show=show or "")
            e.pack(fill="x", padx=18, ipady=7)
            return e

        Label(win, text="Twitch Direct Feed", bg=DARK_BG, fg=TEXT_FG, font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=18, pady=(18, 4))
        Label(win, text="This is optional. It embeds Twitch EventSub settings into local widgets so they can receive live Twitch activity directly.", bg=DARK_BG, fg=MUTED_FG, wraplength=660, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 10))

        label(win, "Enabled? Type yes or no")
        entry(win, enabled_var)
        label(win, "Twitch Client ID")
        entry(win, client_id_var)
        label(win, "OAuth Access Token")
        entry(win, token_var, show="*")
        label(win, "Broadcaster User ID")
        entry(win, broadcaster_var)
        label(win, "Channel Login / Display Name")
        entry(win, channel_var)

        Label(win, textvariable=status_var, bg=DARK_BG, fg=MUTED_FG, wraplength=660, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(10, 10))

        buttons = Frame(win, bg=DARK_BG)
        buttons.pack(fill="x", padx=18, pady=(4, 18))

        def authorize_twitch():
            cid = (client_id_var.get().strip() or TWITCH_DEFAULT_CLIENT_ID)
            client_id_var.set(cid)
            status_var.set("Opening Twitch authorization. Complete the Twitch prompt in your browser...")

            def worker():
                ok, msg, payload = run_twitch_one_click_authorization(cid, log_func=self.write_log)

                def finish():
                    status_var.set(msg)
                    if ok and payload:
                        enabled_var.set("yes")
                        token_var.set(payload.get("access_token", ""))
                        broadcaster_var.set(payload.get("broadcaster_user_id", ""))
                        channel_var.set(payload.get("channel_login") or payload.get("display_name") or "")
                        self.twitch_direct_status_var.set(get_twitch_direct_feed_status_text())
                        self.write_log("Twitch authorization complete and saved.")
                    else:
                        self.write_log(msg)

                self.root.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        def open_docs():
            webbrowser.open("https://dev.twitch.tv/console/apps")

        def validate():
            ok, msg, user = validate_twitch_token(client_id_var.get(), token_var.get())
            status_var.set(msg)
            if ok and user:
                broadcaster_var.set(str(user.get("id", broadcaster_var.get())))
                channel_var.set(str(user.get("login") or user.get("display_name") or channel_var.get()))

        def save():
            payload = {
                "enabled": enabled_var.get().strip().lower() in {"yes", "true", "1", "on"},
                "client_id": client_id_var.get().strip(),
                "access_token": token_var.get().strip(),
                "broadcaster_user_id": broadcaster_var.get().strip(),
                "channel_login": channel_var.get().strip(),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            write_twitch_direct_feed_config(payload)
            self.twitch_direct_status_var.set(get_twitch_direct_feed_status_text())
            self.write_log("Saved Twitch Direct Feed settings.")
            win.destroy()

        def clear_from_settings():
            clear_twitch_direct_feed_config()
            enabled_var.set("no")
            token_var.set("")
            broadcaster_var.set("")
            channel_var.set("")
            status_var.set("Saved Twitch authorization was cleared.")
            self.twitch_direct_status_var.set(get_twitch_direct_feed_status_text())
            self.write_log("Cleared saved Twitch authorization status.")
            self.update_connection_flash_buttons()

        BlueButton(buttons, text="Authorize Twitch", command=authorize_twitch).pack(side="left", padx=(0, 8))
        BlueButton(buttons, text="Open Twitch Apps", command=open_docs).pack(side="left", padx=(0, 8))
        BlueButton(buttons, text="Validate Token", command=validate).pack(side="left", padx=(0, 8))
        Button(buttons, text="Clear Twitch Auth", command=clear_from_settings, bg="#dc2626", fg="white", activebackground="#b91c1c", activeforeground="white", relief="flat", padx=14, pady=8).pack(side="left", padx=(0, 8))
        BlueButton(buttons, text="Save", command=save).pack(side="right", padx=(8, 0))
        Button(buttons, text="Cancel", command=win.destroy, bg=HEADER_BG, fg=TEXT_FG, activebackground=SIDEBAR_ACTIVE, activeforeground=TEXT_FG, relief="flat", padx=14, pady=8).pack(side="right")

    def show_dashboard(self):
        self.set_active_tab("dashboard")
        body = self.make_page(
            "Dashboard",
            "Select a StreamElements alert or widget ZIP, then let SEUnpacker choose the correct Firebot install path.",
        )

        connection_panel = self.make_panel(body, "Connections")
        connection_row = Frame(connection_panel, bg=PANEL_BG)
        connection_row.pack(fill="x", padx=14, pady=(0, 8))

        se_box = Frame(connection_row, bg=PANEL_BG)
        se_box.pack(side="left", fill="x", expand=True, padx=(0, 8))
        Label(se_box, textvariable=self.stream_elements_login_status_var, bg=PANEL_BG, fg=TEXT_FG, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.stream_elements_connect_button = BlueButton(se_box, text="Connect to StreamElements", command=self.open_streamelements_login_window, width=26)
        self.stream_elements_connect_button.pack(anchor="w", pady=(6, 0))

        twitch_box = Frame(connection_row, bg=PANEL_BG)
        twitch_box.pack(side="left", fill="x", expand=True, padx=(8, 0))
        Label(twitch_box, textvariable=self.twitch_direct_status_var, bg=PANEL_BG, fg=TEXT_FG, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.twitch_connect_button = BlueButton(twitch_box, text="Connect to Twitch", command=self.connect_twitch_one_click, width=26)
        self.twitch_connect_button.pack(anchor="w", pady=(6, 0))

        Label(
            connection_panel,
            text="Connect StreamElements for URL imports. Connect Twitch so local widgets can pull live Twitch data directly.",
            bg=PANEL_BG,
            fg=MUTED_FG,
            justify="left",
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=14, pady=(0, 14))

        paths_panel = self.make_panel(body, "Alert or Widget ZIP")
        zip_row = Frame(paths_panel, bg=PANEL_BG)
        zip_row.pack(fill="x", padx=14, pady=(0, 14))

        zip_entry = self.make_entry(zip_row, self.zip_path_var)
        zip_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=7)

        BlueButton(zip_row, text="Browse ZIP", command=self.select_zip).pack(side="left")

        action_panel = Frame(body, bg=DARK_BG)
        action_panel.pack(fill="x", pady=(0, 14))

        BlueButton(action_panel, text="Unpack & Install", command=self.unpack_and_install, width=22).pack(side="left", padx=(0, 8))
        BlueButton(action_panel, text="Check Firebot", command=self.check_firebot_status).pack(side="left", padx=(0, 8))
        BlueButton(action_panel, text="Clear Log", command=self.clear_log).pack(side="right")

        self.make_log_panel(body)

        self.write_log(f"{APP_NAME} v{APP_VERSION} ready.")
        self.write_log("v0.8.5 seeds local widgets from Firebot history first, then uses Twitch for live updates.")
        if webview is None:
            self.write_log("Embedded browser support is not installed in this Python environment. A packaged EXE should bundle pywebview so the StreamElements login/import opens inside SEUnpacker.")
        self.write_log("Log into StreamElements first for the smoothest URL widget import flow.")
        self.write_log("Connect Twitch before installing local widgets that need live Twitch data.")
        self.write_log("Select a ZIP to begin.")
        self.update_connection_flash_buttons()
        if not getattr(self, "connection_flash_started", False):
            self.connection_flash_started = True
            self.root.after(1100, self.schedule_connection_flash)

    def show_analyze(self):
        self.set_active_tab("analyze")
        body = self.make_page(
            "Analyze Pack",
            "Inspect the ZIP and detect whether it is an alert pack or widget pack.",
        )

        panel = self.make_panel(body, "Pack Analysis")
        row = Frame(panel, bg=PANEL_BG)
        row.pack(fill="x", padx=14, pady=(0, 14))

        entry = self.make_entry(row, self.zip_path_var)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=7)

        BlueButton(row, text="Select ZIP", command=self.select_zip).pack(side="left", padx=(0, 8))
        BlueButton(row, text="Analyze Pack", command=self.analyze_selected_pack).pack(side="left")

        self.make_log_panel(body)

    def show_build(self):
        self.set_active_tab("build")
        body = self.make_page(
            "Build",
            "Generate Firebot-ready alert HTML or persistent widget HTML.",
        )

        panel = self.make_panel(body, "Build Settings")
        row1 = Frame(panel, bg=PANEL_BG)
        row1.pack(fill="x", padx=14, pady=(0, 10))

        Label(row1, text="ZIP", bg=PANEL_BG, fg=MUTED_FG, width=10, anchor="w").pack(side="left")
        zip_entry = self.make_entry(row1, self.zip_path_var)
        zip_entry.pack(side="left", fill="x", expand=True, ipady=7)

        row2 = Frame(panel, bg=PANEL_BG)
        row2.pack(fill="x", padx=14, pady=(0, 14))

        Label(row2, text="Output", bg=PANEL_BG, fg=MUTED_FG, width=10, anchor="w").pack(side="left")
        output_entry = self.make_entry(row2, self.output_path_var)
        output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=7)

        BlueButton(row2, text="Choose", command=self.select_output).pack(side="left")

        actions = Frame(body, bg=DARK_BG)
        actions.pack(fill="x", pady=(0, 14))

        BlueButton(actions, text="Build", command=self.build_pack).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Open Output Folder", command=self.open_output_folder).pack(side="left", padx=(0, 8))

        self.make_log_panel(body)

    def show_install(self):
        self.set_active_tab("install")
        body = self.make_page(
            "Install Assets",
            "Copy generated alert or widget files into Firebot overlay resources.",
        )

        panel = self.make_panel(body, "Firebot Resource Destination")
        row = Frame(panel, bg=PANEL_BG)
        row.pack(fill="x", padx=14, pady=(0, 14))

        entry = self.make_entry(row, self.firebot_resources_var)
        entry.pack(side="left", fill="x", expand=True, ipady=7)

        actions = Frame(body, bg=DARK_BG)
        actions.pack(fill="x", pady=(0, 14))

        BlueButton(actions, text="Check Firebot Status", command=self.check_firebot_status).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Port Diagnostic", command=self.show_port_diagnostic).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Install Assets", command=self.install_pack).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Open Firebot Resources", command=self.open_firebot_resources_folder).pack(side="left", padx=(0, 8))

        warning = Label(
            body,
            text="Firebot must be fully closed before installing resources.",
            bg=DARK_BG,
            fg=YELLOW,
            font=("Segoe UI", 10, "bold"),
        )
        warning.pack(anchor="w", pady=(0, 12))

        self.make_log_panel(body)

    def show_event_builder(self):
        self.set_active_tab("events")

        body = self.make_page(
            "Event Builder",
            "Create Firebot alert events for alert asset packs.",
        )

        info_panel = self.make_panel(body, "Firebot Event Creation")
        info_text = Label(
            info_panel,
            text=(
                "Use this only for alert asset packs.\n"
                "For StreamElements widget packs, use Widget / Preset instead.\n\n"
                "Events created:\n"
                "- Follow\n"
                "- Sub / Resub\n"
                "- Gift Sub\n"
                "- Community Gift\n"
                "- Cheer / Bits\n"
                "- Raid\n\n"
                "SEUnpacker backs up events.json before making changes."
            ),
            bg=PANEL_BG,
            fg=TEXT_FG,
            justify="left",
            font=("Segoe UI", 10),
        )
        info_text.pack(anchor="w", padx=14, pady=(0, 14))

        events_panel = self.make_panel(body, "Firebot Events File")
        events_row = Frame(events_panel, bg=PANEL_BG)
        events_row.pack(fill="x", padx=14, pady=(0, 14))

        events_entry = self.make_entry(events_row, self.firebot_events_var)
        events_entry.pack(side="left", fill="x", expand=True, ipady=7)

        actions = Frame(body, bg=DARK_BG)
        actions.pack(fill="x", pady=(0, 14))

        BlueButton(actions, text="Check Firebot Status", command=self.check_firebot_status).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Create Firebot Events", command=self.create_firebot_events).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Open Firebot Events Folder", command=self.open_firebot_events_folder).pack(side="left", padx=(0, 8))

        warning = Label(
            body,
            text="Close Firebot before creating events. Reopen Firebot afterward to see the new events.",
            bg=DARK_BG,
            fg=YELLOW,
            font=("Segoe UI", 10, "bold"),
        )
        warning.pack(anchor="w", pady=(0, 12))

        self.make_log_panel(body)

    def show_widget_builder(self):
        self.set_active_tab("widgets")

        body = self.make_page(
            "Widget / Preset",
            "Create a persistent overlay widget and a preset effect list from StreamElements widget packs.",
        )

        info_panel = self.make_panel(body, "Widget and Preset Creation")
        info_text = Label(
            info_panel,
            text=(
                "Use this for StreamElements widget packs. Local widget exports are rebuilt directly. URL-only widget packs use the StreamElements import flow.\n\n"
                "For URL-only widget packs:\n"
                "1. Build the pack.\n"
                "2. Click Open Primary SE Import URL.\n"
                "3. Import the overlay in StreamElements.\n"
                "4. Use the StreamElements three-dot menu -> Copy URL.\n"
                "5. Paste that copied browser-source URL below.\n"
                "6. Create Widget / Preset.\n\n"
                "SEUnpacker will write a Firebot custom widget that iframes the copied StreamElements browser-source URL."
            ),
            bg=PANEL_BG,
            fg=TEXT_FG,
            justify="left",
            font=("Segoe UI", 10),
            wraplength=760,
        )
        info_text.pack(anchor="w", padx=14, pady=(0, 14))

        se_panel = self.make_panel(body, "StreamElements URL Widget Import")
        se_help = Label(
            se_panel,
            text=(
                "For URL-only widget packs, click Open Primary SE Import URL, import it into StreamElements, "
                "then paste the final Copy URL browser-source link here. Leave blank for local widget export packs."
            ),
            bg=PANEL_BG,
            fg=MUTED_FG,
            justify="left",
            font=("Segoe UI", 10),
            wraplength=820,
        )
        se_help.pack(anchor="w", padx=14, pady=(0, 8))

        se_row = Frame(se_panel, bg=PANEL_BG)
        se_row.pack(fill="x", padx=14, pady=(0, 14))

        se_entry = self.make_entry(se_row, self.stream_elements_overlay_url_var)
        se_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=7)

        BlueButton(se_row, text="Open Primary SE Import URL", command=self.open_primary_streamelements_import_url).pack(side="left", padx=(0, 8))
        BlueButton(se_row, text="Clear URL", command=self.clear_stream_elements_overlay_url).pack(side="left")

        widgets_panel = self.make_panel(body, "Firebot Widget / Preset Files")
        widgets_row = Frame(widgets_panel, bg=PANEL_BG)
        widgets_row.pack(fill="x", padx=14, pady=(0, 8))

        widgets_entry = self.make_entry(widgets_row, self.firebot_widgets_var)
        widgets_entry.pack(side="left", fill="x", expand=True, ipady=7)

        presets_row = Frame(widgets_panel, bg=PANEL_BG)
        presets_row.pack(fill="x", padx=14, pady=(0, 14))

        presets_entry = self.make_entry(presets_row, self.firebot_presets_var)
        presets_entry.pack(side="left", fill="x", expand=True, ipady=7)

        actions = Frame(body, bg=DARK_BG)
        actions.pack(fill="x", pady=(0, 14))

        BlueButton(actions, text="Check Firebot Status", command=self.check_firebot_status).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Build", command=self.build_pack).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Install Assets", command=self.install_pack).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Create Widget / Preset", command=self.create_widget_and_preset).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Open Firebot Profile", command=self.open_firebot_profile_folder).pack(side="left", padx=(0, 8))

        warning = Label(
            body,
            text="Close Firebot before creating widgets or presets. Reopen Firebot afterward to check Overlay Widgets and Preset Effect Lists.",
            bg=DARK_BG,
            fg=YELLOW,
            font=("Segoe UI", 10, "bold"),
        )
        warning.pack(anchor="w", pady=(0, 12))

        self.make_log_panel(body)

    def show_uninstall_packs(self):
        self.set_active_tab("uninstall")
        body = self.make_page(
            "Uninstall Packs",
            "Remove specific SEUnpacker-installed packs from Firebot, or remove all SEUnpacker installs.",
        )

        state = {"selected_slug": "", "selected_name": "", "buttons": []}

        info_panel = self.make_panel(body, "Installed SEUnpacker Packs")
        info = Label(
            info_panel,
            text=(
                "Select a pack below, then click Delete Selected Pack. "
                "This removes the Firebot widget/preset/event records for that pack and deletes its local overlay resource folder.\n\n"
                "Firebot must be fully closed before uninstalling."
            ),
            bg=PANEL_BG,
            fg=TEXT_FG,
            justify="left",
            font=("Segoe UI", 10),
            wraplength=820,
        )
        info.pack(anchor="w", padx=14, pady=(0, 12))

        list_panel = Frame(info_panel, bg=PANEL_BG)
        list_panel.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        selected_label = Label(
            info_panel,
            text="No pack selected.",
            bg=PANEL_BG,
            fg=MUTED_FG,
            font=("Segoe UI", 10, "bold"),
        )
        selected_label.pack(anchor="w", padx=14, pady=(0, 14))

        actions = Frame(body, bg=DARK_BG)
        actions.pack(fill="x", pady=(0, 14))

        delete_button = Button(
            actions,
            text="Delete Selected Pack",
            command=lambda: delete_selected_pack(),
            width=22,
            bg="#4b5563",
            fg="white",
            activebackground="#991b1b",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="arrow",
            font=("Segoe UI", 10, "bold"),
            state="disabled",
        )
        delete_button.pack(side="left", padx=(0, 8))

        BlueButton(actions, text="Refresh List", command=lambda: refresh_pack_list()).pack(side="left", padx=(0, 8))

        nuke_button = Button(
            actions,
            text="Nuke All SEUnpacker Installs",
            command=lambda: nuke_all_installs_with_double_confirm(),
            bg="#7f1d1d",
            fg="white",
            activebackground="#991b1b",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        )
        nuke_button.pack(side="right")

        self.make_log_panel(body)

        def set_selected(pack: dict):
            state["selected_slug"] = pack["pack_slug"]
            state["selected_name"] = pack["display_name"]
            selected_label.configure(text=f"Selected: {pack['display_name']}", fg=TEXT_FG)
            delete_button.configure(state="normal", bg="#dc2626", cursor="hand2")
            for button, button_slug in state["buttons"]:
                button.configure(bg=BLUE if button_slug == pack["pack_slug"] else FIELD_BG)

        def refresh_pack_list():
            for child in list_panel.winfo_children():
                child.destroy()
            state["buttons"] = []
            state["selected_slug"] = ""
            state["selected_name"] = ""
            selected_label.configure(text="No pack selected.", fg=MUTED_FG)
            delete_button.configure(state="disabled", bg="#4b5563", cursor="arrow")

            try:
                packs = discover_installed_seunpacker_packs()
            except Exception as exc:
                self.handle_error(exc)
                return

            if not packs:
                Label(
                    list_panel,
                    text="No SEUnpacker-installed packs were found in the Firebot profile.",
                    bg=PANEL_BG,
                    fg=MUTED_FG,
                    font=("Segoe UI", 10),
                ).pack(anchor="w", pady=(0, 8))
                self.write_log("No SEUnpacker-installed packs found.")
                return

            for pack in packs:
                details = []
                if pack.get("widgets"):
                    details.append(f"widgets: {pack['widgets']}")
                if pack.get("presets"):
                    details.append(f"presets: {pack['presets']}")
                if pack.get("events"):
                    details.append(f"events: {pack['events']}")
                if pack.get("has_resources"):
                    details.append("resources")
                detail_text = ", ".join(details) if details else "detected"
                button_text = f"{pack['display_name']}    ({detail_text})"

                btn = Button(
                    list_panel,
                    text=button_text,
                    command=lambda p=pack: set_selected(p),
                    anchor="w",
                    bg=FIELD_BG,
                    fg=TEXT_FG,
                    activebackground=BLUE_HOVER,
                    activeforeground="white",
                    relief="flat",
                    bd=0,
                    padx=14,
                    pady=10,
                    cursor="hand2",
                    font=("Segoe UI", 10, "bold"),
                )
                btn.pack(fill="x", pady=(0, 6))
                state["buttons"].append((btn, pack["pack_slug"]))

            self.write_log(f"Found {len(packs)} SEUnpacker-installed pack(s).")

        def delete_selected_pack():
            slug = state.get("selected_slug", "")
            name = state.get("selected_name", "")
            if not slug:
                return

            confirmed = messagebox.askyesno(
                APP_NAME,
                f"Delete this SEUnpacker pack from Firebot?\n\n{name}\n\n"
                "This will remove matching Firebot records and delete this pack's local overlay resources."
            )
            if not confirmed:
                return

            try:
                result = uninstall_seunpacker_pack(slug)
                self.write_log("")
                self.write_log(f"Uninstalled SEUnpacker pack: {name} ({slug})")
                self.write_log(f"Events removed: {result['events_removed']}")
                self.write_log(f"Widgets removed: {result['widgets_removed']}")
                self.write_log(f"Presets removed: {result['presets_removed']}")
                self.write_log(f"Resources removed: {result['resources_removed']}")
                refresh_pack_list()
                messagebox.showinfo(APP_NAME, f"Removed pack:\n\n{name}")
            except Exception as exc:
                self.handle_error(exc)

        def confirm_nuke_dialog(title: str, message: str, confirm_text: str, confirm_bg: str = BLUE) -> bool:
            decision = {"value": False}
            dialog = Toplevel(self.root)
            dialog.title(title)
            dialog.geometry("520x260")
            dialog.configure(bg=DARK_BG)
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.resizable(False, False)

            Label(
                dialog,
                text=title,
                bg=HEADER_BG,
                fg=TEXT_FG,
                font=("Segoe UI", 16, "bold"),
                anchor="w",
                padx=18,
                pady=14,
            ).pack(fill="x")

            Label(
                dialog,
                text=message,
                bg=DARK_BG,
                fg=TEXT_FG,
                justify="left",
                wraplength=470,
                font=("Segoe UI", 10),
            ).pack(fill="both", expand=True, padx=18, pady=(18, 12), anchor="w")

            row = Frame(dialog, bg=DARK_BG)
            row.pack(fill="x", padx=18, pady=(0, 18))

            def cancel():
                decision["value"] = False
                dialog.destroy()

            def confirm():
                decision["value"] = True
                dialog.destroy()

            Button(
                row,
                text="Cancel",
                command=cancel,
                bg="#4b5563",
                fg="white",
                activebackground="#374151",
                activeforeground="white",
                relief="flat",
                bd=0,
                padx=14,
                pady=8,
                cursor="hand2",
                font=("Segoe UI", 10, "bold"),
            ).pack(side="right", padx=(8, 0))

            Button(
                row,
                text=confirm_text,
                command=confirm,
                bg=confirm_bg,
                fg="white",
                activebackground="#991b1b" if confirm_bg != BLUE else BLUE_HOVER,
                activeforeground="white",
                relief="flat",
                bd=0,
                padx=14,
                pady=8,
                cursor="hand2",
                font=("Segoe UI", 10, "bold"),
            ).pack(side="right")

            dialog.protocol("WM_DELETE_WINDOW", cancel)
            self.root.wait_window(dialog)
            return decision["value"]

        def nuke_all_installs_with_double_confirm():
            first = confirm_nuke_dialog(
                "Remove All SEUnpacker Installs",
                "You are about to remove every pack SEUnpacker has installed into Firebot.\n\n"
                "This removes SEUnpacker-created events, overlay widgets, preset effect lists, and local overlay resource folders.",
                "I understand",
                BLUE,
            )
            if not first:
                return

            second = confirm_nuke_dialog(
                "Final Confirmation",
                "This action is irreversible from inside SEUnpacker. Local overlay resource folders will be deleted.\n\n"
                "Are you absolutely sure you want to remove all SEUnpacker installs?",
                "Delete Everything",
                "#dc2626",
            )
            if not second:
                return

            try:
                result = nuke_all_seunpacker_installs()
                self.write_log("")
                self.write_log("Removed all SEUnpacker installs from Firebot.")
                self.write_log(f"Events removed: {result['events_removed']}")
                self.write_log(f"Widgets removed: {result['widgets_removed']}")
                self.write_log(f"Presets removed: {result['presets_removed']}")
                self.write_log(f"Resource items removed: {result['resources_removed']}")
                refresh_pack_list()
                messagebox.showinfo(APP_NAME, "All SEUnpacker installs were removed from Firebot.")
            except Exception as exc:
                self.handle_error(exc)

        refresh_pack_list()


    def show_widget_configurator(self):
        self.set_active_tab("configurator")
        body = self.make_page(
            "Widget Configurator",
            "Set SEUnpacker-side behavior for local widgets that cannot be edited directly inside Firebot.",
        )

        panel = self.make_panel(body, "Minimal Event Rotator Widget")
        Label(
            panel,
            text="These options are baked into the next install/rebuild of Minimal Event Rotator. After saving, uninstall and reinstall that pack so Firebot receives the updated widget.html.",
            bg=PANEL_BG,
            fg=MUTED_FG,
            wraplength=780,
            justify="left",
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=14, pady=(0, 12))

        config = read_minimal_event_rotator_config()
        vars_by_key = {}
        rows = [
            ("show_follower_count", "Follow Feeder: show follower count"),
            ("show_sub_months", "Sub Feeder: show total months subscribed"),
            ("show_single_gift_sub", "Gift Sub Feeder: show that the event was a gift sub"),
            ("show_community_gift_count", "Community Gift Feeder: show number gifted in that instance"),
            ("show_cheer_bits", "Cheer Feeder: show number of bits cheered"),
            ("show_raid_viewers", "Raid Feeder: show number of raiders/viewers"),
            ("show_tip_amount", "Tip Feeder: show tip/amount text when available"),
            ("show_redemptions", "Redemption Feeder: show latest redemption text"),
        ]

        for key, label_text in rows:
            var = StringVar(value="1" if config.get(key) else "0")
            vars_by_key[key] = var
            cb = Checkbutton(
                panel,
                text=label_text,
                variable=var,
                onvalue="1",
                offvalue="0",
                bg=PANEL_BG,
                fg=TEXT_FG,
                activebackground=PANEL_BG,
                activeforeground=TEXT_FG,
                selectcolor=FIELD_BG,
                font=("Segoe UI", 10),
                anchor="w",
            )
            cb.pack(fill="x", padx=14, pady=3)

        actions = Frame(panel, bg=PANEL_BG)
        actions.pack(fill="x", padx=14, pady=(14, 14))

        def save_config():
            new_config = {key: (var.get() == "1") for key, var in vars_by_key.items()}
            write_minimal_event_rotator_config(new_config)
            self.write_log("Saved Minimal Event Rotator widget configuration.")
            messagebox.showinfo(APP_NAME, "Widget configuration saved. Reinstall Minimal Event Rotator for the changes to apply.")

        def reset_config():
            defaults = get_default_minimal_event_rotator_config()
            for key, value in defaults.items():
                if key in vars_by_key:
                    vars_by_key[key].set("1" if value else "0")
            write_minimal_event_rotator_config(defaults)
            self.write_log("Reset Minimal Event Rotator widget configuration to defaults.")

        BlueButton(actions, text="Save Widget Config", command=save_config).pack(side="left", padx=(0, 8))
        Button(
            actions,
            text="Reset Defaults",
            command=reset_config,
            bg="#4b5563",
            fg="white",
            activebackground="#374151",
            activeforeground="white",
            relief="flat",
            padx=14,
            pady=8,
        ).pack(side="left")

        self.make_log_panel(body)

    def show_notes(self):
        self.set_active_tab("notes")
        body = self.make_page(
            "Setup Notes",
            "View generated setup notes.",
        )

        actions = Frame(body, bg=DARK_BG)
        actions.pack(fill="x", pady=(0, 14))

        BlueButton(actions, text="Open README", command=self.open_readme).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Open Output Folder", command=self.open_output_folder).pack(side="left", padx=(0, 8))
        BlueButton(actions, text="Open Firebot Profile", command=self.open_firebot_profile_folder).pack(side="left", padx=(0, 8))

        self.make_log_panel(body)

    def show_settings(self):
        self.set_active_tab("settings")
        body = self.make_page(
            "Settings",
            "Manage paths and app behavior.",
        )

        output_panel = self.make_panel(body, "Default Output Folder")
        output_row = Frame(output_panel, bg=PANEL_BG)
        output_row.pack(fill="x", padx=14, pady=(0, 14))

        output_entry = self.make_entry(output_row, self.output_path_var)
        output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=7)

        BlueButton(output_row, text="Choose Output", command=self.select_output).pack(side="left", padx=(0, 8))
        BlueButton(output_row, text="Open Output", command=self.open_output_folder).pack(side="left")

        firebot_panel = self.make_panel(body, "Firebot Overlay Resources")
        firebot_row = Frame(firebot_panel, bg=PANEL_BG)
        firebot_row.pack(fill="x", padx=14, pady=(0, 14))

        firebot_entry = self.make_entry(firebot_row, self.firebot_resources_var)
        firebot_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=7)

        BlueButton(firebot_row, text="Open Folder", command=self.open_firebot_resources_folder).pack(side="left")

        profile_panel = self.make_panel(body, "Firebot Profile Files")
        profile_row = Frame(profile_panel, bg=PANEL_BG)
        profile_row.pack(fill="x", padx=14, pady=(0, 8))

        widgets_entry = self.make_entry(profile_row, self.firebot_widgets_var)
        widgets_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=7)

        preset_row = Frame(profile_panel, bg=PANEL_BG)
        preset_row.pack(fill="x", padx=14, pady=(0, 14))

        preset_entry = self.make_entry(preset_row, self.firebot_presets_var)
        preset_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=7)

        BlueButton(preset_row, text="Open Profile", command=self.open_firebot_profile_folder).pack(side="left")

        twitch_panel = self.make_panel(body, "Twitch Authorization")
        twitch_row = Frame(twitch_panel, bg=PANEL_BG)
        twitch_row.pack(fill="x", padx=14, pady=(0, 14))

        Label(
            twitch_row,
            textvariable=self.twitch_direct_status_var,
            bg=PANEL_BG,
            fg=TEXT_FG,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", fill="x", expand=True)

        BlueButton(twitch_row, text="Connect to Twitch", command=self.connect_twitch_one_click).pack(side="left", padx=(0, 8))
        Button(
            twitch_row,
            text="Clear Twitch Auth",
            command=self.clear_twitch_auth_status,
            bg="#dc2626",
            fg="white",
            activebackground="#b91c1c",
            activeforeground="white",
            relief="flat",
            padx=14,
            pady=8,
        ).pack(side="left")

        self.make_log_panel(body)

    def write_log(self, message: str):
        if self.log is not None and self.log.winfo_exists():
            self.log.insert(END, message + "\n")
            self.log.see(END)
            self.root.update_idletasks()

    def clear_log(self):
        if self.log is not None and self.log.winfo_exists():
            self.log.delete("1.0", END)

    def clear_current_pack(self):
        self.current_pack_info = None

    def select_zip(self):
        path = filedialog.askopenfilename(
            title="Select Alert or Widget ZIP",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
        )

        if path:
            self.zip_path_var.set(path)
            self.clear_current_pack()
            self.write_log(f"Selected ZIP: {path}")
            self.write_log("Current build cleared. Build again before install/create.")

    def select_output(self):
        path = filedialog.askdirectory(title="Select Output Folder")

        if path:
            self.output_path_var.set(path)
            self.clear_current_pack()
            self.write_log(f"Output folder set to: {path}")
            self.write_log("Current build cleared. Build again before install/create.")

    def get_zip_path(self) -> Path:
        path = Path(self.zip_path_var.get().strip())

        if not path.exists():
            raise FileNotFoundError("Selected ZIP file does not exist.")

        if path.suffix.lower() != ".zip":
            raise ValueError("Selected file is not a ZIP file.")

        return path

    def get_output_path(self) -> Path:
        path = Path(self.output_path_var.get().strip())
        path.mkdir(parents=True, exist_ok=True)
        return path

    def is_current_pack_for_selected_zip(self) -> bool:
        if self.current_pack_info is None:
            return False

        try:
            zip_path = self.get_zip_path()
        except Exception:
            return False

        current_source = self.current_pack_info.get("source_zip", "")
        current_mtime = self.current_pack_info.get("source_zip_mtime", None)

        return (
            str(zip_path.resolve()) == current_source
            and current_mtime == zip_path.stat().st_mtime
        )

    def ensure_current_pack_built(self):
        if not self.is_current_pack_for_selected_zip():
            self.write_log("")
            self.write_log("Selected ZIP is new or changed. Building fresh pack...")
            self.build_pack()

        if self.current_pack_info is None:
            raise RuntimeError("No built pack found. Build the pack first.")


    def check_for_updates(self, silent: bool = False):
        def worker():
            try:
                release = get_latest_github_release()
                latest_tag = str(release.get("tag_name") or release.get("name") or "").strip()
                if not latest_tag:
                    raise RuntimeError("GitHub did not return a release version.")

                if not is_newer_version(latest_tag, APP_VERSION):
                    if not silent:
                        self.root.after(0, lambda: messagebox.showinfo(APP_NAME, f"SEUnpacker is up to date.\n\nCurrent version: v{APP_VERSION}\nLatest release: {latest_tag}"))
                    return

                asset = find_release_asset(release)
                body = str(release.get("body") or "").strip()
                asset_name = asset.get("name") if asset else "No SEUnpacker.exe asset found"

                def prompt_update():
                    message = (
                        f"A new SEUnpacker update is available.\n\n"
                        f"Current version: v{APP_VERSION}\n"
                        f"Latest version: {latest_tag}\n"
                        f"Release asset: {asset_name}\n\n"
                    )
                    if body:
                        preview = body[:700] + ("..." if len(body) > 700 else "")
                        message += f"Release notes:\n{preview}\n\n"
                    if asset:
                        message += "Download and install this update now?"
                        if messagebox.askyesno(APP_NAME, message):
                            self.install_github_update(asset, latest_tag)
                    else:
                        message += "No downloadable SEUnpacker.exe was attached to the release. Open the GitHub releases page?"
                        if messagebox.askyesno(APP_NAME, message):
                            webbrowser.open(GITHUB_RELEASES_URL)

                self.root.after(0, prompt_update)

            except Exception as exc:
                if not silent:
                    self.root.after(0, lambda: messagebox.showerror(APP_NAME, f"Unable to check for updates.\n\n{exc}"))
                try:
                    self.write_log(f"Update check failed: {exc}")
                except Exception:
                    pass

        if not silent:
            self.write_log("Checking GitHub for SEUnpacker updates...")
        threading.Thread(target=worker, daemon=True).start()

    def install_github_update(self, asset: dict, latest_tag: str):
        try:
            download_url = asset.get("browser_download_url")
            asset_name = asset.get("name") or GITHUB_RELEASE_ASSET_NAME
            if not download_url:
                raise RuntimeError("The selected GitHub release asset does not have a download URL.")

            if not getattr(sys, "frozen", False):
                messagebox.showinfo(
                    APP_NAME,
                    "SEUnpacker is currently running from app.py, not the packaged EXE.\n\n"
                    "Opening the GitHub releases page instead. Download the release asset or use the update-only zip while developing."
                )
                webbrowser.open(GITHUB_RELEASES_URL)
                return

            current_exe = Path(sys.executable).resolve()
            update_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME / "Updates" / str(latest_tag).lstrip("v")
            downloaded = update_dir / asset_name

            self.write_log(f"Downloading SEUnpacker update {latest_tag}...")
            download_file(download_url, downloaded, log_func=self.write_log)

            if downloaded.suffix.lower() != ".exe":
                messagebox.showinfo(
                    APP_NAME,
                    f"Downloaded {asset_name}, but automatic replacement only supports SEUnpacker.exe for now.\n\nOpening the update folder."
                )
                os.startfile(update_dir)
                return

            updater_script = create_windows_self_update_script(downloaded, current_exe)
            self.write_log(f"Prepared updater script: {updater_script}")
            messagebox.showinfo(
                APP_NAME,
                "The update has been downloaded. SEUnpacker will close, replace itself, and reopen."
            )
            subprocess.Popen(["cmd", "/c", str(updater_script)], shell=False)
            self.root.after(300, self.root.destroy)

        except Exception as exc:
            self.write_log(f"Update install failed: {exc}")
            messagebox.showerror(APP_NAME, f"Update install failed.\n\n{exc}")

    def launch_firebot(self):
        ok, message = launch_firebot_desktop()
        self.write_log(message)
        if not ok:
            messagebox.showwarning(
                APP_NAME,
                message + "\n\nIf Firebot is installed in a custom location, launch it manually for now."
            )

    def check_firebot_status(self):
        running, reason = is_firebot_running()

        if running:
            self.write_log(f"Firebot status: RUNNING. {reason}")
            messagebox.showwarning(APP_NAME, f"Firebot appears to be running.\n\n{reason}")
        else:
            self.write_log(f"Firebot status: CLOSED. {reason}")
            messagebox.showinfo(APP_NAME, f"Firebot does not appear to be running.\n\n{reason}")

    def show_port_diagnostic(self):
        diagnostic = get_firebot_port_diagnostic(7472)

        self.write_log("")
        self.write_log("Port 7472 diagnostic:")
        for line in diagnostic.splitlines():
            self.write_log(line)

        messagebox.showinfo(
            APP_NAME,
            "Port 7472 diagnostic written to the SEUnpacker log.\n\n"
            "FIN_WAIT_2 and CLOSE_WAIT entries are ignored."
        )

    def unpack_and_install(self):
        """Run the normal SEUnpacker workflow from one user-facing button."""
        try:
            running, reason = is_firebot_running()
            if running:
                raise RuntimeError(
                    "Firebot appears to be running.\n\n"
                    f"{reason}\n\n"
                    "Close Firebot completely before unpacking and installing."
                )

            zip_path = self.get_zip_path()
            output_path = self.get_output_path()

            self.write_log("")
            self.write_log("Starting Unpack & Install workflow...")
            self.write_log(f"Selected ZIP: {zip_path}")

            self.write_log("Step 1/4: Analyzing pack...")
            analysis = analyze_zip(zip_path)
            self.write_log(f"Detected pack type: {analysis['pack_type']}")
            self.write_log(f"Shortcut URLs found: {len(analysis['shortcuts'])}")
            self.write_log(f"Images found: {len(analysis['images'])}")
            self.write_log(f"Audio found: {len(analysis['audio'])}")
            self.write_log(f"Widget files found: {len(analysis['widget_files'])}")

            self.write_log("Step 2/4: Building Firebot-ready package...")
            self.current_pack_info = build_firebot_pack(zip_path, output_path)
            self.write_log(f"Build complete: {self.current_pack_info['pack_dir']}")
            self.write_log(f"Final detected pack type: {self.current_pack_info['pack_type']}")

            self.write_log("Step 3/4: Installing assets without removing other SEUnpacker widgets...")
            target_dir = install_to_firebot_resources(self.current_pack_info)
            self.write_log(f"Installed assets to: {target_dir}")

            if self.current_pack_info["pack_type"] == "stream_elements_widget":
                if is_url_only_stream_elements_widget(self.current_pack_info):
                    self.write_log("Step 4/4: StreamElements URL widget detected.")
                    if not self.is_streamelements_logged_in():
                        self.write_log("StreamElements login has not been confirmed. Opening login window before import...")
                        self.waiting_for_login_then_import = True
                        messagebox.showinfo(
                            APP_NAME,
                            "This is a StreamElements URL widget pack.\n\n"
                            "Please log into StreamElements in the window that opens. "
                            "Once SEUnpacker confirms the login, it will continue the import flow automatically."
                        )
                        self.open_streamelements_login_window()
                        return

                    self.write_log("StreamElements login confirmed. Opening import assistant...")
                    self.show_streamelements_import_assistant()
                    return

                self.write_log("Step 4/4: Creating Firebot overlay widget and preset...")
                result = create_firebot_widget_and_preset_for_pack(self.current_pack_info)
                self.write_log(f"Created overlay widget: {result['created_widget']}")
                self.write_log(f"Created preset effect list: {result['created_preset']}")
                self.log_widget_feeder_result(result)
                self.write_log("Done. Reopen Firebot, then refresh OBS browser cache.")
                messagebox.showinfo(
                    APP_NAME,
                    "Widget installed successfully.\n\nReopen Firebot, then refresh the OBS browser source cache."
                )
                return

            self.write_log("Step 4/4: Creating Firebot events...")
            result = create_firebot_events_for_pack(self.current_pack_info)
            self.write_log(f"Created Firebot events: {len(result['created_events'])}")
            for event_name in result["created_events"]:
                self.write_log(f"  - {event_name}")
            self.write_log("Done. Reopen Firebot, then refresh OBS browser cache.")
            messagebox.showinfo(
                APP_NAME,
                "Alert events installed successfully.\n\nReopen Firebot, then refresh the OBS browser source cache."
            )

        except Exception as exc:
            self.handle_error(exc)

    def show_streamelements_copy_url_splash(self):
        """Show a temporary guide window while StreamElements is open.

        This window is only shown during URL-widget import. It mirrors the
        StreamElements My Overlays card layout closely enough that users know
        to click the three-dot menu and then Copy URL.
        """
        try:
            if self.se_copy_url_splash is not None and self.se_copy_url_splash.winfo_exists():
                self.se_copy_url_splash.lift()
                return
        except Exception:
            self.se_copy_url_splash = None

        splash = Toplevel(self.root)
        self.se_copy_url_splash = splash
        splash.title("SEUnpacker StreamElements Guide")
        splash.geometry("650x620+100+90")
        splash.minsize(610, 560)
        splash.configure(bg=DARK_BG)
        splash.transient(self.root)
        splash.attributes("-topmost", True)

        header = Frame(splash, bg=HEADER_BG, height=92)
        header.pack(fill="x")
        header.pack_propagate(False)

        Label(
            header,
            text="Copy the StreamElements Overlay URL",
            bg=HEADER_BG,
            fg=TEXT_FG,
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", padx=22, pady=(14, 0))

        Label(
            header,
            text="SEUnpacker is watching your clipboard. Click Copy URL on the imported overlay card.",
            bg=HEADER_BG,
            fg="#d1d5db",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=24, pady=(4, 0))

        body = Frame(splash, bg=DARK_BG)
        body.pack(fill="both", expand=True, padx=18, pady=16)

        steps_panel = self.make_panel(body, "Quick steps")
        Label(
            steps_panel,
            text=(
                "1. Log into StreamElements if prompted.\n"
                "2. Wait for the overlay card to appear in My Overlays.\n"
                "3. On the correct overlay card, click the three-dot menu.\n"
                "4. Click Copy URL at the top of that menu.\n"
                "5. SEUnpacker captures it automatically and closes this guide."
            ),
            bg=PANEL_BG,
            fg=TEXT_FG,
            justify="left",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=14, pady=(0, 12))

        mock_panel = Frame(body, bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1)
        mock_panel.pack(fill="both", expand=True, pady=(12, 0))

        Label(
            mock_panel,
            text="Look for a card like this",
            bg=PANEL_BG,
            fg=TEXT_FG,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 6))

        card_outer = Frame(mock_panel, bg=PANEL_BG)
        card_outer.pack(anchor="center", pady=(0, 10))

        card = Frame(card_outer, bg="#1f232b", highlightbackground="#374151", highlightthickness=1)
        card.pack(side="left", padx=(0, 20))

        preview = Canvas(card, width=250, height=126, bg="#11b9e8", highlightthickness=0)
        preview.pack(fill="x")
        # Draw a simple diagonal stripe preview like the StreamElements card in the screenshots.
        for x in range(-180, 300, 16):
            preview.create_line(x, 126, x + 126, 0, fill="#8b5cf6", width=4)
        preview.create_rectangle(0, 96, 250, 126, fill="#111827", outline="")
        preview.create_text(16, 108, anchor="w", text="[Kudos.TV] Minimal Hud", fill=TEXT_FG, font=("Segoe UI", 10, "bold"))

        title_row = Frame(card, bg="#1f232b")
        title_row.pack(fill="x", padx=12, pady=(10, 0))
        Label(
            title_row,
            text="[Kudos.TV] Minimal Hud\nv1.0.2 (Twitch)",
            bg="#1f232b",
            fg=TEXT_FG,
            justify="left",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", anchor="w")
        Label(
            title_row,
            text="☆",
            bg="#1f232b",
            fg="#6b7280",
            font=("Segoe UI", 19),
        ).pack(side="right", anchor="n")

        meta_row = Frame(card, bg="#1f232b")
        meta_row.pack(fill="x", padx=12, pady=(8, 8))
        Label(
            meta_row,
            text="RECENT",
            bg="#991b1b",
            fg="#fecaca",
            font=("Segoe UI", 7, "bold"),
            padx=6,
            pady=2,
        ).pack(side="left", anchor="w")

        action_row = Frame(card, bg="#1f232b")
        action_row.pack(fill="x", padx=12, pady=(0, 12))
        dots = Label(
            action_row,
            text="⋯",
            bg="#1f232b",
            fg=YELLOW,
            font=("Segoe UI", 18, "bold"),
        )
        dots.pack(side="left", anchor="w")
        Label(
            action_row,
            text="  EDIT  ",
            bg="#1f232b",
            fg=TEXT_FG,
            font=("Segoe UI", 9, "bold"),
            relief="solid",
            bd=1,
            padx=22,
            pady=6,
        ).pack(side="right", anchor="e")

        menu_column = Frame(card_outer, bg=PANEL_BG)
        menu_column.pack(side="left", anchor="s")
        Label(
            menu_column,
            text="Click the three dots, then choose:",
            bg=PANEL_BG,
            fg=YELLOW,
            justify="left",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        menu = Frame(menu_column, bg="#111827", highlightbackground=YELLOW, highlightthickness=2)
        menu.pack(anchor="w")

        Label(
            menu,
            text="  Copy URL  ",
            bg="#24324f",
            fg=TEXT_FG,
            font=("Segoe UI", 11, "bold"),
            width=20,
            anchor="w",
        ).pack(fill="x", padx=0, pady=(0, 0), ipady=9)
        for item in ["Properties", "Duplicate", "Delete"]:
            Label(
                menu,
                text=f"  {item}",
                bg="#111827",
                fg=MUTED_FG,
                font=("Segoe UI", 10, "bold"),
                width=20,
                anchor="w",
            ).pack(fill="x", ipady=8)

        warning = Label(
            body,
            text=(
                "Do not use the browser address bar URL. Only use the three-dot menu -> Copy URL.\n"
                "When SEUnpacker captures it, this guide closes and the install button flashes."
            ),
            bg=DARK_BG,
            fg=YELLOW,
            justify="left",
            font=("Segoe UI", 9, "bold"),
        )
        warning.pack(anchor="w", pady=(12, 0))

        def on_close():
            self.se_copy_url_splash = None
            splash.destroy()

        splash.protocol("WM_DELETE_WINDOW", on_close)

    def close_copy_url_splash_if_possible(self):
        try:
            if self.se_copy_url_splash is not None and self.se_copy_url_splash.winfo_exists():
                self.se_copy_url_splash.destroy()
            self.se_copy_url_splash = None
        except Exception:
            self.se_copy_url_splash = None

    def refresh_stream_elements_login_status(self, write_to_log: bool = True) -> bool:
        data = read_streamelements_login_status()
        status = data.get("status", "unknown")
        url = data.get("url", "")
        updated_at = data.get("updated_at", "")
        message = data.get("message", "")

        if status == "logged_in":
            self.stream_elements_login_status_var.set("StreamElements: Logged in")
            detail = "Ready for URL-based widget imports."
            if updated_at:
                detail += f" Last confirmed: {updated_at}."
            self.stream_elements_login_detail_var.set(detail)
            if write_to_log:
                self.write_log("StreamElements login status: logged in.")
            self.update_connection_flash_buttons()
            return True

        if status == "checking":
            self.stream_elements_login_status_var.set("StreamElements: Checking login...")
            self.stream_elements_login_detail_var.set(message or "A StreamElements login window is open. Complete login there.")
            if write_to_log:
                self.write_log("StreamElements login status: checking.")
            self.update_connection_flash_buttons()
            return False

        if status == "login_required":
            self.stream_elements_login_status_var.set("StreamElements: Login required")
            self.stream_elements_login_detail_var.set(message or "Click Connect to StreamElements before installing URL-based widget packs.")
            if write_to_log:
                self.write_log("StreamElements login status: login required.")
            self.update_connection_flash_buttons()
            return False

        self.stream_elements_login_status_var.set("StreamElements: Not checked")
        self.stream_elements_login_detail_var.set(message or "Click Connect to StreamElements before installing URL-based widget packs.")
        if write_to_log:
            self.write_log("StreamElements login status: not checked.")
        self.update_connection_flash_buttons()
        return False

    def is_streamelements_logged_in(self) -> bool:
        return self.refresh_stream_elements_login_status(write_to_log=False)

    def open_streamelements_login_window(self):
        try:
            status_path = get_streamelements_status_file()
            write_streamelements_login_status(
                "checking",
                message="Login window is open. Log into StreamElements, then leave the window open until SEUnpacker confirms the login."
            )
            self.refresh_stream_elements_login_status(write_to_log=False)

            login_url = "https://www.streamelements.com/dashboard/overlays"
            screen_width = max(900, int(self.root.winfo_screenwidth() * 0.52))
            screen_height = max(720, int(self.root.winfo_screenheight() * 0.82))

            if webview is None:
                self.write_log("Embedded browser support is not installed. Opening StreamElements login in a separate browser window.")
                self.open_url_in_separate_browser_window(login_url, screen_width, screen_height)
            else:
                if getattr(sys, "frozen", False):
                    exe_path = Path(sys.executable)
                    command = [
                        str(exe_path),
                        "--se-login",
                        login_url,
                        str(screen_width),
                        str(screen_height),
                        str(status_path),
                    ]
                else:
                    command = [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--se-login",
                        login_url,
                        str(screen_width),
                        str(screen_height),
                        str(status_path),
                    ]

                self.se_login_process = subprocess.Popen(command)
                self.write_log("Opened embedded StreamElements login window.")

            self.start_streamelements_login_poll()

        except Exception as exc:
            self.handle_error(exc)

    def start_streamelements_login_poll(self):
        if self.login_poll_active:
            return
        self.login_poll_active = True
        self.root.after(800, self.poll_streamelements_login_status)

    def poll_streamelements_login_status(self):
        logged_in = self.refresh_stream_elements_login_status(write_to_log=False)

        if logged_in:
            self.login_poll_active = False
            self.close_streamelements_login_window_if_possible()
            if self.waiting_for_login_then_import:
                self.waiting_for_login_then_import = False
                self.write_log("StreamElements login confirmed. Continuing URL widget import flow...")
                self.root.after(500, self.show_streamelements_import_assistant)
            return

        self.root.after(1000, self.poll_streamelements_login_status)

    def close_streamelements_login_window_if_possible(self):
        try:
            if self.se_login_process is not None and self.se_login_process.poll() is None:
                self.se_login_process.terminate()
                self.write_log("Closed embedded StreamElements login helper window.")
            self.se_login_process = None
        except Exception:
            pass

    def show_streamelements_import_assistant(self):
        try:
            self.ensure_current_pack_built()
            primary_url = normalize_user_url(self.current_pack_info.get("primary_share_url", ""))
            if not primary_url:
                raise RuntimeError("No StreamElements share/import URL was found in this pack.")

            win = Toplevel(self.root)
            win.title("StreamElements Import Assistant")
            win.geometry("760x520")
            win.minsize(700, 460)
            win.configure(bg=DARK_BG)
            win.transient(self.root)

            header = Frame(win, bg=HEADER_BG, height=78)
            header.pack(fill="x")
            header.pack_propagate(False)

            Label(
                header,
                text="StreamElements URL Widget Import",
                bg=HEADER_BG,
                fg=TEXT_FG,
                font=("Segoe UI", 18, "bold"),
            ).pack(anchor="w", padx=22, pady=(14, 0))

            Label(
                header,
                text="Import the overlay in StreamElements, then SEUnpacker will capture the copied browser-source URL from your clipboard.",
                bg=HEADER_BG,
                fg="#d1d5db",
                font=("Segoe UI", 10),
            ).pack(anchor="w", padx=24, pady=(2, 0))

            body = Frame(win, bg=DARK_BG)
            body.pack(fill="both", expand=True, padx=18, pady=18)

            panel = self.make_panel(body, "Detected Primary Import URL")
            url_row = Frame(panel, bg=PANEL_BG)
            url_row.pack(fill="x", padx=14, pady=(0, 14))

            url_var = StringVar(value=primary_url)
            url_entry = self.make_entry(url_row, url_var)
            url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=7)

            import_started = {"value": False}

            def open_import_url():
                if import_started["value"]:
                    return
                import_started["value"] = True
                self.write_log(f"Opening StreamElements import URL: {primary_url}")
                self.show_streamelements_copy_url_splash()
                self.open_url_inside_app_when_available(primary_url)
                start_clipboard_watch()

            BlueButton(url_row, text="Open Import Window", command=open_import_url).pack(side="left")

            steps_panel = self.make_panel(body, "What the user does")
            steps = Label(
                steps_panel,
                text=(
                    "1. Log into StreamElements if prompted.\n"
                    "2. Let StreamElements import the overlay.\n"
                    "3. In My Overlays, open the three-dot menu on the imported overlay and click Copy URL.\n"
                    "4. Return here. SEUnpacker will detect the copied URL and enable Finish Install."
                ),
                bg=PANEL_BG,
                fg=TEXT_FG,
                justify="left",
                font=("Segoe UI", 10),
            )
            steps.pack(anchor="w", padx=14, pady=(0, 14))

            captured_panel = self.make_panel(body, "Captured StreamElements Browser Source URL")
            captured_row = Frame(captured_panel, bg=PANEL_BG)
            captured_row.pack(fill="x", padx=14, pady=(0, 14))

            captured_var = StringVar(value="Waiting for copied StreamElements browser-source URL...")
            captured_entry = self.make_entry(captured_row, captured_var)
            captured_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=7)

            finish_button = BlueButton(captured_row, text="Install Captured URL", command=lambda: finish_from_clipboard())
            finish_button.pack(side="left")
            finish_button.configure(state="disabled", bg="#4b5563")

            status_label = Label(
                captured_panel,
                text="Clipboard watcher starts after you click Open Import.",
                bg=PANEL_BG,
                fg=MUTED_FG,
                justify="left",
                font=("Segoe UI", 9),
            )
            status_label.pack(anchor="w", padx=14, pady=(0, 14))

            found_url = {"value": ""}
            flash_state = {"count": 0}

            def flash_finish_button():
                if not win.winfo_exists():
                    return
                if flash_state["count"] >= 12:
                    finish_button.configure(bg=BLUE)
                    return
                flash_state["count"] += 1
                finish_button.configure(bg=YELLOW if flash_state["count"] % 2 else BLUE)
                win.after(250, flash_finish_button)

            def set_finish_enabled(enabled: bool):
                if enabled:
                    finish_button.configure(state="normal", bg=BLUE)
                else:
                    finish_button.configure(state="disabled", bg="#4b5563")

            def read_clipboard_text():
                try:
                    return normalize_user_url(self.root.clipboard_get())
                except Exception:
                    return ""

            def poll_clipboard():
                if not win.winfo_exists():
                    return

                text = read_clipboard_text()
                if text and not is_dashboard_share_url(text) and looks_like_browser_source_url(text):
                    if found_url["value"] != text:
                        found_url["value"] = text
                        captured_var.set(text)
                        status_label.configure(
                            text="Browser-source URL captured. Click the flashing install button to localize and install it into Firebot.",
                            fg=TEXT_FG,
                        )
                        set_finish_enabled(True)
                        self.close_streamelements_window_if_possible()
                        self.close_copy_url_splash_if_possible()
                        flash_state["count"] = 0
                        flash_finish_button()
                    win.after(1000, poll_clipboard)
                else:
                    win.after(1000, poll_clipboard)

            def start_clipboard_watch():
                status_label.configure(text="Watching clipboard for the StreamElements Copy URL...", fg=TEXT_FG)
                win.after(500, poll_clipboard)

            def finish_from_clipboard():
                try:
                    url = found_url["value"] or read_clipboard_text()
                    url = normalize_user_url(url)

                    if not url:
                        raise RuntimeError("No StreamElements browser-source URL has been captured yet.")
                    if is_dashboard_share_url(url):
                        raise RuntimeError("That is still the StreamElements share/import URL. Use the overlay three-dot menu and click Copy URL.")
                    if not looks_like_browser_source_url(url):
                        raise RuntimeError("The captured URL does not look like a StreamElements browser-source URL.")

                    self.stream_elements_overlay_url_var.set(url)
                    self.apply_pasted_streamelements_overlay_url_to_pack()

                    self.write_log("Creating Firebot overlay widget and preset from local widget resource...")
                    result = create_firebot_widget_and_preset_for_pack(self.current_pack_info)
                    self.write_log(f"Created overlay widget: {result['created_widget']}")
                    self.write_log(f"Created preset effect list: {result['created_preset']}")
                    self.log_widget_feeder_result(result)
                    self.write_log("Done. Reopen Firebot, then refresh OBS browser cache.")

                    messagebox.showinfo(
                        APP_NAME,
                        "StreamElements widget installed successfully.\n\nReopen Firebot, then refresh the OBS browser source cache."
                    )
                    self.close_copy_url_splash_if_possible()
                    win.destroy()

                except Exception as exc:
                    self.handle_error(exc)

            self.write_log("StreamElements import assistant opened.")
            win.after(700, open_import_url)

        except Exception as exc:
            self.handle_error(exc)

    def open_url_inside_app_when_available(self, url: str):
        """Open StreamElements in its own half-size helper window.

        pywebview must run on the main thread. Tkinter is already using the
        main thread, so SEUnpacker launches a tiny helper instance of itself.
        In that helper process, pywebview is running on that process main
        thread while the main SEUnpacker window stays responsive and can keep
        watching the clipboard for the copied StreamElements overlay URL.
        """
        screen_width = max(900, int(self.root.winfo_screenwidth() * 0.52))
        screen_height = max(720, int(self.root.winfo_screenheight() * 0.82))

        if webview is None:
            self.write_log("Embedded browser support is not installed. Opening StreamElements in a separate browser window.")
            self.open_url_in_separate_browser_window(url, screen_width, screen_height)
            return

        try:
            if getattr(sys, "frozen", False):
                command = [
                    sys.executable,
                    "--se-webview",
                    url,
                    str(screen_width),
                    str(screen_height),
                ]
            else:
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--se-webview",
                    url,
                    str(screen_width),
                    str(screen_height),
                ]

            self.se_webview_process = subprocess.Popen(command)
            self.write_log("Opened embedded StreamElements login/import window.")

        except Exception as exc:
            self.write_log(f"Embedded StreamElements window failed. Browser fallback used. Reason: {exc}")
            self.open_url_in_separate_browser_window(url, screen_width, screen_height)

    def open_url_in_separate_browser_window(self, url: str, width: int, height: int):
        if os.name == "nt":
            browser_candidates = [
                (os.environ.get("PROGRAMFILES(X86)", "") + r"\Microsoft\Edge\Application\msedge.exe"),
                (os.environ.get("PROGRAMFILES", "") + r"\Microsoft\Edge\Application\msedge.exe"),
                (os.environ.get("PROGRAMFILES", "") + r"\Google\Chrome\Application\chrome.exe"),
                (os.environ.get("PROGRAMFILES(X86)", "") + r"\Google\Chrome\Application\chrome.exe"),
            ]

            for browser_path in browser_candidates:
                if browser_path and Path(browser_path).exists():
                    try:
                        subprocess.Popen([
                            browser_path,
                            "--new-window",
                            f"--window-size={width},{height}",
                            "--window-position=80,80",
                            url,
                        ])
                        return
                    except Exception:
                        pass

        webbrowser.open_new(url)

    def close_streamelements_window_if_possible(self):
        try:
            if self.se_webview_window is not None:
                self.se_webview_window.destroy()
                self.se_webview_window = None
                self.write_log("Closed StreamElements import window.")
        except Exception:
            pass

        try:
            if self.se_webview_process is not None and self.se_webview_process.poll() is None:
                self.se_webview_process.terminate()
                self.se_webview_process = None
                self.write_log("Closed embedded StreamElements helper window.")
        except Exception:
            pass

    def analyze_selected_pack(self):
        try:
            zip_path = self.get_zip_path()
            self.write_log("")
            self.write_log("SEUnpacker is analyzing the pack...")

            analysis = analyze_zip(zip_path)

            self.write_log("Analysis complete:")
            self.write_log(f"Detected pack type: {analysis['pack_type']}")
            self.write_log(f"Images found: {len(analysis['images'])}")
            self.write_log(f"Audio found: {len(analysis['audio'])}")
            self.write_log(f"Video found: {len(analysis['video'])}")
            self.write_log(f"Shortcut URLs found: {len(analysis['shortcuts'])}")
            self.write_log(f"Widget files found: {len(analysis['widget_files'])}")
            self.write_log(f"Nested ZIPs found: {len(analysis['nested_zips'])}")
            self.write_log(f"Other files found: {len(analysis['other'])}")

            if analysis["widget_files"]:
                self.write_log("")
                self.write_log("Widget files:")
                for item in analysis["widget_files"]:
                    self.write_log(f"  - {item}")

            if analysis["images"]:
                self.write_log("")
                self.write_log("Images:")
                for item in analysis["images"]:
                    self.write_log(f"  - {item}")

            if analysis["nested_zips"]:
                self.write_log("")
                self.write_log("Nested ZIPs:")
                for item in analysis["nested_zips"]:
                    self.write_log(f"  - {item}")

            if analysis["pack_type"] == "stream_elements_widget":
                self.write_log("")
                self.write_log("This is a StreamElements widget pack.")
                primary_url = choose_primary_streamelements_share_url(analysis.get("shortcut_urls", []), safe_slug(zip_path.name))
                if primary_url:
                    self.write_log(f"Primary StreamElements import URL: {primary_url}")
                self.write_log("Use: Build -> Install Assets -> Create Widget / Preset.")
            else:
                self.write_log("")
                self.write_log("This is an alert asset pack.")
                self.write_log("Use: Build -> Install Assets -> Create Events.")

        except Exception as exc:
            self.handle_error(exc)

    def build_pack(self):
        try:
            zip_path = self.get_zip_path()
            output_path = self.get_output_path()

            self.write_log("")
            self.write_log("Building Firebot-ready package...")

            self.current_pack_info = build_firebot_pack(zip_path, output_path)

            self.write_log("Build complete.")
            self.write_log(f"Detected pack type: {self.current_pack_info['pack_type']}")
            self.write_log(f"Pack folder: {self.current_pack_info['pack_dir']}")
            self.write_log(f"HTML file: {self.current_pack_info['html_path']}")
            self.write_log(f"Setup notes: {self.current_pack_info['readme_path']}")

            if self.current_pack_info["pack_type"] == "stream_elements_widget":
                self.write_log("Generated persistent widget.html.")
                if is_url_only_stream_elements_widget(self.current_pack_info):
                    self.write_log(f"Primary StreamElements import URL: {self.current_pack_info.get('primary_share_url', '')}")
                    self.write_log("Paste the StreamElements Copy URL on the Widget / Preset page before creating the widget.")
            else:
                self.write_log("Generated alert.html.")

            messagebox.showinfo(
                APP_NAME,
                "Firebot-ready package generated successfully.",
            )

        except Exception as exc:
            self.handle_error(exc)

    def install_pack(self):
        try:
            running, reason = is_firebot_running()

            if running:
                raise RuntimeError(
                    "Firebot appears to be running.\n\n"
                    f"{reason}\n\n"
                    "Close Firebot completely before installing resources."
                )

            self.ensure_current_pack_built()

            self.write_log("")
            self.write_log("Installing assets to Firebot overlay resources...")

            target_dir = install_to_firebot_resources(self.current_pack_info)

            self.write_log(f"Installed assets to: {target_dir}")

            if self.current_pack_info["pack_type"] == "stream_elements_widget":
                next_step = "Next step: Create Widget / Preset."
            else:
                next_step = "Next step: Create Firebot Events."

            messagebox.showinfo(
                APP_NAME,
                f"Assets installed successfully:\n\n{target_dir}\n\n{next_step}"
            )

        except Exception as exc:
            self.handle_error(exc)

    def log_widget_feeder_result(self, result: dict):
        feeder = result.get("feeder_result") if isinstance(result, dict) else None
        if not feeder:
            return
        self.write_log(f"Backed up events.json to: {feeder['backup_path']}")
        self.write_log(f"Replaced old widget feeder events for this pack: {feeder['removed_count']}")
        self.write_log(f"Created widget feeder events: {len(feeder['created_events'])}")
        for event_name in feeder["created_events"]:
            self.write_log(f"  - {event_name}")

    def create_firebot_events(self):
        try:
            running, reason = is_firebot_running()

            if running:
                raise RuntimeError(
                    "Firebot appears to be running.\n\n"
                    f"{reason}\n\n"
                    "Close Firebot completely before creating events."
                )

            self.ensure_current_pack_built()

            self.write_log("")
            self.write_log("Creating Firebot Events...")

            result = create_firebot_events_for_pack(self.current_pack_info)

            self.write_log(f"Backed up events.json to: {result['backup_path']}")
            self.write_log(f"Removed old SEUnpacker events for this pack: {result['removed_count']}")

            self.write_log("Created Firebot Events:")
            for event_name in result["created_events"]:
                self.write_log(f"  - {event_name}")

            self.write_log("")
            self.write_log("Done. Reopen Firebot and check the Events tab.")

            messagebox.showinfo(
                APP_NAME,
                "Firebot Events created successfully.\n\n"
                "Reopen Firebot and check the Events tab."
            )

        except Exception as exc:
            self.handle_error(exc)

    def open_primary_streamelements_import_url(self):
        try:
            self.ensure_current_pack_built()

            primary_url = normalize_user_url(self.current_pack_info.get("primary_share_url", ""))

            if not primary_url:
                raise RuntimeError("No StreamElements share/import URL was found in this pack.")

            self.write_log("")
            self.write_log(f"Opening primary StreamElements import URL: {primary_url}")
            webbrowser.open(primary_url)

            messagebox.showinfo(
                APP_NAME,
                "StreamElements import URL opened.\n\n"
                "After it imports into StreamElements, go to My Overlays, use the three-dot menu, choose Copy URL, then paste that browser-source URL into SEUnpacker."
            )

        except Exception as exc:
            self.handle_error(exc)

    def clear_stream_elements_overlay_url(self):
        self.stream_elements_overlay_url_var.set("")
        self.write_log("Cleared pasted StreamElements browser-source URL.")

    def apply_pasted_streamelements_overlay_url_to_pack(self):
        if not self.current_pack_info or not is_url_only_stream_elements_widget(self.current_pack_info):
            return

        pasted_url = normalize_user_url(self.stream_elements_overlay_url_var.get())

        if not pasted_url:
            primary_url = normalize_user_url(self.current_pack_info.get("primary_share_url", ""))
            raise RuntimeError(
                "This is a StreamElements URL-only widget pack.\n\n"
                "Do this first:\n"
                "1. Click Open Primary SE Import URL.\n"
                "2. Import it into StreamElements.\n"
                "3. In StreamElements My Overlays, click the three-dot menu and choose Copy URL.\n"
                "4. Paste that copied browser-source URL into SEUnpacker.\n\n"
                f"Primary import URL:\n{primary_url}"
            )

        if is_dashboard_share_url(pasted_url):
            raise RuntimeError(
                "That looks like the StreamElements share/import URL, not the final browser-source Copy URL.\n\n"
                "Open the import link, import the overlay, then use StreamElements My Overlays -> three-dot menu -> Copy URL. Paste that copied URL here."
            )

        if not looks_like_browser_source_url(pasted_url):
            raise RuntimeError(
                "The pasted StreamElements URL does not look like a usable browser-source URL.\n\n"
                "Paste the URL from StreamElements My Overlays -> three-dot menu -> Copy URL."
            )

        self.current_pack_info["final_overlay_url"] = pasted_url

        self.write_log(f"Using captured StreamElements browser-source URL: {pasted_url}")

        widget_path = self.current_pack_info["pack_dir"] / "widget.html"

        if is_minimal_event_rotator_pack(self.current_pack_info):
            self.write_log("Minimal Event Rotator source profile detected.")
            self.write_log("Bypassing StreamElements shell capture and rebuilding from HTML/CSS/JS/Fields/Data source.")
            captured, capture_message = generate_minimal_event_rotator_local_widget(
                self.current_pack_info,
                log_func=self.write_log,
            )
            if captured and widget_path.exists():
                self.current_pack_info["captured_local_overlay"] = True
                self.write_log(capture_message)
                self.write_log(f"Rebuilt widget.html as a true local Firebot overlay: {widget_path}")
            else:
                self.current_pack_info["captured_local_overlay"] = False
                widget_html = generate_widget_html(self.current_pack_info)
                widget_path.write_text(widget_html, encoding="utf-8")
                self.write_log(f"Source rebuild failed, falling back to iframe wrapper. Reason: {capture_message}")
                self.write_log(f"Rebuilt widget.html with StreamElements iframe fallback: {widget_path}")
        else:
            captured, capture_message, _captured_html = capture_stream_elements_overlay_to_local(
                pasted_url,
                self.current_pack_info["pack_dir"],
                log_func=self.write_log,
            )

            if captured and widget_path.exists():
                self.current_pack_info["captured_local_overlay"] = True
                self.write_log(capture_message)
                self.write_log(f"Rebuilt widget.html as a localized Firebot overlay: {widget_path}")
            else:
                self.current_pack_info["captured_local_overlay"] = False
                widget_html = generate_widget_html(self.current_pack_info)
                widget_path.write_text(widget_html, encoding="utf-8")
                self.write_log(f"Local capture failed, falling back to iframe wrapper. Reason: {capture_message}")
                self.write_log(f"Rebuilt widget.html with StreamElements iframe fallback: {widget_path}")

        self.current_pack_info["widget_path"] = widget_path
        self.current_pack_info["html_path"] = widget_path

        valid, validation_errors = validate_local_widget_html(widget_path, self.current_pack_info)
        if not valid:
            self.current_pack_info["captured_local_overlay"] = False
            raise RuntimeError(
                "Local widget rebuild failed validation. SEUnpacker did not install this widget because it would be blank or StreamElements-dependent.\n\n"
                + "\n".join(f"- {error}" for error in validation_errors)
            )

        target_dir = sync_rebuilt_pack_to_firebot_resources(self.current_pack_info)
        installed_widget_path = target_dir / "widget.html"

        installed_valid, installed_validation_errors = validate_local_widget_html(installed_widget_path, self.current_pack_info)
        if not installed_valid:
            raise RuntimeError(
                "The rebuilt widget was valid in the output folder, but the Firebot resource copy failed validation.\n\n"
                + "\n".join(f"- {error}" for error in installed_validation_errors)
            )

        self.write_log(f"Validated local widget.html: {widget_path}")
        self.write_log(f"Synced rebuilt local widget to Firebot resources: {installed_widget_path}")

    def create_widget_and_preset(self):
        try:
            running, reason = is_firebot_running()

            if running:
                raise RuntimeError(
                    "Firebot appears to be running.\n\n"
                    f"{reason}\n\n"
                    "Close Firebot completely before creating widgets or presets."
                )

            self.ensure_current_pack_built()

            if self.current_pack_info["pack_type"] != "stream_elements_widget":
                selected_zip = self.get_zip_path()
                analysis = analyze_zip(selected_zip)
                if is_forced_url_widget_pack(
                    selected_zip,
                    analysis.get("shortcut_urls", []),
                    analysis.get("images", []),
                    analysis.get("audio", []),
                    analysis.get("video", []),
                ):
                    self.current_pack_info["pack_type"] = "stream_elements_widget"
                    self.current_pack_info["analysis"] = analysis
                    self.write_log("Force-corrected pack type to stream_elements_widget for URL widget pack.")
                else:
                    raise RuntimeError(
                        "This selected ZIP is not a StreamElements widget pack.\n\n"
                        "Use Create Events for alert packs."
                    )

            self.apply_pasted_streamelements_overlay_url_to_pack()

            self.write_log("")
            self.write_log("Installing widget assets first...")
            target_dir = install_to_firebot_resources(self.current_pack_info)
            self.write_log(f"Installed widget assets to: {target_dir}")

            self.write_log("")
            self.write_log("Creating Firebot overlay widget and preset effect list...")

            result = create_firebot_widget_and_preset_for_pack(self.current_pack_info)

            self.write_log(f"Backed up overlay-widgets.json to: {result['widgets_backup_path']}")
            self.write_log(f"Backed up preset-effect-lists.json to: {result['presets_backup_path']}")
            self.write_log(f"Replaced old SEUnpacker widgets for this same pack: {result['removed_widgets_count']}")
            self.write_log(f"Replaced old SEUnpacker presets for this same pack: {result['removed_presets_count']}")
            self.write_log(f"Created overlay widget: {result['created_widget']}")
            self.write_log(f"Created preset effect list: {result['created_preset']}")
            self.log_widget_feeder_result(result)
            self.write_log("")
            self.write_log("Done. Reopen Firebot and check Overlay Widgets and Preset Effect Lists.")

            messagebox.showinfo(
                APP_NAME,
                "Overlay widget and preset effect list created successfully.\n\n"
                "Reopen Firebot and check Overlay Widgets and Preset Effect Lists."
            )

        except Exception as exc:
            self.handle_error(exc)

    def open_output_folder(self):
        try:
            output_path = self.get_output_path()
            os.startfile(output_path)
        except Exception as exc:
            self.handle_error(exc)

    def open_firebot_resources_folder(self):
        try:
            path = get_appdata_firebot_resources()
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(path)
        except Exception as exc:
            self.handle_error(exc)

    def open_firebot_events_folder(self):
        try:
            events_path = get_firebot_events_json_path()
            events_path.parent.mkdir(parents=True, exist_ok=True)
            os.startfile(events_path.parent)
        except Exception as exc:
            self.handle_error(exc)

    def open_firebot_profile_folder(self):
        try:
            path = get_firebot_main_profile_path()
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(path)
        except Exception as exc:
            self.handle_error(exc)

    def open_readme(self):
        try:
            self.ensure_current_pack_built()

            readme_path = self.current_pack_info.get("readme_path")

            if not readme_path or not Path(readme_path).exists():
                raise RuntimeError("README.txt was not found. Build the pack again.")

            os.startfile(readme_path)

        except Exception as exc:
            self.handle_error(exc)

    def handle_error(self, exc: Exception):
        error_text = str(exc)

        if "Access is denied" in error_text or "WinError 5" in error_text:
            error_text += (
                "\n\nThis is usually caused by OneDrive or Windows locking the output folder.\n"
                "Try changing the Output Folder to:\n"
                r"%LOCALAPPDATA%\SEUnpacker\Output"
            )

        messagebox.showerror(APP_NAME, error_text)
        self.write_log(f"ERROR: {error_text}")


def get_webview_current_url(window) -> str:
    try:
        url = window.get_current_url()
        if url:
            return str(url)
    except Exception:
        pass

    try:
        url = window.evaluate_js("window.location.href")
        if url:
            return str(url)
    except Exception:
        pass

    return ""


def start_pywebview_with_persistent_storage(helper_webview, callback=None):
    """Start pywebview with a reusable storage folder when supported."""
    kwargs = {}
    try:
        import inspect
        signature = inspect.signature(helper_webview.start)
        if "private_mode" in signature.parameters:
            kwargs["private_mode"] = False
        if "storage_path" in signature.parameters:
            kwargs["storage_path"] = str(get_streamelements_webview_storage_folder())
    except Exception:
        pass

    if callback is None:
        helper_webview.start(**kwargs)
    else:
        helper_webview.start(callback, **kwargs)


def run_streamelements_webview_helper():
    """Run the StreamElements webview in a separate process.

    This avoids pywebview's main-thread restriction while keeping the main
    SEUnpacker Tkinter app responsive.
    """
    try:
        marker_index = sys.argv.index("--se-webview")
        url = sys.argv[marker_index + 1]
    except Exception:
        return 2

    try:
        width = int(sys.argv[marker_index + 2])
        height = int(sys.argv[marker_index + 3])
    except Exception:
        width = 900
        height = 720

    try:
        import webview as helper_webview
    except Exception:
        return 3

    helper_webview.create_window(
        "SEUnpacker StreamElements Login / Import",
        url,
        width=width,
        height=height,
        resizable=True,
        confirm_close=False,
    )
    start_pywebview_with_persistent_storage(helper_webview)
    return 0



def run_streamelements_rendered_capture_helper():
    """Load a StreamElements browser-source URL and save the rendered DOM."""
    try:
        marker_index = sys.argv.index("--se-capture-rendered")
        url = sys.argv[marker_index + 1]
        width = int(sys.argv[marker_index + 2])
        height = int(sys.argv[marker_index + 3])
        output_path = Path(sys.argv[marker_index + 4])
        wait_seconds = int(sys.argv[marker_index + 5])
    except Exception:
        return 2

    def write_payload(success: bool, message: str, html: str = "", current_url: str = ""):
        payload = {
            "success": success,
            "message": message,
            "html": html,
            "url": current_url,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            pass

    try:
        import webview as helper_webview
    except Exception as exc:
        write_payload(False, f"Embedded browser support failed to load: {exc}")
        return 3

    window = helper_webview.create_window(
        "SEUnpacker StreamElements Capture",
        url,
        width=width,
        height=height,
        resizable=True,
        confirm_close=False,
    )

    def capture_after_load():
        try:
            time.sleep(max(3, wait_seconds))
            # Give lazy widgets one more short chance to populate DOM.
            html = ""
            current_url = ""
            for _ in range(4):
                current_url = get_webview_current_url(window)
                html = window.evaluate_js("document.documentElement ? document.documentElement.outerHTML : ''") or ""
                if html and len(str(html)) > 500:
                    break
                time.sleep(1)
            write_payload(True, "Captured rendered StreamElements DOM from embedded browser.", str(html), current_url)
        except Exception as exc:
            write_payload(False, f"Could not capture rendered DOM: {exc}")
        finally:
            try:
                window.destroy()
            except Exception:
                pass

    start_pywebview_with_persistent_storage(helper_webview, capture_after_load)
    return 0

def run_streamelements_login_helper():
    """Open StreamElements and mark the login status once dashboard access is detected."""
    try:
        marker_index = sys.argv.index("--se-login")
        url = sys.argv[marker_index + 1]
    except Exception:
        return 2

    try:
        width = int(sys.argv[marker_index + 2])
        height = int(sys.argv[marker_index + 3])
        status_path = Path(sys.argv[marker_index + 4])
    except Exception:
        width = 900
        height = 720
        status_path = get_streamelements_status_file()

    def write_status(status: str, current_url: str = "", message: str = ""):
        payload = {
            "status": status,
            "url": current_url,
            "message": message,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    write_status("checking", message="Waiting for StreamElements login.")

    try:
        import webview as helper_webview
    except Exception:
        write_status("login_required", message="Embedded browser support failed to load.")
        return 3

    window = helper_webview.create_window(
        "SEUnpacker StreamElements Login",
        url,
        width=width,
        height=height,
        resizable=True,
        confirm_close=False,
    )

    def monitor_login():
        last_url = ""
        for _ in range(900):
            current_url = get_webview_current_url(window)
            if current_url and current_url != last_url:
                last_url = current_url
                if looks_like_streamelements_logged_in_url(current_url):
                    write_status("logged_in", current_url, "StreamElements dashboard access confirmed.")
                    try:
                        window.destroy()
                    except Exception:
                        pass
                    return
                if looks_like_streamelements_login_url(current_url):
                    write_status("login_required", current_url, "StreamElements login page is open.")
            time.sleep(1)

        write_status("unknown", last_url, "Login could not be confirmed automatically.")

    start_pywebview_with_persistent_storage(helper_webview, monitor_login)
    return 0

def main():
    root = Tk()
    SEUnpackerApp(root)
    root.mainloop()


if __name__ == "__main__":
    if "--se-webview" in sys.argv:
        raise SystemExit(run_streamelements_webview_helper())
    if "--se-login" in sys.argv:
        raise SystemExit(run_streamelements_login_helper())
    if "--se-capture-rendered" in sys.argv:
        raise SystemExit(run_streamelements_rendered_capture_helper())
    main()
