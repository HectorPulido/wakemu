"""Bounded cleanup of this probe's exact disposable PostgresCase namespace."""
import re
from psycopg import sql


def empty_owned_schema(store, schema):
    if not re.fullmatch(r"case_[a-f0-9]{32}", schema):
        raise ValueError("Refusing cleanup outside one owned PostgresCase schema")
    with store.connection() as db:
        tables = db.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname=%s", (schema,)
        ).fetchall()
    for row in tables:
        # Commit every table so the single DROP SCHEMA does not reserve all
        # relation locks at once in the deliberately small local QA database.
        with store.connection() as db:
            db.execute(
                sql.SQL("DROP TABLE IF EXISTS {}.{} CASCADE").format(
                    sql.Identifier(schema), sql.Identifier(row["tablename"])
                )
            )
