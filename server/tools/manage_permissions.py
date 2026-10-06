"""Offline operator tool for roles and scheduler credentials; never prints secrets."""
import argparse
import os
from pathlib import Path
from wakfu_server.command_permissions import set_admin
from wakfu_server.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        default=os.environ.get("WAKFU_DATABASE_URL"),
        help="PostgreSQL connection configuration; defaults to WAKFU_DATABASE_URL",
    )
    commands = parser.add_subparsers(dest="action", required=True)
    role = commands.add_parser("role")
    role.add_argument("--account-id", type=int, required=True)
    role.add_argument("--admin", choices=("yes", "no"), required=True)
    role.add_argument("--operator", required=True)
    role.add_argument("--reason", required=True)
    scheduler = commands.add_parser("scheduler-token")
    scheduler.add_argument("--account-id", type=int, required=True)
    scheduler.add_argument("--output", type=Path, required=True)
    scheduler.add_argument("--ttl-seconds", type=int, default=604800)
    args = parser.parse_args()
    if not args.database:
        parser.error("Provide --database or WAKFU_DATABASE_URL")
    store = Store(args.database)
    try:
        if args.action == "role":
            set_admin(
                store,
                args.account_id,
                args.admin == "yes",
                operator=args.operator,
                reason=args.reason,
            )
            print("Role updated and audited.")
        else:
            if not 60 <= args.ttl_seconds <= 31536000:
                parser.error("TTL must be between 60 seconds and one year")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation prevents silently overwriting a deployed credential.
            descriptor = os.open(
                args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            token = None
            try:
                with os.fdopen(descriptor, "w") as stream:
                    token = store.issue_token(
                        args.account_id, "scheduler", ttl=args.ttl_seconds
                    )
                    stream.write(token + "\n")
            except Exception:
                if token is not None:
                    store.revoke_token(token)
                args.output.unlink(missing_ok=True)
                raise
            print("Scheduler credential written to protected file.")
    finally:
        store.close()


if __name__ == "__main__":
    main()
