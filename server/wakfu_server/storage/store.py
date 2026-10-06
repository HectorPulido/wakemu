"""PostgreSQL persistence with explicit account and lease ownership."""
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
import secrets
from psycopg.errors import UniqueViolation, ForeignKeyViolation
from psycopg.types.json import Jsonb
from wakfu_server.postgres import Database
import time
from protocol_codec import APPEARANCE_FIELDS


class Store:
    def __init__(
        self, database_url, clock=time.time, *, max_characters=None, password_file=None
    ):
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError("PostgreSQL connection configuration required")
        self.database_url = database_url
        self.clock = clock
        self.max_characters = (
            int(os.environ.get("WAKFU_MAX_CHARACTERS", "5"))
            if max_characters is None
            else max_characters
        )
        if type(self.max_characters) is not int or not 1 <= self.max_characters <= 127:
            raise ValueError("Invalid character selection capacity")
        self.database = Database(
            database_url,
            password_file=password_file
            or os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )

    def connection(self):
        return self.database.connection()

    def close(self):
        self.database.close()

    def now(self, offset=0):
        return datetime.fromtimestamp(self.clock() + offset, timezone.utc)

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
        try:
            with self.connection() as db:
                row = db.execute(
                    "INSERT INTO accounts(username,username_key,salt,password_hash,created_at) "
                    "VALUES(%s,%s,%s,%s,%s) RETURNING id,username",
                    (username, username.casefold(), salt, hashed, self.now()),
                ).fetchone()
                db.execute(
                    "INSERT INTO account_wallets(account_id) VALUES(%s)", (row["id"],)
                )
        except UniqueViolation:
            raise ValueError("Ese usuario ya existe.") from None
        return row

    def authenticate(self, username, password):
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM accounts WHERE username_key=%s",
                (username.strip().casefold(),),
            ).fetchone()
        salt = row["salt"] if row else bytes(16)
        candidate = self.password_hash(password, salt)
        if row is None or not hmac.compare_digest(candidate, row["password_hash"]):
            raise ValueError("Usuario o contraseña incorrectos.")
        return {"id": row["id"], "username": row["username"]}

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def issue_token(self, account_id, kind, ttl=300, generation=None, realm_id=None):
        if kind not in {"game", "remember", "api", "ticket", "scheduler"}:
            raise ValueError("Invalid token kind")
        token = secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute("DELETE FROM tokens WHERE expires_at<=%s", (self.now(),))
            db.execute(
                "INSERT INTO tokens(digest,account_id,kind,expires_at,generation,realm_id) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    self.digest(token),
                    account_id,
                    kind,
                    self.now(ttl),
                    generation,
                    realm_id,
                ),
            )
        return token

    def token(self, token, kind, consume=False):
        with self.connection() as db:
            if consume:
                row = db.execute(
                    "WITH consumed AS (DELETE FROM tokens WHERE digest=%s AND kind=%s "
                    "AND expires_at>%s RETURNING *) "
                    "SELECT t.*,a.username FROM consumed t JOIN accounts a ON a.id=t.account_id",
                    (self.digest(token), kind, self.now()),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT t.*,a.username FROM tokens t JOIN accounts a ON a.id=t.account_id "
                    "WHERE digest=%s AND kind=%s AND expires_at>%s",
                    (self.digest(token), kind, self.now()),
                ).fetchone()
            if row is None:
                raise ValueError("Acceso inválido o caducado.")
            return row

    def revoke_token(self, token):
        with self.connection() as db:
            db.execute("DELETE FROM tokens WHERE digest=%s", (self.digest(token),))

    def begin_session(self, account_id, ttl=60):
        generation = secrets.token_hex(16)
        with self.connection() as db:
            if (
                db.execute(
                    "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
                ).fetchone()
                is None
            ):
                raise ValueError("Cuenta inválida")
            db.execute(
                "INSERT INTO sessions(account_id,generation,expires_at) VALUES(%s,%s,%s) "
                "ON CONFLICT(account_id) DO UPDATE SET generation=excluded.generation, "
                "expires_at=excluded.expires_at,character_id=NULL",
                (account_id, generation, self.now(ttl)),
            )
            db.execute(
                "DELETE FROM tokens WHERE account_id=%s AND kind='ticket'",
                (account_id,),
            )
        return generation

    def current_session(self, account_id, generation):
        with self.connection() as db:
            return (
                db.execute(
                    "SELECT 1 FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s",
                    (account_id, generation, self.now()),
                ).fetchone()
                is not None
            )

    def current_character_session(self, account_id, generation, character_id):
        with self.connection() as db:
            return (
                db.execute(
                    "SELECT 1 FROM sessions WHERE account_id=%s AND generation=%s "
                    "AND character_id=%s AND expires_at>%s",
                    (account_id, generation, character_id, self.now()),
                ).fetchone()
                is not None
            )

    def heartbeat(self, account_id, generation, ttl=60):
        with self.connection() as db:
            return (
                db.execute(
                    "UPDATE sessions SET expires_at=%s WHERE account_id=%s AND generation=%s AND expires_at>%s",
                    (self.now(ttl), account_id, generation, self.now()),
                ).rowcount
                == 1
            )

    def end_session(self, account_id, generation):
        with self.connection() as db:
            db.execute(
                "DELETE FROM sessions WHERE account_id=%s AND generation=%s",
                (account_id, generation),
            )
            db.execute(
                "DELETE FROM tokens WHERE account_id=%s AND generation=%s AND kind='ticket'",
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
        from wakfu_server.health import maximum
        from wakfu_server.inventory import initialize
        from wakfu_server.haven_bag_store import initial_layout

        hp = maximum(breed, 1)
        try:
            with self.connection() as db:
                if (
                    db.execute(
                        "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
                    ).fetchone()
                    is None
                ):
                    raise ValueError("Cuenta inválida.")
                count = db.execute(
                    "SELECT count(*) AS count FROM characters WHERE account_id=%s",
                    (account_id,),
                ).fetchone()["count"]
                if count >= self.max_characters:
                    raise ValueError(
                        f"Máximo {self.max_characters} personajes por cuenta."
                    )
                character_id = db.execute(
                    "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,created_at,appearance,hp,max_hp) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (
                        account_id,
                        name,
                        name.casefold(),
                        breed,
                        bool(sex),
                        face,
                        hair,
                        Jsonb(colors),
                        self.now(),
                        Jsonb(appearance),
                        hp,
                        hp,
                    ),
                ).fetchone()["id"]
                initialize(db, character_id)
                db.execute(
                    "INSERT INTO character_progression(character_id,xp) VALUES(%s,0)",
                    (character_id,),
                )
                db.execute(
                    "INSERT INTO account_wallets(account_id) VALUES(%s) ON CONFLICT(account_id) DO NOTHING",
                    (account_id,),
                )
                db.execute(
                    "INSERT INTO haven_bags(character_id,layout) VALUES(%s,%s)",
                    (character_id, Jsonb(initial_layout(character_id))),
                )
                db.execute(
                    "INSERT INTO character_build_selection(character_id) VALUES(%s)",
                    (character_id,),
                )
                return self.character(account_id, character_id, db)
        except (UniqueViolation, ForeignKeyViolation):
            raise ValueError("Ese nombre ya existe o la cuenta es inválida.") from None

    def character(self, account_id, character_id, db=None):
        if db is None:
            with self.connection() as connection:
                return self.character(account_id, character_id, connection)
        row = db.execute(
            "SELECT * FROM characters WHERE account_id=%s AND id=%s",
            (account_id, character_id),
        ).fetchone()
        if row is None:
            raise ValueError("Personaje no encontrado.")
        result = dict(row)
        capacity = db.execute(
            "SELECT value FROM settings WHERE name='non_permanent_build_limit'"
        ).fetchone()
        if capacity is None or type(capacity["value"]) is not int:
            raise ValueError("Invalid non-permanent build capacity setting")
        result["non_permanent_build_limit"] = int(capacity["value"])
        if not 1 <= result["non_permanent_build_limit"] <= 24:
            raise ValueError("Invalid non-permanent build capacity setting")
        from wakfu_server.combat_rewards import load as load_progression

        result.update(load_progression(db, result))
        from wakfu_server.haven_bag_store import load

        result["haven_bag"] = load(db, character_id)
        from wakfu_server.inventory import load as load_inventory

        result["inventory_containers"] = load_inventory(db, character_id)
        from wakfu_server.inventory_items import load as load_items

        result["inventory_items"] = load_items(db, character_id)
        from wakfu_server.mount_state import load as load_mount_state

        result["mount_state"] = load_mount_state(db, character_id)
        from wakfu_server.world_shortcuts import load as load_shortcuts

        result["world_shortcuts"] = load_shortcuts(db, character_id)
        result["builds"] = {
            entry["build_index"]: {
                key: entry[key].hex()
                for key in ("sheet", "equipment", "deck", "aptitudes")
            }
            for entry in db.execute(
                "SELECT * FROM character_builds WHERE character_id=%s", (character_id,)
            )
        }
        if not result["appearance"]:
            result["appearance"] = dict(
                zip(APPEARANCE_FIELDS[:3], (c - (1 << 24) for c in result["colors"]))
            )
            result["appearance"].update(
                sex=result["sex"], faceIndex=result["face"], clothIndex=result["hair"]
            )
        selection = db.execute(
            "SELECT active_index,revision FROM character_build_selection WHERE character_id=%s",
            (character_id,),
        ).fetchone()
        result["active_build_index"] = selection["active_index"]
        result["build_selection_revision"] = selection["revision"]
        from wakfu_server.builds import catalog_indices, effective_sheet_level

        if result["active_build_index"] not in catalog_indices(result):
            raise ValueError("Selected build is missing from owned catalog")
        result["effective_level"] = effective_sheet_level(
            result, result["active_build_index"]
        )
        return result

    def characters(self, account_id):
        with self.connection() as db:
            return [
                self.character(account_id, row["id"], db)
                for row in db.execute(
                    "SELECT id FROM characters WHERE account_id=%s ORDER BY id",
                    (account_id,),
                )
            ]

    def clear_character(self, account_id, generation):
        with self.connection() as db:
            result = db.execute(
                "UPDATE sessions SET character_id=NULL WHERE account_id=%s AND generation=%s AND expires_at>%s",
                (account_id, generation, self.now()),
            )
            if result.rowcount != 1:
                raise ValueError("Sesión sustituida o caducada.")

    def lock_character(
        self, db, account_id, generation, character_id, *, selected=True
    ):
        """Lock session before character, consistently across owned mutations."""
        lease = db.execute(
            "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
            "AND expires_at>%s FOR UPDATE",
            (account_id, generation, self.now()),
        ).fetchone()
        if lease is None or (selected and lease["character_id"] != character_id):
            raise ValueError("Sesión o personaje inválidos.")
        if (
            db.execute(
                "SELECT id FROM characters WHERE id=%s AND account_id=%s FOR UPDATE",
                (character_id, account_id),
            ).fetchone()
            is None
        ):
            raise ValueError("Personaje no encontrado.")

    def select_character(self, account_id, generation, character_id):
        with self.connection() as db:
            self.lock_character(
                db, account_id, generation, character_id, selected=False
            )
            character = self.character(account_id, character_id, db)
            db.execute(
                "UPDATE sessions SET character_id=%s WHERE account_id=%s AND generation=%s",
                (character_id, account_id, generation),
            )
            return character

    def move(self, account_id, generation, character_id, start, end):
        for position in (start, end):
            if (
                not isinstance(position, dict)
                or any(type(position.get(key)) is not int for key in ("x", "y", "z"))
                or any(
                    not -(1 << 31) <= position[key] < (1 << 31) for key in ("x", "y")
                )
                or not -(1 << 15) <= position["z"] < (1 << 15)
            ):
                raise ValueError("Invalid movement position")
        with self.connection() as db:
            self.lock_character(db, account_id, generation, character_id)
            character = self.character(account_id, character_id, db)
            if any(character[k] != start[k] for k in ("x", "y", "z")):
                raise ValueError("Posición de origen desincronizada.")
            db.execute(
                "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s AND account_id=%s",
                (end["x"], end["y"], end["z"], character_id, account_id),
            )
            return self.character(account_id, character_id, db)

    def activate_build(self, account_id, generation, character_id, index, *, in_fight):
        from wakfu_server.builds import valid_index, catalog_indices
        from wakfu_server.equipment_stats import effective_character

        if type(in_fight) is not bool or in_fight:
            raise ValueError("Build activation requires an outside-combat character")
        if not valid_index(index):
            raise ValueError("Invalid active build index")
        with self.connection() as db:
            self.lock_character(db, account_id, generation, character_id)
            current = self.character(account_id, character_id, db)
            if index not in catalog_indices(current):
                raise ValueError("Requested build does not exist")
            if index == current["active_build_index"]:
                return current
            selected = dict(current, active_build_index=index)
            effective = effective_character(selected)
            maximum = effective["max_hp"]
            from wakfu_server.health_policy import reconfigure

            hp = reconfigure(db, current, maximum)
            db.execute(
                "UPDATE character_build_selection SET active_index=%s,revision=revision+1 WHERE character_id=%s",
                (index, character_id),
            )
            from wakfu_server.mount_state import reconcile_equipment

            reconcile_equipment(db, current, selected)

            if maximum != current["max_hp"]:
                now = self.now()
                db.execute(
                    "UPDATE character_regeneration SET initial_hp=%s,started_at=%s,last_at=%s WHERE character_id=%s",
                    (hp, now, now, character_id),
                )
            return self.character(account_id, character_id, db)

    def delete_build(self, account_id, generation, character_id, index, *, in_fight):
        """Delete an owned sheet, selection and health in one transaction."""
        from wakfu_server.builds import valid_index
        from wakfu_server.wire import proto_fields
        from wakfu_server.equipment_stats import effective_character

        if type(in_fight) is not bool or in_fight:
            raise ValueError("Build deletion requires an outside-combat character")
        if not valid_index(index) or index == 0:
            raise ValueError("Default build cannot be deleted")
        with self.connection() as db:
            self.lock_character(db, account_id, generation, character_id)
            current = self.character(account_id, character_id, db)
            sheet = current["builds"].get(index)
            if sheet is None:
                raise ValueError("Requested build does not exist")
            if dict(proto_fields(bytes.fromhex(sheet["sheet"]))).get(64, 0):
                raise ValueError("Permanent build cannot be deleted")
            remaining = {i: b for i, b in current["builds"].items() if i != index}
            active = (
                0
                if current["active_build_index"] == index
                else current["active_build_index"]
            )
            effective = effective_character(
                dict(current, builds=remaining, active_build_index=active)
            )
            from wakfu_server.mount_state import reconcile_equipment

            reconcile_equipment(
                db, current, dict(current, builds=remaining, active_build_index=active)
            )
            db.execute(
                "DELETE FROM character_builds WHERE character_id=%s AND build_index=%s",
                (character_id, index),
            )
            if active != current["active_build_index"]:
                db.execute(
                    "UPDATE character_build_selection SET active_index=%s,revision=revision+1 WHERE character_id=%s",
                    (active, character_id),
                )
            from wakfu_server.health_policy import reconfigure

            hp = reconfigure(db, current, effective["max_hp"])
            if effective["max_hp"] != current["max_hp"]:
                now = self.now()
                db.execute(
                    "UPDATE character_regeneration SET initial_hp=%s,started_at=%s,last_at=%s WHERE character_id=%s",
                    (hp, now, now, character_id),
                )
            return self.character(account_id, character_id, db)

    def save_build(self, account_id, generation, character_id, build_index, blobs):
        with self.connection() as db:
            self.lock_character(db, account_id, generation, character_id)
            character = self.character(account_id, character_id, db)
            from wakfu_server.builds import validate

            validate(character, build_index, blobs)
            previous = character["builds"].get(build_index, {})
            values = [
                blobs[key] or bytes.fromhex(previous.get(key, ""))
                for key in ("sheet", "equipment", "deck", "aptitudes")
            ]
            db.execute(
                "INSERT INTO character_builds VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(character_id,build_index) DO UPDATE SET "
                "sheet=excluded.sheet,equipment=excluded.equipment,deck=excluded.deck,aptitudes=excluded.aptitudes",
                (character_id, build_index, *values),
            )
            updated = self.character(account_id, character_id, db)
            from wakfu_server.mount_state import reconcile_equipment

            reconcile_equipment(db, character, updated)
            from wakfu_server.equipment_stats import effective_character

            effective = effective_character(updated)
            maximum = effective["max_hp"]
            from wakfu_server.health_policy import reconfigure

            hp = reconfigure(db, character, maximum)
            if maximum != character["max_hp"]:
                now = self.now()
                db.execute(
                    "UPDATE character_regeneration SET initial_hp=%s,started_at=%s,last_at=%s WHERE character_id=%s",
                    (hp, now, now, character_id),
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
            or destination["map_id"] >= (1 << 31)
            or destination["instance_id"] >= (1 << 63)
        ):
            raise ValueError("Invalid map destination")
        with self.connection() as db:
            self.lock_character(db, account_id, generation, character_id)
            current = self.character(account_id, character_id, db)
            if any(current[key] != source[key] for key in keys):
                raise ValueError("Map origin is desynchronized")
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (*[destination[key] for key in keys], character_id),
            )
            return self.character(account_id, character_id, db)

    def account_kamas(self, account_id):
        from wakfu_server.combat_rewards import wallet

        return wallet(self, account_id)
