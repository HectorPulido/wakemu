#!/usr/bin/env python3
"""Extract the Celestial Dojo lesson scene markers from the official capture.

Family 330 is the native state-carrier sprite presentation bound to a cell. The
official dojo lessons publish these markers around the bound sack; the local
server publishes none of them, which is why the lesson floor is blank and the
sack looks like an ordinary potato sack.

Output is sanitized: graphic references, cells, counts and the first frame that
carried each marker. No account identity or raw packet is written.
"""

import argparse
import base64
import collections
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server"))

from tools.extract_rii_los_areas import _fields, _signed  # noqa: E402

LESSONS = (
    (1, "1552064409", 10574, "orientation"),
    (2, "1552064413", 10575, "elements"),
    (3, "1552064417", 10576, "distance"),
    (4, "1552064422", 10608, "line_of_sight"),
    (5, "1552064435", 10609, "areas"),
    (6, "1552064442", 10610, "displacement"),
    (7, "1552064448", 10611, "states"),
)
# Hero bootstrap carriers appear on the hero's own cell in every lesson and are
# not lesson markers; the sack cells come from the fight bootstrap.
HERO_CELL = (0, -10, 0)
SACK_CELLS = frozenset(
    {(0, -13, 0), (1, -13, 0), (0, -14, 0), (-1, -13, 0), (0, -12, 0)}
)


def _inbound(analysis):
    result = {}
    with (analysis / "inbound.jsonl").open() as handle:
        for line in handle:
            row = json.loads(line)
            result[row["frame_index"]] = row
    return result


def markers_for(analysis, fight_id, target_cells):
    inbound = _inbound(analysis)
    fights = json.loads((analysis / "airyna-seven-fights.json").read_text())
    seen = collections.Counter()
    first = {}
    for frame in fights[str(fight_id)]:
        if frame.get("direction") != "in":
            continue
        row = inbound.get(frame["frame_index"])
        if not row:
            continue
        fields = row.get("fields") or {}
        payload = fields.get("hwM")
        if fields.get("mzM") != 330 or not isinstance(payload, dict):
            continue
        try:
            data = _fields(base64.b64decode(payload["base64"]))
            graphic = data.get(3)
            position = _fields(data[5])
        except (KeyError, TypeError, ValueError):
            continue
        if graphic is None or not isinstance(data.get(5), (bytes, bytearray)):
            continue
        cell = (
            _signed(position.get(1, 0)),
            _signed(position.get(2, 0)),
            position.get(3, 0),
        )
        key = (graphic, cell)
        seen[key] += 1
        first.setdefault(key, frame["frame_index"])
    output = {"target": [], "approach": [], "hero_bootstrap": [], "other": []}
    for (graphic, cell), count in sorted(
        seen.items(), key=lambda row: (row[0][1], row[0][0])
    ):
        entry = dict(
            graphic=graphic,
            cell=list(cell),
            publications=count,
            first_frame=first[(graphic, cell)],
        )
        if cell == list(HERO_CELL):
            output["hero_bootstrap"].append(entry)
        elif cell in target_cells:
            output["target"].append(entry)
        elif cell[2] == 0:
            output[
                "approach" if abs(cell[0] - 0) + abs(cell[1] + 13) <= 6 else "other"
            ].append(entry)
        else:
            output["other"].append(entry)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture",
        default=str(
            Path.home() / "Documents/Wakfu-captures-private/official-incarnam-20261112"
        ),
    )
    parser.add_argument(
        "--output",
        default=str(
            REPO
            / "agents_docs/reports/quest-reconstruction/dojo-scene-markers-20261112.json"
        ),
    )
    args = parser.parse_args()
    analysis = Path(args.capture) / "analysis"
    document = {
        "schema": "wakemu.rii-dojo-scene-markers-v1",
        "authority": (
            "official 2026-11-12 session; family 330 state-carrier sprite "
            "presentations observed inside each lesson fight"
        ),
        "note": (
            "hero_bootstrap markers ride the hero's own cell in every lesson and are "
            "not lesson geometry; target marks the bound sack cells; approach cells are "
            "the reviewed floor guidance around them"
        ),
        "lessons": [],
    }
    for number, fight_id, objective, name in LESSONS:
        cells = (
            SACK_CELLS
            if number != 5
            else {(0, -13, 0), (1, -13, 0), (0, -14, 0), (-1, -13, 0)}
        )
        lesson = dict(
            number=number,
            fight_id=int(fight_id),
            objective=objective,
            name=name,
        )
        lesson.update(markers_for(analysis, fight_id, {tuple(c) for c in cells}))
        document["lessons"].append(lesson)
        print(
            f"leccion {number} {name}: objetivo={len(lesson['target'])} "
            f"acercamiento={len(lesson['approach'])} heroe={len(lesson['hero_bootstrap'])} "
            f"otras={len(lesson['other'])}"
        )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(document, indent=2) + "\n")
    print("especificacion escrita en", args.output)


if __name__ == "__main__":
    main()
