#!/usr/bin/env python3
"""Obtain a real Wakfu game token through the API shipped with the client."""
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".runtime"
BASE = "https://haapi.ankama.com/json/Ankama/v5/"


def save_private(name, data):
    fd = os.open(RUNTIME / name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as out:
        json.dump(data, out)


def request(endpoint, params, key=None, post=False):
    headers = {"Accept": "application/json"}
    if key:
        headers["APIKEY"] = key
    encoded = urllib.parse.urlencode(params).encode()
    url = BASE + endpoint
    if post:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    else:
        url += "?" + encoded.decode()
    req = urllib.request.Request(url, data=encoded if post else None, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def main():
    credentials = json.loads((RUNTIME / "credentials.json").read_text())
    try:
        result = request(
            "Api/CreateApiKey",
            {
                "login": credentials["login"],
                "password": credentials["password"],
                "game_id": 102,
                "long_life_token": "false",
                "lang": "es",
            },
            post=True,
        )
        if not isinstance(result, dict) or not result.get("key"):
            raise ValueError("Response does not contain an API key.")
        save_private("api-key.json", result)
        print("API key obtained; value omitted.")
        token = request("Account/CreateToken", {"game": 3}, key=result["key"])
        if not isinstance(token, dict) or not token.get("token"):
            raise ValueError("Response does not contain a game token.")
        save_private("game-token.json", token)
        print("Wakfu token obtained; value omitted.")
        return 0
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            data = json.loads(raw)
            message = str(
                data.get("message", data.get("reason", "Error without message"))
            )
        except (ValueError, AttributeError):
            message = "Response does not contain a JSON error."
        for secret in credentials.values():
            message = message.replace(secret, "[REDACTED]")
        save_private("auth-error.json", {"http_status": error.code, "message": message})
        print(f"Authentication rejected: HTTP {error.code}: {message[:400]}")
        return 1
    except (OSError, ValueError) as error:
        print(f"Token could not be obtained: {type(error).__name__}.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
