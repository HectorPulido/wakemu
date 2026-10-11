"""Extract numeric Stasis tooltip contracts without modifying installed client data."""
import hashlib
import json
from pathlib import Path
import re
import zipfile


def extract(root=Path("client/contents/i18n")):
    result = {"provenance": [], "locales": {}}
    for locale in ("fr", "en", "es", "pt"):
        archive = root / f"i18n_{locale}.jar"
        with zipfile.ZipFile(archive) as source:
            name = next(
                n for n in source.namelist() if n.endswith(f"texts_{locale}.properties")
            )
            payload = source.read(name)
        rows = {}
        for line in payload.decode("utf8").splitlines():
            if not line.startswith("stasis.dungeon.tooltip.bonus.type."):
                continue
            key, template = line.split("=", 1)
            # Every numeric branch includes the difficulty and template argument index.
            branches = re.findall(r"\{\[(\d+)=1\]\?[^<>]*<b[^>]*>(\d+):", template)
            if not branches:
                continue
            assert len(branches) == 40, (locale, key, len(branches))
            arrays = []
            for offset in range(0, 40, 10):
                group = branches[offset : offset + 10]
                assert [int(d) for d, v in group] == list(range(1, 11))
                arrays.append([int(v) for d, v in group])
            rows[key] = dict(
                zip(
                    (
                        "hp_percent",
                        "damage_percent",
                        "competitive_reward_percent",
                        "normal_reward_percent",
                    ),
                    arrays,
                )
            )
        result["locales"][locale] = rows
        result["provenance"].append(
            {
                "archive": str(archive),
                "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "member": name,
                "member_sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return result


if __name__ == "__main__":
    import sys

    output = Path(sys.argv[1])
    data = extract()
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    for locale, rows in data["locales"].items():
        print(locale, len(rows), "templates")
    for kind in range(5):
        variants = [
            v
            for k, v in data["locales"]["fr"].items()
            if k.startswith(f"stasis.dungeon.tooltip.bonus.type.{kind}.")
        ]
        assert variants and all(v == variants[0] for v in variants)
        print(kind, variants[0])
