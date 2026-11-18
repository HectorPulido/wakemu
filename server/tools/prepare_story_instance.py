"""Compile reviewed story sources; do not install data or restart services."""

import argparse
import hashlib
import json
from pathlib import Path

from wakfu_server import generic_transports
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.owned_story_configuration import compile_story, compile_object_trials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directory = args.manifest.parent
    manifest = json.loads(args.manifest.read_text())
    controller = json.loads((directory / manifest["controller_file"]).read_text())
    native_file = directory / controller["native_sources"]["path"]
    if not native_file.exists():
        native_file = (
            Path(__file__).parents[1]
            / "wakfu_server/maps/owned_story_profiles"
            / controller["native_sources"]["path"]
        )
    if (
        hashlib.sha256(native_file.read_bytes()).hexdigest()
        != controller["native_sources"]["sha256"]
    ):
        raise ValueError("Reviewed story native descriptor source changed")
    common = dict(
        exploration=json.loads((directory / manifest["exploration_file"]).read_text()),
        geometry=published_geometry(manifest["map_id"]),
        sources={
            (row["map_id"], row["id"]): row for row in generic_transports._CATALOG
        },
    )
    if manifest.get("content_policy") == "owned-object-trials-v1":
        configuration = compile_object_trials(manifest, trials=controller, **common)
    elif manifest.get("content_policy") == "owned-story-narrative-v1":
        configuration = compile_story(
            manifest,
            controller=controller,
            encounters=None,
            monster=None,
            **common,
        )
    else:
        from wakfu_server.monsters import reference
        from wakfu_server.dungeon_runtime_config import require_monster_admission

        configuration = compile_story(
            manifest,
            controller=controller,
            encounters=json.loads(
                (directory / manifest["encounters_file"]).read_text()
            ),
            monster=reference,
            **common,
        )
        require_monster_admission(configuration)
    args.output.write_text(
        json.dumps(configuration, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            dict(
                route=configuration["route"]["key"],
                version=configuration["version"],
                rooms=len(configuration["compiled_plan"]["rooms"]),
                official=False,
            )
        )
    )


if __name__ == "__main__":
    main()
