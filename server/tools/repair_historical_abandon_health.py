"""Prepare/read a strict historical-return proof; writes require explicit --apply.

Run application only after the operator's database backup and service quiescence.
This tool never changes a current session, starts a service, or sends packets.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from wakfu_server.combat.combat_historical_abandon_health import (
    capture,
    digest,
    prepare,
    qualify,
    repair,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--apply", action="store_true")
    parser.add_argument("--log", type=Path, action="append", default=[])
    parser.add_argument("--account-id", type=int)
    parser.add_argument("--character-id", type=int)
    parser.add_argument("--fight-id", type=int)
    parser.add_argument("--ack-request-id")
    parser.add_argument(
        "--failed-allocation", action="append", default=[], metavar="FIGHT:REQUEST"
    )
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--expected-proof-sha256")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument(
        "--skip-already-alive",
        action="store_true",
        help="Explicitly report a proven already-living character without any write",
    )
    args = parser.parse_args()
    if args.apply and (
        not args.expected_proof_sha256 or args.backup is None or args.receipt is None
    ):
        parser.error("--apply requires pinned proof SHA, exclusive backup and receipt")
    if args.skip_already_alive and not args.apply:
        parser.error("--skip-already-alive is an explicit application-window option")
    if args.receipt is not None and args.receipt.exists():
        parser.error("Receipt already exists")
    os.umask(0o077)
    from wakfu_server.postgres import Database

    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        min_size=1,
        max_size=1,
    )
    try:
        with database.connection() as db:
            if not args.apply:
                db.execute("SET TRANSACTION READ ONLY")
            if args.prepare:
                if not args.log or any(
                    value is None
                    for value in (
                        args.account_id,
                        args.character_id,
                        args.fight_id,
                        args.ack_request_id,
                    )
                ):
                    parser.error(
                        "--prepare requires raw logs and complete explicit identities"
                    )
                records, sources = [], []
                for path in args.log:
                    data = path.read_bytes()
                    sources.append(
                        dict(name=path.name, sha256=hashlib.sha256(data).hexdigest())
                    )
                    records.extend(
                        json.loads(line) for line in data.splitlines() if line.strip()
                    )
                allocations = []
                for value in args.failed_allocation:
                    fight, request_id = value.split(":", 1)
                    allocations.append(dict(fight_id=int(fight), request_id=request_id))
                proof = prepare(
                    db,
                    records,
                    account_id=args.account_id,
                    character_id=args.character_id,
                    fight_id=args.fight_id,
                    ack_request_id=args.ack_request_id,
                    failed_allocations=allocations,
                    sources=sources,
                )
                with args.proof.open("x") as stream:
                    json.dump(proof, stream, indent=2)
                    stream.write("\n")
                result = dict(
                    qualified=True,
                    applied=False,
                    proof=str(args.proof),
                    proof_sha256=digest(proof),
                )
            else:
                proof = json.loads(args.proof.read_text())
                if digest(proof) != args.expected_proof_sha256:
                    raise ValueError("Proof differs from the operator-reviewed SHA")
                if args.apply:
                    result = repair(
                        db,
                        proof,
                        backup=args.backup,
                        skip_already_alive=args.skip_already_alive,
                    )
                else:
                    qualify(proof, capture(db, proof["character_id"]))
                    result = dict(
                        qualified=True, applied=False, proof_sha256=digest(proof)
                    )
        if args.receipt is not None:
            with args.receipt.open("x") as stream:
                json.dump(result, stream, indent=2)
                stream.write("\n")
        print(json.dumps(result, sort_keys=True))
    finally:
        database.close()


if __name__ == "__main__":
    main()
