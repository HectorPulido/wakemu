"""Install the reviewed H.O.T. interaction for a specific imported client revision."""
import argparse
import os

from wakfu_server.postgres import Database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--revision", required=True, help="SHA-256 of imported native quest export"
    )
    args = parser.parse_args()
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db:
            source = db.execute(
                "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=1197",
                (args.revision,),
            ).fetchone()
            if source is None or {x["d"] for x in source["data"]["native"]["cjJ"]} != {
                2157
            }:
                raise ValueError("Missing or incompatible mission 1197 metadata")
            expected = (
                507,
                18153,
                0,
                0,
                -5,
                -57,
                -2,
                "GenericActivableInteractiveElement",
                4,
                15862,
                1,
                1197,
                2157,
                args.revision,
                "Reconstructed: native template 113, action 66 and item cost; objective association from mission text and active criterion.",
            )
            db.execute(
                "INSERT INTO quest_interactive_bindings "
                "(map_id,object_id,action_id,parameter,x,y,z,object_type,max_distance,required_item,required_quantity,quest_id,objective_id,revision,evidence) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (map_id,object_id,action_id,parameter) DO NOTHING",
                expected,
            )
            row = db.execute(
                "SELECT * FROM quest_interactive_bindings WHERE map_id=%s AND object_id=%s AND action_id=%s AND parameter=%s",
                expected[:4],
            ).fetchone()
            keys = (
                "map_id",
                "object_id",
                "action_id",
                "parameter",
                "x",
                "y",
                "z",
                "object_type",
                "max_distance",
                "required_item",
                "required_quantity",
                "quest_id",
                "objective_id",
                "revision",
                "evidence",
            )
            if tuple(row[k] for k in keys) != expected:
                raise ValueError(
                    "Existing H.O.T. binding conflicts with reviewed policy"
                )
            print("Installed H.O.T. quest binding 1197/2157 at 507:18153")
    finally:
        database.close()


if __name__ == "__main__":
    main()
