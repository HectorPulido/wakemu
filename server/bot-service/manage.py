"""Manage bot profiles without placing credentials in commands or output."""
import argparse
import json
import os
from pathlib import Path

from wakfu_bots.clients import JsonClient
from wakfu_bots.config import BOT_ID, validate_profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url", default=os.environ.get("WAKFU_BOTS_URL", "http://127.0.0.1:18087")
    )
    parser.add_argument(
        "--token-file", default=os.environ.get("WAKFU_BOTS_ADMIN_TOKEN_FILE")
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    put = commands.add_parser("put")
    put.add_argument(
        "--profile", required=True, help="JSON document containing one bot profile"
    )
    delete = commands.add_parser("delete")
    delete.add_argument("bot_id")
    arguments = parser.parse_args()
    if not arguments.token_file:
        parser.error("--token-file or WAKFU_BOTS_ADMIN_TOKEN_FILE is required")
    token = Path(arguments.token_file).read_text().strip()
    if len(token) < 24:
        parser.error("Management credential is invalid")
    http = JsonClient(arguments.url, token)
    if arguments.command == "list":
        result = http.request("GET", "/v1/bots")
    elif arguments.command == "put":
        profile = validate_profile(json.loads(Path(arguments.profile).read_text()))
        result = http.request("PUT", "/v1/bots/" + profile["bot_id"], profile)
    else:
        if not BOT_ID.fullmatch(arguments.bot_id):
            parser.error("Invalid bot ID")
        result = http.request("DELETE", "/v1/bots/" + arguments.bot_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
