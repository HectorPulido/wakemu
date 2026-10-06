"""Apply the final PostgreSQL schema using private connection configuration."""
import os
from pathlib import Path
from wakfu_server.postgres import Database, migrate


def main():
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db:
            count = migrate(db, Path(__file__).resolve().parents[1] / "migrations")
        print(f"PostgreSQL migrations applied: {count}")
    finally:
        database.close()


if __name__ == "__main__":
    main()
