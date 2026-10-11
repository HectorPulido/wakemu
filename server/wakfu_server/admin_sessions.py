"""Bounded operator sessions that survive administration service restarts."""
import hashlib
import threading
import time

SESSION_SECONDS = 8 * 3600
SESSION_LIMIT = 100


class SessionCapacity(ValueError):
    """The operator already has the maximum number of active sessions."""


class MemoryAdminSessions:
    """Isolated HTTP test services have no backing database."""

    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()

    def create(self, token, username, csrf_token):
        with self.lock:
            now = time.time()
            self.sessions = {
                key: value
                for key, value in self.sessions.items()
                if value["expires"] > now
            }
            if len(self.sessions) >= SESSION_LIMIT:
                raise SessionCapacity("Too many administrator sessions")
            session = dict(
                username=username, csrf_token=csrf_token, expires=now + SESSION_SECONDS
            )
            self.sessions[token] = session
            return dict(session)

    def get(self, token):
        with self.lock:
            session = self.sessions.get(token)
            if session is None or session["expires"] <= time.time():
                self.sessions.pop(token, None)
                return None
            return dict(session)

    def revoke(self, token):
        with self.lock:
            self.sessions.pop(token, None)


class PostgresAdminSessions:
    def __init__(self, store, credential_revision):
        self.store = store
        self.credential_revision = credential_revision

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, token, username, csrf_token):
        with self.store.connection() as db:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("admin_sessions:" + username,),
            )
            db.execute(
                "DELETE FROM admin_panel_sessions WHERE expires_at <= CURRENT_TIMESTAMP "
                "OR (username=%s AND credential_revision<>%s)",
                (username, self.credential_revision),
            )
            count = db.execute(
                "SELECT count(*) AS n FROM admin_panel_sessions WHERE username=%s",
                (username,),
            ).fetchone()["n"]
            if count >= SESSION_LIMIT:
                raise SessionCapacity("Too many administrator sessions")
            db.execute(
                "INSERT INTO admin_panel_sessions(token_sha256,username,csrf_token,credential_revision,expires_at) "
                "VALUES(%s,%s,%s,%s,CURRENT_TIMESTAMP + interval '8 hours')",
                (
                    self.token_hash(token),
                    username,
                    csrf_token,
                    self.credential_revision,
                ),
            )
        return dict(username=username, csrf_token=csrf_token)

    def get(self, token):
        if not isinstance(token, str) or not 1 <= len(token) <= 128:
            return None
        with self.store.connection() as db:
            row = db.execute(
                "SELECT username,csrf_token FROM admin_panel_sessions "
                "WHERE token_sha256=%s AND credential_revision=%s AND expires_at>CURRENT_TIMESTAMP",
                (self.token_hash(token), self.credential_revision),
            ).fetchone()
        return None if row is None else dict(row)

    def revoke(self, token):
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM admin_panel_sessions WHERE token_sha256=%s",
                (self.token_hash(token),),
            )
