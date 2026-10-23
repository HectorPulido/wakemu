#!/usr/bin/env python3
"""Reproduce companion-pet migration206 from original aMw/fwr model descriptors."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "protocol/pet-models.json"
MIGRATION = ROOT / "migrations/206_native_pet_authority.sql"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def generate(document):
    models = document["models"]
    if (
        len(models) != 126
        or len({row["model_id"] for row in models}) != 126
        or len({row["reference"] for row in models}) != 126
    ):
        raise ValueError("Original companion-pet model coverage changed")
    digest = hashlib.sha256(canonical(document).encode()).hexdigest()
    sql = """-- Original aMw/fwr companion models; separate from native mount_models.
CREATE TABLE native_pet_models (
    model_id integer PRIMARY KEY CHECK (model_id >= 0),
    reference integer NOT NULL UNIQUE CHECK (reference > 0),
    maximum_health integer NOT NULL CHECK (maximum_health > 0),
    xp_per_level integer NOT NULL CHECK (xp_per_level > 0),
    maximum_level integer NOT NULL CHECK (maximum_level >= 0),
    default_equipped_item_ref integer NOT NULL CHECK (default_equipped_item_ref >= 0),
    meal_item_refs integer[] NOT NULL,
    xp_item_refs integer[] NOT NULL,
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$')
);
CREATE TABLE inventory_pets (
    uid bigint PRIMARY KEY REFERENCES inventory_items(uid) ON DELETE CASCADE,
    model_id integer NOT NULL REFERENCES native_pet_models(model_id),
    name text NOT NULL DEFAULT '',
    xp integer NOT NULL DEFAULT 0 CHECK (xp >= 0),
    health integer NOT NULL CHECK (health >= 0),
    color_item_ref integer NOT NULL DEFAULT 0 CHECK (color_item_ref >= 0),
    equipped_item_ref integer NOT NULL DEFAULT 0 CHECK (equipped_item_ref >= 0),
    sleep_item_ref integer NOT NULL DEFAULT 0 CHECK (sleep_item_ref >= 0),
    reskin_item_ref integer NOT NULL DEFAULT 0 CHECK (reskin_item_ref >= 0),
    last_meal_date bigint NOT NULL CHECK (last_meal_date >= 0 AND last_meal_date % 1000 = 0),
    last_hungry_date bigint NOT NULL CHECK (last_hungry_date >= 0 AND last_hungry_date % 1000 = 0),
    sleep_date bigint NOT NULL DEFAULT 0 CHECK (sleep_date >= 0 AND sleep_date % 1000 = 0),
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0),
    CHECK ((sleep_item_ref=0 AND sleep_date=0) OR (sleep_item_ref>0 AND sleep_date>0))
);
CREATE FUNCTION validate_pet_unit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    unit_record inventory_items%ROWTYPE;
    model_record native_pet_models%ROWTYPE;
BEGIN
    SELECT * INTO unit_record FROM inventory_items WHERE uid=NEW.uid FOR UPDATE;
    SELECT * INTO model_record FROM native_pet_models WHERE model_id=NEW.model_id;
    IF unit_record.uid IS NULL OR model_record.model_id IS NULL
        OR unit_record.quantity<>1 OR unit_record.reference<>model_record.reference
        OR NEW.health>model_record.maximum_health
        OR NEW.xp>model_record.xp_per_level*model_record.maximum_level
        OR EXISTS(SELECT 1 FROM inventory_mounts WHERE uid=NEW.uid) THEN
        RAISE EXCEPTION 'Invalid authoritative companion pet unit' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER inventory_pet_unit_valid BEFORE INSERT OR UPDATE ON inventory_pets
    FOR EACH ROW EXECUTE FUNCTION validate_pet_unit();
CREATE FUNCTION preserve_pet_unit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM inventory_pets WHERE uid=OLD.uid)
        AND (NEW.quantity<>1 OR NEW.reference<>OLD.reference OR NEW.uid<>OLD.uid) THEN
        RAISE EXCEPTION 'Pet unit cannot be stacked or redefined' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER inventory_pet_unit_preserved BEFORE UPDATE OF quantity,reference,uid ON inventory_items
    FOR EACH ROW EXECUTE FUNCTION preserve_pet_unit();
INSERT INTO native_pet_models
(model_id,reference,maximum_health,xp_per_level,maximum_level,default_equipped_item_ref,meal_item_refs,xp_item_refs,source_sha256) VALUES
"""
    rows = []
    for model in models:
        for key in ("reference", "maximum_health", "xp_per_level"):
            if type(model[key]) is not int or model[key] <= 0:
                raise ValueError("Invalid native pet model")
        if type(model["model_id"]) is not int or model["model_id"] < 0:
            raise ValueError("Invalid native pet model identity")
        if type(model["maximum_level"]) is not int or model["maximum_level"] < 0:
            raise ValueError("Invalid native pet maximum level")
        if (
            type(model["default_equipped_item_ref"]) is not int
            or model["default_equipped_item_ref"] < 0
        ):
            raise ValueError("Invalid native pet accessory")
        arrays = [
            "ARRAY[" + ",".join(map(str, model[key])) + "]::integer[]"
            for key in ("meal_item_refs", "xp_item_refs")
        ]
        rows.append(
            "("
            + ",".join(
                map(
                    str,
                    [
                        model[key]
                        for key in (
                            "model_id",
                            "reference",
                            "maximum_health",
                            "xp_per_level",
                            "maximum_level",
                            "default_equipped_item_ref",
                        )
                    ],
                )
            )
            + ","
            + ",".join(arrays)
            + ",'"
            + digest
            + "')"
        )
    sql += ",\n".join(rows) + ";\n"
    sql += """-- Previously owned ordinary singletons had no companion-state authority. Establish
-- it once; never touch existing mount rows, identities, owners or item quantities.
INSERT INTO inventory_pets(uid,model_id,health,equipped_item_ref,last_meal_date,last_hungry_date)
SELECT i.uid,m.model_id,m.maximum_health,m.default_equipped_item_ref,
       floor(extract(epoch FROM now()))::bigint*1000,
       floor(extract(epoch FROM now()))::bigint*1000
FROM inventory_items i JOIN native_pet_models m ON m.reference=i.reference
WHERE i.quantity=1 AND NOT EXISTS(SELECT 1 FROM inventory_mounts x WHERE x.uid=i.uid);
"""
    return sql, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-native", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.import_native:
        native = json.loads(args.import_native.read_text())
        models = [
            dict(
                model_id=row["model_id"],
                reference=row["item_ref"],
                maximum_health=row["maximum_health"],
                xp_per_level=row["xp_per_level"],
                maximum_level=row["maximum_level"],
                default_equipped_item_ref=row["default_equipped_item_ref"],
                meal_item_refs=row["meal_item_refs"],
                xp_item_refs=[
                    food["item_ref"] for food in row["pet_xp_foods"] if food["xp"]
                ],
            )
            for row in native
        ]
        document = dict(
            schema_version=1,
            source="Original aMw models constructed through bbx.a/fwr",
            models=sorted(models, key=lambda row: row["model_id"]),
        )
    else:
        document = json.loads(DOCUMENT.read_text())
    generated, digest = generate(document)
    encoded = json.dumps(document, sort_keys=True, indent=2) + "\n"
    if args.check:
        if MIGRATION.read_text() != generated or DOCUMENT.read_text() != encoded:
            raise SystemExit("Native pet artifacts differ from regeneration")
    else:
        DOCUMENT.write_text(encoded)
        MIGRATION.write_text(generated)
    print(f"126 companion pet models; source_sha256={digest}")


if __name__ == "__main__":
    main()
