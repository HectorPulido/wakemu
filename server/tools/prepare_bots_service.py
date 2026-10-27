"""Create dedicated local bot credentials without printing or rotating secrets."""
import argparse
import os
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secrets-dir", type=Path, default=Path(".database/secrets"))
    args = parser.parse_args()
    args.secrets_dir.mkdir(parents=True, exist_ok=True)
    for name in ("bots-world-token", "bots-admin-token"):
        path = args.secrets_dir / name
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        except FileExistsError:
            if not path.is_file() or len(path.read_text().strip()) < 24:
                raise ValueError(f"Invalid existing credential file: {name}") from None
        else:
            with os.fdopen(descriptor, "w") as output:
                output.write(secrets.token_urlsafe(48) + "\n")
                output.flush()
                os.fsync(output.fileno())
        # The bot process has this group as a supplementary group in Compose.
        # Only these dedicated bot credentials need group readability.
        os.chmod(path, 0o640)
    group_ids = {
        path.stat().st_gid
        for path in (
            args.secrets_dir / "bots-world-token",
            args.secrets_dir / "bots-admin-token",
        )
    }
    if len(group_ids) != 1:
        raise ValueError("Bot credential files must share the same group")
    print(f"Bot credentials ready; WAKFU_BOTS_SECRET_GID={group_ids.pop()}")


if __name__ == "__main__":
    main()
