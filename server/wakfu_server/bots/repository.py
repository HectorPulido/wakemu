"""Dedicated bot identities; normal account and character initialization is reused."""
from contextlib import contextmanager
from copy import copy
import re
import secrets

from psycopg.types.json import Jsonb


CAPABILITIES = frozenset(("chat", "exchange"))
PUBLIC_CHARACTER_FIELDS = (
    "id",
    "name",
    "breed",
    "sex",
    "level",
    "map_id",
    "instance_id",
    "x",
    "y",
    "z",
)


def validate_bot_id(bot_id):
    if (
        not isinstance(bot_id, str)
        or re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", bot_id) is None
    ):
        raise ValueError("Invalid bot identity")
    return bot_id


def public_character(character):
    return {key: character[key] for key in PUBLIC_CHARACTER_FIELDS if key in character}


def validate_capabilities(capabilities):
    if (
        not isinstance(capabilities, list)
        or any(
            not isinstance(value, str) or value not in CAPABILITIES
            for value in capabilities
        )
        or len(set(capabilities)) != len(capabilities)
    ):
        raise ValueError("Invalid bot capabilities")


def validate_create(args):
    allowed = {
        "name",
        "breed",
        "sex",
        "face",
        "hair",
        "colors",
        "capabilities",
        "location",
        "initial_kamas",
    }
    if not isinstance(args, dict) or set(args) - allowed:
        raise ValueError("Invalid bot creation fields")
    if not isinstance(args.get("name"), str):
        raise ValueError("Bot name is required")
    validate_capabilities(args.get("capabilities", []))
    for key, default in (("breed", 15), ("sex", 0), ("face", 0), ("hair", 0)):
        if type(args.get(key, default)) is not int:
            raise ValueError("Invalid bot appearance")
    colors = args.get("colors", [0xFFFFFF] * 3)
    if (
        not isinstance(colors, list)
        or len(colors) != 3
        or any(type(value) is not int or not 0 <= value <= 0xFFFFFF for value in colors)
    ):
        raise ValueError("Invalid bot colors")
    budget = args.get("initial_kamas", 0)
    if type(budget) is not int or not 0 <= budget <= 1_000_000_000:
        raise ValueError("Invalid initial bot budget")
    location = args.get("location")
    if location is not None:
        if (
            not isinstance(location, dict)
            or set(location) - {"map_id", "instance_id", "x", "y", "z"}
            or any(
                type(location.get(key)) is not int for key in ("map_id", "x", "y", "z")
            )
            or type(location.get("instance_id", 0)) is not int
            or location.get("instance_id", 0) != 0
            or not 0 < location["map_id"] < 2**31
            or any(not -(2**31) <= location[axis] < 2**31 for axis in ("x", "y"))
            or not -(2**15) <= location["z"] < 2**15
        ):
            raise ValueError("Bot placement requires a public native map cell")
        from wakfu_server.combat_terrain import map_geometry

        if (location["x"], location["y"], location["z"]) not in set(
            map(tuple, map_geometry(location["map_id"])["cells"])
        ):
            raise ValueError("Bot placement is outside native walkable terrain")


class BotsRepository:
    def __init__(self, store):
        self.store = store

    def get(self, bot_id):
        validate_bot_id(bot_id)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT * FROM world_bots WHERE bot_id=%s", (bot_id,)
            ).fetchone()
        if row is None:
            raise ValueError("Unknown bot")
        return dict(row)

    def list(self):
        with self.store.connection() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM world_bots ORDER BY bot_id")
            ]

    def configure(self, bot_id, capabilities):
        validate_bot_id(bot_id)
        validate_capabilities(capabilities)
        with self.store.connection() as db:
            row = db.execute(
                "UPDATE world_bots SET capabilities=%s WHERE bot_id=%s RETURNING *",
                (Jsonb(capabilities), bot_id),
            ).fetchone()
        if row is None:
            raise ValueError("Unknown bot")
        return dict(row)

    def create(self, bot_id, args):
        validate_bot_id(bot_id)
        validate_create(args)
        config = dict(
            name=args["name"].strip(),
            breed=args.get("breed", 15),
            sex=args.get("sex", 0),
            face=args.get("face", 0),
            hair=args.get("hair", 0),
            colors=args.get("colors", [0xFFFFFF] * 3),
            initial_kamas=args.get("initial_kamas", 0),
            location=args.get("location"),
        )
        with self.store.connection() as db:
            # A transaction-scoped lock makes repeat creation safe across HTTP
            # retries without claiming a similarly named human account.
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 5790545590))",
                (bot_id,),
            )
            existing = db.execute(
                "SELECT * FROM world_bots WHERE bot_id=%s", (bot_id,)
            ).fetchone()
            if existing is not None:
                if existing["creation_config"] != config or set(
                    existing["capabilities"]
                ) != set(args.get("capabilities", [])):
                    raise ValueError(
                        "Bot identity already exists with different configuration"
                    )
                return dict(existing)

            # Store methods keep their normal validation and initialization but
            # share this transaction, so a failure cannot leave orphan accounts.
            scoped = copy(self.store)

            @contextmanager
            def connection(**options):
                with db.transaction():
                    yield db

            scoped.connection = connection
            account = scoped.register(
                "bot_" + secrets.token_hex(12), secrets.token_urlsafe(48)
            )
            character = scoped.create_character(
                account["id"],
                args["name"],
                **{
                    key: args[key]
                    for key in ("breed", "sex", "face", "hair", "colors")
                    if key in args
                },
            )
            location = args.get("location")
            if location is not None:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s AND account_id=%s",
                    (
                        location["map_id"],
                        location["x"],
                        location["y"],
                        location["z"],
                        character["id"],
                        account["id"],
                    ),
                )
            budget = args.get("initial_kamas", 0)
            if budget:
                db.execute(
                    "UPDATE account_wallets SET kamas=%s WHERE account_id=%s",
                    (budget, account["id"]),
                )
            row = db.execute(
                "INSERT INTO world_bots(bot_id,account_id,character_id,capabilities,creation_config) VALUES(%s,%s,%s,%s,%s) RETURNING *",
                (
                    bot_id,
                    account["id"],
                    character["id"],
                    Jsonb(args.get("capabilities", [])),
                    Jsonb(config),
                ),
            ).fetchone()
            return dict(row)
