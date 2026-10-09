#!/usr/bin/env python3
"""Validate the opt-in auth proxy against a fake upstream with no host ports."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "nginx:1.27-alpine"

FAKE_UPSTREAM = """
server {
    listen 18081;
    location = /login {
        default_type application/json;
        return 200 '{"api_token":"fixture-api-token","account":{"id":1}}';
    }
    location = /remember {
        default_type application/json;
        return 200 '{"api_token":"fixture-api-token"}';
    }
    location = /game-token {
        if ($http_authorization != "Bearer fixture-api-token") { return 401; }
        default_type application/json;
        return 200 '{"game_token":"fixture-game-token"}';
    }
    location / { return 500; }
}
"""

CHECK = """set -eu
nginx -t
nginx
trap 'nginx -s quit' EXIT
wget --no-check-certificate -q -O /tmp/login --post-data='{}' https://127.0.0.1:8443/login
grep -q 'fixture-api-token' /tmp/login
wget --no-check-certificate -q -O /tmp/game --header='Authorization: Bearer fixture-api-token' --post-data='{}' https://127.0.0.1:8443/game-token
grep -q 'fixture-game-token' /tmp/game
wget --no-check-certificate -q -O /tmp/remember --post-data='{}' https://127.0.0.1:8443/remember
grep -q 'fixture-api-token' /tmp/remember
for path in health register scheduler/tasks characters; do
    wget --no-check-certificate -S -O /dev/null --post-data='{}' "https://127.0.0.1:8443/$path" > /tmp/result 2>&1 && exit 1
    grep -q '404 Not Found' /tmp/result
done
wget --no-check-certificate -S -O /dev/null https://127.0.0.1:8443/login > /tmp/result 2>&1 && exit 1
grep -q '403 Forbidden' /tmp/result
wget --no-check-certificate -S -O /dev/null --post-data='{}' https://127.0.0.1:8443/game-token > /tmp/result 2>&1 && exit 1
grep -q '401 Unauthorized' /tmp/result
echo 'PASS: login, remember, game-token authorization forwarded; other routes and GET blocked'
"""


def main():
    with tempfile.TemporaryDirectory(prefix="wakemu-auth-proxy-smoke-") as directory:
        temporary = Path(directory)
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-keyout",
                str(temporary / "key"),
                "-out",
                str(temporary / "cert"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        config = temporary / "nginx.conf"
        config.write_text(
            (ROOT / "server/remote-auth/nginx.conf").read_text() + FAKE_UPSTREAM
        )
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--add-host",
                "world:127.0.0.1",
                "-v",
                str(config) + ":/etc/nginx/conf.d/default.conf:ro",
                "-v",
                str(temporary / "cert") + ":/etc/nginx/remote.crt:ro",
                "-v",
                str(temporary / "key") + ":/etc/nginx/remote.key:ro",
                IMAGE,
                "sh",
                "-ec",
                CHECK,
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
