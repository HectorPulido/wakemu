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
from wakfu_server.account_bans import require_access
import time
from protocol_codec import APPEARANCE_FIELDS
from wakfu_server.characters.selection_capacity import configured_capacity


class Store:
    def __init__(
        self, database_url, clock=time.time, *, max_characters=None, password_file=None
    ):
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError("PostgreSQL connection configuration required")
        self.database_url = database_url
        self.clock = clock
        self.max_characters = configured_capacity(max_characters)
        self.database = Database(
            database_url,
            password_file=password_file
            or os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )

    def connection(self, **options):
        return self.database.connection(**options)

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
        with self.connection() as db:
            require_access(db, row["id"], self.now())
        return {"id": row["id"], "username": row["username"]}

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def issue_token(self, account_id, kind, ttl=300, generation=None, realm_id=None):
        if kind not in {"game", "remember", "api", "ticket", "scheduler"}:
            raise ValueError("Invalid token kind")
        token = secrets.token_urlsafe(32)
        with self.connection() as db:
            require_access(db, account_id, self.now())
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
            owner = db.execute(
                "SELECT account_id FROM tokens WHERE digest=%s AND kind=%s",
                (self.digest(token), kind),
            ).fetchone()
            if owner is None:
                raise ValueError("Acceso inválido o caducado.")
            require_access(db, owner["account_id"], self.now())
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

    def begin_session(self, account_id, ttl=300):
        generation = secrets.token_hex(16)
        with self.connection() as db:
            require_access(db, account_id, self.now())
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

    def session_health(self, account_id, generation, *, renew=False, ttl=300):
        """Observe lease ownership and conditional renewal in one SQL statement."""
        with self.connection() as db:
            row = db.execute(
                "WITH observed AS MATERIALIZED (SELECT generation,expires_at,clock_timestamp() AS checked_at "
                "FROM sessions WHERE account_id=%s FOR UPDATE), renewed AS ("
                "UPDATE sessions s SET expires_at=%s FROM observed o WHERE s.account_id=%s "
                "AND s.generation=%s AND o.generation=%s AND o.expires_at>o.checked_at AND %s "
                "RETURNING s.expires_at) SELECT clock_timestamp() AS db_now,o.generation,o.expires_at,"
                "o.checked_at,(SELECT expires_at FROM renewed) AS renewed_until "
                "FROM (SELECT 1) singleton LEFT JOIN observed o ON TRUE",
                (account_id, self.now(ttl), account_id, generation, generation, renew),
            ).fetchone()
        current = row["generation"]
        reason = (
            "missing"
            if current is None
            else "replaced"
            if current != generation
            else "expired"
            if row["expires_at"] <= row["checked_at"]
            else "renewal_failed"
            if renew and row["renewed_until"] is None
            else "valid"
        )
        fingerprint = (
            lambda value: None
            if value is None
            else hashlib.sha256(value.encode()).hexdigest()[:12]
        )
        return dict(
            valid=reason == "valid",
            reason=reason,
            expected_generation_id=fingerprint(generation),
            observed_generation_id=fingerprint(current),
            expires_at=None
            if row["expires_at"] is None
            else row["expires_at"].isoformat(),
            db_now=row["db_now"].isoformat(),
            renewed_until=None
            if row["renewed_until"] is None
            else row["renewed_until"].isoformat(),
        )

    def heartbeat(self, account_id, generation, ttl=300):
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
            from wakfu_server.characters.guild_character import record_presence

            record_presence(db, account_id, generation)
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
                    "SELECT count(*) AS count FROM characters WHERE account_id=%s AND deleted_at IS NULL",
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
                    "INSERT INTO account_haven_bags(account_id,character_id) VALUES(%s,%s) "
                    "ON CONFLICT(account_id) DO NOTHING",
                    (account_id, character_id),
                )
                db.execute(
                    "INSERT INTO character_build_selection(character_id) VALUES(%s)",
                    (character_id,),
                )
                return self.character(account_id, character_id, db)
        except (UniqueViolation, ForeignKeyViolation):
            raise ValueError("Ese nombre ya existe o la cuenta es inválida.") from None

    def cosmetic_record(self, account_id):
        from wakfu_server.characters.cosmetic_store import load

        with self.connection() as db:
            cosmetics = load(db, account_id)
            return None if cosmetics is None else cosmetics.to_record()

    def equip_owned_finishers(self, account_id, character_id, opcode, body):
        from wakfu_server.characters.cosmetic_store import load, equip_finishers
        from wakfu_server.characters.cosmetics import finisher_request

        with self.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
            character = self.character(account_id, character_id, db)
            record = load(db, account_id)
            updated = finisher_request(record, character, opcode, body)
            equip_finishers(
                db,
                character,
                updated.selected_finishers(character_id),
                updated_record=updated,
            )
            return self.character(account_id, character_id, db)

    def character(self, account_id, character_id, db=None):
        if db is None:
            with self.connection() as connection:
                return self.character(account_id, character_id, connection)
        row = db.execute(
            "SELECT c.*,a.is_admin account_is_admin,ap.state AS achievement_progress,"
            "aa.snapshot AS achievement_authority FROM characters c JOIN accounts a ON a.id=c.account_id "
            "LEFT JOIN character_achievement_progress ap ON ap.character_id=c.id "
            "LEFT JOIN character_achievement_authority aa ON aa.character_id=c.id "
            "WHERE c.account_id=%s AND c.id=%s AND c.deleted_at IS NULL",
            (account_id, character_id),
        ).fetchone()
        if row is None:
            raise ValueError("Personaje no encontrado.")
        result = dict(row)
        from wakfu_server.achievements.service import project_section

        result["achievement_section"] = project_section(
            result.pop("achievement_progress"),
            result.pop("achievement_authority"),
            db=db,
        )
        from wakfu_server.characters.nation_state import load as load_nation

        result["nation_id"] = load_nation(db, character_id)
        from wakfu_server.characters.guild_character import load as load_guild

        load_guild(db, self, result)
        from wakfu_server.characters.captured_roster_store import (
            load as load_captured_roster,
        )

        result["captured_roster"] = load_captured_roster(db, result)
        from wakfu_server.characters.cosmetic_store import load as load_cosmetics

        cosmetics = load_cosmetics(db, account_id)
        result["owned_cosmetics"] = None if cosmetics is None else cosmetics.to_record()
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
        from wakfu_server.characters.exploration_secrets import load as load_secrets

        result["exploration_secrets"] = load_secrets(db)
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
        from wakfu_server.characters.dungeon_modulation import hydrate

        return hydrate(db, result)

    def characters(self, account_id):
        with self.connection() as db:
            return [
                self.character(account_id, row["id"], db)
                for row in db.execute(
                    "SELECT id FROM characters WHERE account_id=%s AND deleted_at IS NULL ORDER BY id",
                    (account_id,),
                )
            ]

    def delete_character(self, account_id, generation, character_id):
        """Hide an owned character while retaining rows referenced by history.

        Character selection and deletion serialize on the account session row.
        Active operations that must finish against the character are rejected;
        party membership is removed transactionally and reported for publication.
        """
        if (
            type(account_id) is not int
            or account_id <= 0
            or not isinstance(generation, str)
            or not generation
            or type(character_id) is not int
            or character_id <= 0
        ):
            raise ValueError("Invalid character deletion request")

        from wakfu_server.maps.player_parties import _lock_members

        with self.connection() as db:
            # Match party mutations' advisory-lock order before taking the
            # session/character locks used by selection and owned changes.
            _lock_members(db, (character_id,))
            if (
                db.execute(
                    "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
                ).fetchone()
                is None
            ):
                raise ValueError("Account not found")
            lease = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
                "AND expires_at>%s FOR UPDATE",
                (account_id, generation, self.now()),
            ).fetchone()
            if lease is None or lease["character_id"] is not None:
                raise ValueError("Return to character selection before deletion")
            character = db.execute(
                "SELECT id,name FROM characters WHERE id=%s AND account_id=%s "
                "AND deleted_at IS NULL FOR UPDATE",
                (character_id, account_id),
            ).fetchone()
            if character is None:
                raise ValueError("Character not found")

            if db.execute(
                "SELECT 1 FROM combat_fight_participants p "
                "JOIN combat_fights f ON f.id=p.fight_id "
                "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
                (character_id,),
            ).fetchone():
                raise ValueError("Character has an active fight")
            if db.execute(
                "SELECT 1 FROM player_exchange_members m "
                "JOIN player_exchanges e ON e.id=m.exchange_id "
                "WHERE m.character_id=%s AND (e.state='active' OR "
                "(e.state='invitation' AND e.expires_at>%s)) LIMIT 1",
                (character_id, self.now()),
            ).fetchone():
                raise ValueError("Character has an active exchange")
            if db.execute(
                "SELECT 1 FROM resource_harvest_occupations WHERE character_id=%s "
                "AND expires_at>%s LIMIT 1",
                (character_id, self.now()),
            ).fetchone():
                raise ValueError("Character has an active harvest")
            if db.execute(
                "SELECT 1 FROM craft_occupations WHERE character_id=%s "
                "AND state='active' LIMIT 1",
                (character_id,),
            ).fetchone():
                raise ValueError("Character has an active craft")

            party_change = None
            party = db.execute(
                "SELECT p.id,p.leader_id FROM player_parties p "
                "JOIN player_party_members m ON m.party_id=p.id "
                "WHERE m.character_id=%s FOR UPDATE OF p",
                (character_id,),
            ).fetchone()
            if party is not None:
                before = db.execute(
                    "SELECT character_id FROM player_party_members WHERE party_id=%s "
                    "ORDER BY joined_order",
                    (party["id"],),
                ).fetchall()
                db.execute(
                    "DELETE FROM player_party_invitations WHERE inviter_id=%s OR invitee_id=%s",
                    (character_id, character_id),
                )
                db.execute(
                    "DELETE FROM player_party_members WHERE character_id=%s",
                    (character_id,),
                )
                remaining = db.execute(
                    "SELECT character_id FROM player_party_members WHERE party_id=%s "
                    "ORDER BY joined_order",
                    (party["id"],),
                ).fetchall()
                removed = [character_id]
                if len(remaining) < 2:
                    removed.extend(row["character_id"] for row in remaining)
                    if remaining:
                        survivor = remaining[0]["character_id"]
                        db.execute(
                            "DELETE FROM player_party_invitations WHERE inviter_id=%s OR invitee_id=%s",
                            (survivor, survivor),
                        )
                    from wakfu_server.player_parties import dissolve

                    dissolve(db, party["id"])
                    remaining_ids = []
                else:
                    leader = (
                        remaining[0]["character_id"]
                        if party["leader_id"] == character_id
                        else party["leader_id"]
                    )
                    db.execute(
                        "UPDATE player_parties SET leader_id=%s,revision=revision+1 WHERE id=%s",
                        (leader, party["id"]),
                    )
                    remaining_ids = [row["character_id"] for row in remaining]
                party_change = {
                    "party_id": party["id"],
                    "deleted_character_id": character_id,
                    "removed": removed,
                    "remaining": remaining_ids,
                    "previous_members": [row["character_id"] for row in before],
                }
            db.execute(
                "DELETE FROM player_party_invitations WHERE inviter_id=%s OR invitee_id=%s",
                (character_id, character_id),
            )
            db.execute(
                "UPDATE sessions SET character_id=NULL WHERE account_id=%s AND character_id=%s",
                (account_id, character_id),
            )
            # Saved heroes must never retain a soft-deleted owned actor.
            removed_hero = db.execute(
                "DELETE FROM account_hero_slots WHERE account_id=%s AND character_id=%s RETURNING slot",
                (account_id, character_id),
            ).fetchone()
            db.execute(
                "DELETE FROM account_hero_rosters WHERE account_id=%s AND leader_id=%s",
                (account_id, character_id),
            )
            if removed_hero is not None:
                db.execute(
                    "UPDATE account_hero_rosters SET revision=revision+1 WHERE account_id=%s",
                    (account_id,),
                )
            db.execute(
                "UPDATE characters SET deleted_at=%s WHERE id=%s AND account_id=%s "
                "AND deleted_at IS NULL",
                (self.now(), character_id, account_id),
            )
            return {
                "character_id": character_id,
                "name": character["name"],
                "party_change": party_change,
            }

    def clear_character(self, account_id, generation):
        with self.connection() as db:
            from wakfu_server.characters.guild_character import record_presence

            record_presence(db, account_id, generation)
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
                "SELECT id FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL FOR UPDATE",
                (character_id, account_id),
            ).fetchone()
            is None
        ):
            raise ValueError("Personaje no encontrado.")

    def select_character(self, account_id, generation, character_id):
        with self.connection() as db:
            # Shared cosmetic writers lock account before character.
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
            self.lock_character(
                db, account_id, generation, character_id, selected=False
            )
            from wakfu_server.characters.guild_character import record_presence
            from wakfu_server.equipment_stacks import normalize

            normalize(db, character_id)
            character = self.character(account_id, character_id, db)
            from wakfu_server.achievements.service import drain_rewards

            # Selection publishes a fresh absolute bootstrap. Retry earned
            # entitlements first, then reload XP, inventory and account unlocks;
            # incremental grant packets must not double-apply that snapshot.
            drain_rewards(db, self, character)
            character = self.character(account_id, character_id, db)
            from wakfu_server.characters.cosmetic_store import load as load_cosmetics
            from psycopg.types.json import Jsonb

            cosmetics = load_cosmetics(db, account_id)
            if (
                cosmetics is not None
                and cosmetics.items
                and character_id not in dict(cosmetics.selections)
            ):
                cosmetics = cosmetics.equip_finishers(character, ())
                db.execute(
                    "INSERT INTO account_cosmetics(account_id,record) VALUES(%s,%s) "
                    "ON CONFLICT(account_id) DO UPDATE SET record=EXCLUDED.record,revision=account_cosmetics.revision+1",
                    (account_id, Jsonb(cosmetics.to_record())),
                )
                character = self.character(account_id, character_id, db)
            from wakfu_server.characters.starter_decks import (
                initialize as initialize_decks,
            )

            initialize_decks(db, character)
            character = self.character(account_id, character_id, db)
            record_presence(db, account_id, generation)
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
            if current.get("dungeon_modulation") is not None:
                raise ValueError("Competitive automatic build selection is read-only")
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

        if type(in_fight) is not bool:
            raise ValueError("Invalid build combat state")
        if not valid_index(index) or index == 0:
            raise ValueError("Default build cannot be deleted")
        with self.connection() as db:
            self.lock_character(db, account_id, generation, character_id)
            current = self.character(account_id, character_id, db)
            active_edit = index == current["active_build_index"]
            durable_fight = db.execute(
                "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
                (character_id,),
            ).fetchone()
            if active_edit and (in_fight or durable_fight):
                raise ValueError("Active build cannot be deleted during combat")
            modulation = current.get("dungeon_modulation")
            if modulation is not None and index == modulation["build_index"]:
                raise ValueError("Temporary automatic build is read-only")
            sheet = current["builds"].get(index)
            if sheet is None:
                raise ValueError("Requested build does not exist")
            if dict(proto_fields(bytes.fromhex(sheet["sheet"]))).get(64, 0):
                raise ValueError("Permanent build cannot be deleted")
            if not active_edit:
                # An inactive sheet is not a change to the live actor. In
                # particular, do not rewrite combat HP or regeneration.
                db.execute(
                    "DELETE FROM character_builds WHERE character_id=%s AND build_index=%s",
                    (character_id, index),
                )
                return self.character(account_id, character_id, db)
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
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
            lease = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
                "AND expires_at>%s FOR UPDATE",
                (account_id, generation, self.now()),
            ).fetchone()
            if lease is None:
                raise ValueError("Invalid build session")
            db.execute(
                "SELECT account_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
                (account_id,),
            )
            from wakfu_server.characters.heroes import session_authorized

            if not session_authorized(
                db,
                {
                    "account_id": account_id,
                    "id": character_id,
                    "selected_character_id": lease["character_id"],
                },
            ):
                raise ValueError("Build character is not an active owned hero")
            self.lock_character(
                db, account_id, generation, character_id, selected=False
            )
            character = self.character(account_id, character_id, db)
            active_edit = build_index == character["active_build_index"]
            if (
                active_edit
                and db.execute(
                    "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                    "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
                    (character_id,),
                ).fetchone()
            ):
                raise ValueError("Active build cannot be saved during combat")
            modulation = character.get("dungeon_modulation")
            if modulation is not None and build_index == modulation["build_index"]:
                raise ValueError("Temporary automatic build is read-only")
            from wakfu_server.builds import validated_saved_blobs
            from wakfu_server.equipment_stacks import for_sheet

            if for_sheet(db, character_id, blobs["equipment"]):
                character = self.character(account_id, character_id, db)
            merged = validated_saved_blobs(character, build_index, blobs)
            values = [
                merged[key] for key in ("sheet", "equipment", "deck", "aptitudes")
            ]
            db.execute(
                "INSERT INTO character_builds VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(character_id,build_index) DO UPDATE SET "
                "sheet=excluded.sheet,equipment=excluded.equipment,deck=excluded.deck,aptitudes=excluded.aptitudes",
                (character_id, build_index, *values),
            )
            updated = self.character(account_id, character_id, db)
            if not active_edit:
                return updated
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
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
            self.lock_character(db, account_id, generation, character_id)
            current = self.character(account_id, character_id, db)
            if any(current[key] != source[key] for key in keys):
                raise ValueError("Map origin is desynchronized")
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (*[destination[key] for key in keys], character_id),
            )
            from wakfu_server.characters.heroes import follow_main

            follow_main(db, self, account_id, generation, character_id)
            from wakfu_server.characters.dungeon_modulation_health import reconcile

            reconcile(self, db, [character_id])
            return self.character(account_id, character_id, db)

    def account_kamas(self, account_id):
        from wakfu_server.combat_rewards import wallet

        return wallet(self, account_id)
