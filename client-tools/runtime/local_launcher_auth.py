"""Revocable-token renewal for the local launcher session file."""
import json
import os
from pathlib import Path
import tempfile
import threading
import urllib.error
import urllib.request


class LauncherAuthenticationError(ValueError):
    """Safe RPC error: never includes credentials or HTTP response bodies."""


class LauncherAuthentication:
    def __init__(self, login_file, api_url="http://127.0.0.1:18081", opener=None):
        self.login_file = Path(login_file)
        self.api_url = api_url.rstrip("/")
        self.opener = opener or urllib.request.urlopen
        self.lock = threading.Lock()

    def _login(self):
        try:
            login = json.loads(self.login_file.read_text())
            token = login["api_token"]
            if not isinstance(token, str) or not token:
                raise ValueError()
            return login
        except (OSError, ValueError, KeyError, TypeError):
            raise LauncherAuthenticationError(
                "Local login session unavailable; sign in again"
            ) from None

    def _request(self, route, body, token=None):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(
            self.api_url + route, data=json.dumps(body).encode(), headers=headers
        )
        with self.opener(request, timeout=5) as response:
            return json.load(response)

    def _renew(self, previous):
        try:
            remembered = json.loads(
                self.login_file.with_name("remember.json").read_text()
            )
            token = remembered["token"]
            if not isinstance(token, str) or not token:
                raise ValueError()
        except (OSError, ValueError, KeyError, TypeError):
            raise LauncherAuthenticationError(
                "Local login expired; no remembered access; sign in again"
            ) from None
        try:
            renewed = self._request("/remember", {"remember_token": token})
            if (
                not isinstance(renewed, dict)
                or not isinstance(renewed.get("api_token"), str)
                or not renewed["api_token"]
            ):
                raise ValueError()
            previous_id = previous.get("account", {}).get("id")
            if (
                previous_id is not None
                and renewed.get("account", {}).get("id") != previous_id
            ):
                raise ValueError()
            self._write(renewed)
            return renewed
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
            raise LauncherAuthenticationError(
                "Remembered local access unavailable or revoked; sign in again"
            ) from None

    def _write(self, login):
        staged = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self.login_file.parent, delete=False
            ) as output:
                staged = Path(output.name)
                os.fchmod(output.fileno(), 0o600)
                json.dump(login, output)
                output.flush()
                os.fsync(output.fileno())
            staged.replace(self.login_file)
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    def game_token(self):
        # Serialize renewal, but reread the file on every call so another login
        # dialog can replace the session without restarting this bridge.
        with self.lock:
            login = self._login()
            try:
                result = self._request("/game-token", {}, login["api_token"])
            except urllib.error.HTTPError as error:
                if error.code != 401:
                    raise LauncherAuthenticationError(
                        "Local game-token service rejected the request"
                    ) from None
                login = self._renew(login)
                try:
                    result = self._request("/game-token", {}, login["api_token"])
                except urllib.error.URLError:
                    raise LauncherAuthenticationError(
                        "Renewed local session could not obtain a game token"
                    ) from None
            except urllib.error.URLError:
                raise LauncherAuthenticationError(
                    "Local authentication service unavailable"
                ) from None
            try:
                token = result["game_token"]
                if not isinstance(token, str) or not token:
                    raise ValueError()
                return token
            except (ValueError, KeyError, TypeError):
                raise LauncherAuthenticationError(
                    "Invalid local game-token response"
                ) from None
