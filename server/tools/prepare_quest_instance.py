"""Compile a reviewed quest arena into a frozen existing-runtime configuration.

This only writes requested source artifacts. Installation/restart belongs to the
normal authorized release workflow; captures or private runtime paths are not
required. Species/counts are reviewed reconstruction, never official formations.
"""

import argparse
import json
from pathlib import Path

from wakfu_server import generic_transports
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.dungeon_runtime_config import require_monster_admission
from wakfu_server.monsters import reference
from wakfu_server.quest_instance_configuration import compile_profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--migration", type=Path)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text())
    configuration = compile_profile(
        profile,
        geometry=published_geometry(profile["map_id"]),
        exploration=json.loads(
            (args.profile.parent / profile["exploration_file"]).read_text()
        ),
        sources={
            (row["map_id"], row["id"]): row for row in generic_transports._CATALOG
        },
        monster=reference(profile["monster_reference"]),
    )
    require_monster_admission(configuration)
    args.output.write_text(
        json.dumps(configuration, ensure_ascii=False, indent=2) + "\n"
    )
    if args.migration:
        from build_physical_dungeon_configuration import migration

        args.migration.write_text(
            "-- Reviewed reconstructed quest instance; no player/progress writes.\n"
            + migration(configuration)
        )
    print(
        json.dumps(
            dict(
                route=configuration["route"]["key"],
                version=configuration["version"],
                official=False,
            )
        )
    )


if __name__ == "__main__":
    main()
