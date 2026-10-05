"""SQLite persistence with account isolation and generation-safe session leases."""
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from protocol_codec import APPEARANCE_FIELDS


class Store:
    def __init__(self, path, clock=time.time, *, max_characters=None):
        self.path = str(path)
        self.clock = clock
        self.max_characters = (
            int(os.environ.get("WAKFU_MAX_CHARACTERS", "5"))
            if max_characters is None
            else max_characters
        )
        if type(self.max_characters) is not int or not 1 <= self.max_characters <= 127:
            raise ValueError("Invalid character selection capacity")
        self.build_journal = None
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    salt BLOB NOT NULL, password_hash BLOB NOT NULL,
                    created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    breed INTEGER NOT NULL, sex INTEGER NOT NULL,
                    face INTEGER NOT NULL, hair INTEGER NOT NULL,
                    colors TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 1,
                    hp INTEGER NOT NULL DEFAULT 50, max_hp INTEGER NOT NULL DEFAULT 50,
                    map_id INTEGER NOT NULL DEFAULT 1134,
                    instance_id INTEGER NOT NULL DEFAULT 0,
                    x INTEGER NOT NULL DEFAULT -12, y INTEGER NOT NULL DEFAULT -8,
                    z INTEGER NOT NULL DEFAULT -1,
                    created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    account_id INTEGER PRIMARY KEY REFERENCES accounts(id),
                    generation TEXT NOT NULL UNIQUE, expires_at REAL NOT NULL,
                    character_id INTEGER REFERENCES characters(id));
                CREATE TABLE IF NOT EXISTS tokens (
                    digest TEXT PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
                    kind TEXT NOT NULL, expires_at REAL NOT NULL,
                    generation TEXT, realm_id INTEGER);
                CREATE INDEX IF NOT EXISTS tokens_expiry ON tokens(expires_at);
                CREATE INDEX IF NOT EXISTS characters_account ON characters(account_id);
                CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS character_builds (
                    character_id INTEGER NOT NULL REFERENCES characters(id),
                    build_index INTEGER NOT NULL,
                    sheet BLOB NOT NULL, equipment BLOB NOT NULL,
                    deck BLOB NOT NULL, aptitudes BLOB NOT NULL,
                    PRIMARY KEY(character_id, build_index));
                INSERT OR IGNORE INTO settings VALUES ('schema_version','1');
            """
            )
            columns = {
                row["name"] for row in db.execute("PRAGMA table_info(characters)")
            }
            if "appearance" not in columns:
                db.execute(
                    "ALTER TABLE characters ADD COLUMN appearance TEXT NOT NULL DEFAULT '{}'"
                )
            from wakfu_server.haven_bag_store import schema

            schema(db)
            from wakfu_server.tutorials import schema as tutorial_schema

            tutorial_schema(db)
            db.execute("UPDATE settings SET value='5' WHERE name='schema_version'")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def password_hash(password, salt):
        return hashlib.scrypt(
            password.encode(), salt=salt, n=16384, r=8, p=1, maxmem=64 * 1024 * 1024
        )

    def register(self, username, password):
        username = username.strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,32}", username):
            raise ValueError("Usuario: 3–32 letras, números, guion o guion bajo.")
        if not 8 <= len(password) <= 256:
            raise ValueError("Contraseña: 8–256 caracteres.")
        salt = secrets.token_bytes(16)
        hashed = self.password_hash(password, salt)
        with self.connection() as db:
            try:
                result = db.execute(
                    "INSERT INTO accounts(username,salt,password_hash,created_at) VALUES(?,?,?,?)",
                    (username, salt, hashed, self.clock()),
                )
            except sqlite3.IntegrityError:
                raise ValueError("Ese usuario ya existe.") from None
            return {"id": result.lastrowid, "username": username}

    def authenticate(self, username, password):
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM accounts WHERE username=?", (username.strip(),)
            ).fetchone()
        # Missing users also perform the expensive hash.
        salt = row["salt"] if row else bytes(16)
        candidate = self.password_hash(password, salt)
        if row is None or not hmac.compare_digest(candidate, row["password_hash"]):
            raise ValueError("Usuario o contraseña incorrectos.")
        return {"id": row["id"], "username": row["username"]}

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def issue_token(self, account_id, kind, ttl=300, generation=None, realm_id=None):
        if kind not in {"game", "remember", "api", "ticket"}:
            raise ValueError("Invalid token kind")
        token = secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute("DELETE FROM tokens WHERE expires_at<=?", (self.clock(),))
            db.execute(
                "INSERT INTO tokens VALUES(?,?,?,?,?,?)",
                (
                    self.digest(token),
                    account_id,
                    kind,
                    self.clock() + ttl,
                    generation,
                    realm_id,
                ),
            )
        return token

    def token(self, token, kind, consume=False):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT t.*,a.username FROM tokens t JOIN accounts a ON a.id=t.account_id "
                "WHERE digest=? AND kind=? AND expires_at>?",
                (self.digest(token), kind, self.clock()),
            ).fetchone()
            if row is None:
                raise ValueError("Acceso inválido o caducado.")
            if consume:
                db.execute("DELETE FROM tokens WHERE digest=?", (row["digest"],))
            return dict(row)

    def revoke_token(self, token):
        with self.connection() as db:
            db.execute("DELETE FROM tokens WHERE digest=?", (self.digest(token),))

    def begin_session(self, account_id, ttl=60):
        generation = secrets.token_hex(16)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO sessions(account_id,generation,expires_at) VALUES(?,?,?) "
                "ON CONFLICT(account_id) DO UPDATE SET generation=excluded.generation, "
                "expires_at=excluded.expires_at,character_id=NULL",
                (account_id, generation, self.clock() + ttl),
            )
            db.execute(
                "DELETE FROM tokens WHERE account_id=? AND kind='ticket'", (account_id,)
            )
        return generation

    def current_session(self, account_id, generation):
        with self.connection() as db:
            return (
                db.execute(
                    "SELECT 1 FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
                    (account_id, generation, self.clock()),
                ).fetchone()
                is not None
            )

    def heartbeat(self, account_id, generation, ttl=60):
        with self.connection() as db:
            result = db.execute(
                "UPDATE sessions SET expires_at=? WHERE account_id=? AND generation=? AND expires_at>?",
                (self.clock() + ttl, account_id, generation, self.clock()),
            )
            return result.rowcount == 1

    def end_session(self, account_id, generation):
        # A late finally from an old socket must not delete the replacement session.
        with self.connection() as db:
            db.execute(
                "DELETE FROM sessions WHERE account_id=? AND generation=?",
                (account_id, generation),
            )
            db.execute(
                "DELETE FROM tokens WHERE account_id=? AND generation=? AND kind='ticket'",
                (account_id, generation),
            )

    def create_character(
        self,
        account_id,
        name,
        breed=15,
        sex=0,
        face=0,
        hair=0,
        colors=None,
        appearance=None,
    ):
        if appearance is not None:
            if not isinstance(appearance, dict) or any(
                key not in APPEARANCE_FIELDS
                or type(value) is not int
                or not -(1 << 31) <= value < (1 << 31)
                for key, value in appearance.items()
            ):
                raise ValueError("Apariencia protobuf inválida.")
            appearance = dict(appearance)
            sex = appearance.get("sex", sex)
            face = appearance.get("faceIndex", face)
            hair = appearance.get("clothIndex", hair)
        name = name.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z -]{2,23}", name):
            raise ValueError("Nombre: 3–24 letras, espacios o guiones.")
        from wakfu_server.breed_resources import playable_breeds

        if (
            type(breed) is not int
            or breed not in playable_breeds()
            or sex not in (0, 1)
            or face not in range(32)
            or hair not in range(32)
        ):
            raise ValueError("Apariencia inválida.")
        colors = colors if colors is not None else [0xFFFFFF] * 3
        if len(colors) != 3 or any(
            type(c) is not int or not 0 <= c <= 0xFFFFFF for c in colors
        ):
            raise ValueError("Se requieren tres colores RGB.")
        if appearance is None:
            appearance = dict(
                zip(APPEARANCE_FIELDS[:3], (c - (1 << 24) for c in colors))
            )
            appearance.update(sex=sex, faceIndex=face, clothIndex=hair)
        else:
            appearance.setdefault("sex", sex)
            appearance.setdefault("faceIndex", face)
            appearance.setdefault("clothIndex", hair)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute(
                    "SELECT COUNT(*) FROM characters WHERE account_id=?", (account_id,)
                ).fetchone()[0]
                >= self.max_characters
            ):
                raise ValueError(
                    "Máximo cinco personajes por cuenta."
                    if self.max_characters == 5
                    else f"Máximo {self.max_characters} personajes por cuenta."
                )
            try:
                result = db.execute(
                    "INSERT INTO characters(account_id,name,breed,sex,face,hair,colors,created_at,appearance) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        account_id,
                        name,
                        breed,
                        sex,
                        face,
                        hair,
                        json.dumps(colors),
                        self.clock(),
                        json.dumps(appearance),
                    ),
                )
            except sqlite3.IntegrityError:
                raise ValueError(
                    "Ese nombre ya existe o la cuenta es inválida."
                ) from None
            return self.character(account_id, result.lastrowid, db)

    def character(self, account_id, character_id, db=None):
        if db is None:
            with self.connection() as connection:
                return self.character(account_id, character_id, connection)
        row = db.execute(
            "SELECT * FROM characters WHERE account_id=? AND id=?",
            (account_id, character_id),
        ).fetchone()
        if row is None:
            raise ValueError("Personaje no encontrado.")
        result = dict(row)
        from wakfu_server.combat_rewards import load as load_progression

        result.update(load_progression(db, result))
        from wakfu_server.haven_bag_store import load

        result["haven_bag"] = load(db, character_id)
        from wakfu_server.inventory import load as load_inventory

        result["inventory_containers"] = load_inventory(db, character_id)
        from wakfu_server.inventory_items import load as load_items

        result["inventory_items"] = load_items(db, character_id)
        result["colors"] = json.loads(result["colors"])
        result["appearance"] = json.loads(result["appearance"])
        result["builds"] = {
            entry["build_index"]: {
                key: entry[key].hex()
                for key in ("sheet", "equipment", "deck", "aptitudes")
            }
            for entry in db.execute(
                "SELECT * FROM character_builds WHERE character_id=?", (character_id,)
            )
        }
        if not result["appearance"]:
            result["appearance"] = dict(
                zip(APPEARANCE_FIELDS[:3], (c - (1 << 24) for c in result["colors"]))
            )
            result["appearance"].update(
                sex=result["sex"], faceIndex=result["face"], clothIndex=result["hair"]
            )
        if self.build_journal is not None:
            result = self.build_journal.overlay(result, db)
        return result

    def characters(self, account_id):
        with self.connection() as db:
            return [
                self.character(account_id, row["id"], db)
                for row in db.execute(
                    "SELECT id FROM characters WHERE account_id=? ORDER BY id",
                    (account_id,),
                )
            ]

    def clear_character(self, account_id, generation):
        with self.connection() as db:
            result = db.execute(
                "UPDATE sessions SET character_id=NULL WHERE account_id=? AND generation=? AND expires_at>?",
                (account_id, generation, self.clock()),
            )
            if result.rowcount != 1:
                raise ValueError("Sesión sustituida o caducada.")

    def select_character(self, account_id, generation, character_id):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            character = self.character(account_id, character_id, db)
            result = db.execute(
                "UPDATE sessions SET character_id=? WHERE account_id=? AND generation=? AND expires_at>?",
                (character_id, account_id, generation, self.clock()),
            )
            if result.rowcount != 1:
                raise ValueError("Sesión sustituida o caducada.")
            return character

    def move(self, account_id, generation, character_id, start, end):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
                (account_id, generation, self.clock()),
            ).fetchone()
            if session is None or session["character_id"] != character_id:
                raise ValueError("Sesión o personaje inválidos.")
            character = self.character(account_id, character_id, db)
            if any(character[k] != start[k] for k in ("x", "y", "z")):
                raise ValueError("Posición de origen desincronizada.")
            db.execute(
                "UPDATE characters SET x=?,y=?,z=? WHERE id=?",
                (end["x"], end["y"], end["z"], character_id),
            )
            return self.character(account_id, character_id, db)

    def save_build(self, account_id, generation, character_id, build_index, blobs):
        if self.build_journal is not None:
            return self.build_journal.save(
                account_id, generation, character_id, build_index, blobs
            )
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
                (account_id, generation, self.clock()),
            ).fetchone()
            if session is None or session["character_id"] != character_id:
                raise ValueError("Sesión o personaje inválidos.")
            character = self.character(account_id, character_id, db)
            from wakfu_server.builds import validate

            validate(character, build_index, blobs)
            previous = character["builds"].get(build_index, {})
            values = [
                blobs[key] or bytes.fromhex(previous.get(key, ""))
                for key in ("sheet", "equipment", "deck", "aptitudes")
            ]
            db.execute(
                "INSERT INTO character_builds VALUES(?,?,?,?,?,?) ON CONFLICT(character_id,build_index) DO UPDATE SET "
                "sheet=excluded.sheet,equipment=excluded.equipment,deck=excluded.deck,aptitudes=excluded.aptitudes",
                (character_id, build_index, *values),
            )
            updated = self.character(account_id, character_id, db)
            from wakfu_server.equipment_stats import effective_character
            from wakfu_server import health_store

            effective = effective_character(updated)
            maximum = effective["max_hp"]
            hp = (
                maximum
                if character["hp"] == character["max_hp"]
                else min(character["hp"], maximum)
            )
            db.execute(
                "UPDATE characters SET hp=?,max_hp=? WHERE account_id=? AND id=?",
                (hp, maximum, account_id, character_id),
            )
            health_store.schema(db)
            now_ms = int(self.clock() * 1000)
            db.execute(
                "UPDATE character_regeneration SET initial_hp=?,started_ms=?,last_ms=? WHERE character_id=?",
                (hp, now_ms, now_ms, character_id),
            )
            return self.character(account_id, character_id, db)

    def transition_map(self, account_id, generation, character_id, source, destination):
        """Compare-and-set an owned world location without reviving stale sessions."""
        keys = ("map_id", "instance_id", "x", "y", "z")
        if any(type(destination.get(key)) is not int for key in keys):
            raise ValueError("Invalid map destination")
        if (
            destination["map_id"] <= 0
            or destination["instance_id"] < 0
            or not -(1 << 15) <= destination["z"] < (1 << 15)
        ):
            raise ValueError("Invalid map destination")
        if (
            any(not -(1 << 31) <= destination[key] < (1 << 31) for key in ("x", "y"))
            or destination["map_id"] >= (1 << 63)
            or destination["instance_id"] >= (1 << 63)
        ):
            raise ValueError("Invalid map destination")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
                (account_id, generation, self.clock()),
            ).fetchone()
            if session is None or session["character_id"] != character_id:
                raise ValueError("Sesión o personaje inválidos.")
            current = self.character(account_id, character_id, db)
            if any(current[key] != source[key] for key in keys):
                raise ValueError("Map origin is desynchronized")
            db.execute(
                "UPDATE characters SET map_id=?,instance_id=?,x=?,y=?,z=? WHERE id=?",
                (*[destination[key] for key in keys], character_id),
            )
            return self.character(account_id, character_id, db)

    def account_kamas(self, account_id):
        from wakfu_server.combat_rewards import wallet

        return wallet(self, account_id)
