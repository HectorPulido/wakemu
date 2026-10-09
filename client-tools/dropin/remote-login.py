#!/usr/bin/env python3
"""Obtain a private launcher session through the configured HTTPS login."""
import getpass
import json
import os
from pathlib import Path
import urllib.request
from urllib.parse import urlsplit
from portable_config import settings


def main():
    config = settings()
    if urlsplit(config["api_url"]).scheme != "https":
        raise ValueError(
            "Remote login requires HTTPS with a trusted server certificate"
        )
    username = input("Usuario: ")
    password = getpass.getpass("Contraseña: ")
    request = urllib.request.Request(
        config["api_url"] + "/login",
        data=json.dumps(
            {"username": username, "password": password, "remember": False}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    # Standard TLS verification stays enabled; no insecure certificate bypass.
    with urllib.request.urlopen(request, timeout=15) as response:
        session = json.load(response)
    if (
        not isinstance(session, dict)
        or not isinstance(session.get("api_token"), str)
        or not session["api_token"].strip()
    ):
        raise ValueError("Login did not return a launcher session")
    target = config["runtime_root"] / "remote-login-session.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(session, output)
    print("Sesión guardada en " + str(target))


if __name__ == "__main__":
    main()
