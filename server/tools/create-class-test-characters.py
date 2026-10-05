#!/usr/bin/env python3
"""Create an account-owned class test roster, without changing existing players."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.store import Store
from wakfu_server.breed_resources import playable_breeds
from wakfu_server.spells import available_spells, encode_deck, validate_deck
from wakfu_server.health import maximum
from wakfu_server.progression import level_xp
from wakfu_server.builds import EMPTY_EQUIPMENT, EMPTY_APTITUDES, validate
from wakfu_server.wire import proto_field


CLASS_LABELS = {
    1: "Feca",
    2: "Osamodas",
    3: "Anutrof",
    4: "Sram",
    5: "Xelor",
    6: "Zurcarak",
    7: "Aniripsa",
    8: "Yopuka",
    9: "Ocra",
    10: "Sadida",
    11: "Sacro",
    12: "Pandawa",
    13: "Tymador",
    14: "Zobal",
    15: "Uginak",
    16: "Steamer",
    18: "Selotrop",
    19: "Hipermago",
}


def create_roster(store, account_id, *, level=200, prefix="Prueba"):
    level_xp(level)
    breeds = playable_breeds()
    if breeds != frozenset(CLASS_LABELS):
        raise ValueError("Installed class catalog differs from this test roster")
    requested = [(breed, f"{prefix} {CLASS_LABELS[breed]}") for breed in sorted(breeds)]
    requested.append((11, f"{prefix} Sacro Control"))
    with store.connection() as db:
        if (
            db.execute("SELECT id FROM accounts WHERE id=?", (account_id,)).fetchone()
            is None
        ):
            raise ValueError("Account does not exist")
        existing = {
            row["name"]: dict(row)
            for row in db.execute("SELECT id,account_id,name,breed FROM characters")
        }
        missing = 0
        for breed, name in requested:
            row = existing.get(name)
            if row is not None and (
                row["account_id"] != account_id or row["breed"] != breed
            ):
                raise ValueError(
                    f"Test character name is already owned elsewhere: {name}"
                )
            missing += int(row is None)
        current = db.execute(
            "SELECT COUNT(*) FROM characters WHERE account_id=?", (account_id,)
        ).fetchone()[0]
        if current + missing > store.max_characters:
            raise ValueError(
                "Configured selection capacity is too small for this roster"
            )
    result = []
    for breed, name in requested:
        previous = existing.get(name)
        if previous is not None:
            character = store.character(account_id, previous["id"])
            created = False
        else:
            character = store.create_character(account_id, name, breed=breed)
            character.update(
                level=level, hp=maximum(breed, level), max_hp=maximum(breed, level)
            )
            spells = available_spells(breed, level)
            active = [s["id"] for s in spells if s["kind"] == "active"][:12]
            deck = encode_deck(active, (), -1)
            sheet = b"".join(
                proto_field(tag, value)
                for tag, value in (
                    (8, 0),
                    (18, b"Build por defecto"),
                    (24, (1 << 64) - 1),
                    (56, 1),
                    (64, 1),
                )
            )
            blobs = dict(
                sheet=sheet,
                equipment=EMPTY_EQUIPMENT,
                deck=deck,
                aptitudes=EMPTY_APTITUDES,
            )
            validate(character, 0, blobs)
            with store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "UPDATE characters SET level=?,hp=?,max_hp=? WHERE id=? AND account_id=?",
                    (
                        level,
                        character["hp"],
                        character["max_hp"],
                        character["id"],
                        account_id,
                    ),
                )
                db.execute(
                    "UPDATE character_progression SET xp=? WHERE character_id=?",
                    (level_xp(level), character["id"]),
                )
                db.execute(
                    "INSERT INTO character_builds VALUES(?,?,?,?,?,?)",
                    (character["id"], 0, sheet, EMPTY_EQUIPMENT, deck, EMPTY_APTITUDES),
                )
            character = store.character(account_id, character["id"])
            created = True
        saved = bytes.fromhex(character["builds"][0]["deck"])
        deck = validate_deck(saved, breed, character["level"])
        spells = available_spells(breed, character["level"])
        result.append(
            dict(
                id=character["id"],
                name=character["name"],
                breed=breed,
                level=character["level"],
                created=created,
                available_active=sum(s["kind"] == "active" for s in spells),
                available_passive=sum(s["kind"] == "passive" for s in spells),
                deck_active=deck["active"],
                deck_passive=deck["passive"],
                map_id=character["map_id"],
                position=[character[k] for k in ("x", "y", "z")],
            )
        )
    return dict(
        account_id=account_id,
        requested_count=19,
        playable_classes=len(breeds),
        characters=result,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--account-id", required=True, type=int)
    parser.add_argument("--level", type=int, default=200)
    parser.add_argument("--max-characters", type=int, default=24)
    parser.add_argument("--prefix", default="Prueba")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = create_roster(
        Store(args.db, max_characters=args.max_characters),
        args.account_id,
        level=args.level,
        prefix=args.prefix,
    )
    Path(args.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "account_id": report["account_id"],
                "count": len(report["characters"]),
                "created": sum(r["created"] for r in report["characters"]),
                "level": args.level,
            },
            ensure_ascii=False,
        )
    )
