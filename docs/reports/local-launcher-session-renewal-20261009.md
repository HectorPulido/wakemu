# Local launcher session renewal

The local bridge previously read `login-session.json` once at startup. After its API token expired, a game-token request returned401; the HTTP exception escaped the RPC handler and silently closed the launcher connection. Replacing the login file from another login dialog did not refresh the cached token.

`client-tools/runtime/local_launcher_auth.py` now reads the session file on each game-token RPC. On401 it renews using the profile's revocable `remember.json` token, validates account identity, atomically replaces the login file with mode0600, and retries once. It never reads or stores a password. Missing/revoked remember access and service failures produce sanitized structured RPC errors. Existing bridge game/session authentication remains unchanged. The remote drop-in bridge is outside this local fix.

Validation: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_local_launcher_auth` passed5/5. Mocked coverage includes expiry+renewal, file reread, absent/revoked token preservation, foreign-account rejection, and an actual socket RPC error followed by a successful RPC on the same connection.

One authorized live helper call confirmed the current local login file already obtained a game token and had mode0600; no renewal was necessary at that instant. No token was printed. No bridge/client relaunch occurred. An already running Python bridge retains its previously loaded implementation until its process is replaced; disk changes alone do not hot-reload that process.
