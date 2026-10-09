# MethodWakfu dungeon composition extraction

The archive is stored under `.runtime/local/methodwakfu-dungeons/`. Each downloaded guide has its own directory containing the article and downloaded images. Keep captures and downloaded content in `.runtime`; do not commit the full articles or images.

The output contract is [dungeon-room-composition.schema.json](../../server/protocol/dungeon-room-composition.schema.json). Produce one JSON file per dungeon under `.runtime/local/methodwakfu-dungeons/compositions/<slug>.json`. These files are evidence artifacts, not executable spawn definitions.

## Extraction instructions for Luna

1. Read the archive manifest first. Confirm that the guide downloaded successfully. Read its article text and HTML, then inspect every image associated with a room. Images can contain the only evidence of monster counts.
2. Record the guide URL, archive directory, retrieval timestamp and SHA-256 of the archived article. Copy publication/update dates and game version only when explicitly stated. A recent download does not prove that the guide describes the current client.
3. Extract rooms in their stated order. Preserve labels from the guide. Do not assume that an unlabeled image is a room or that image order proves room order. Record ambiguity in `unresolved_questions`.
4. For each room, identify each monster species and its explicitly shown count. An image may support counting only if the species and every visible member are distinguishable. Do not derive counts from the dungeon bestiary, overall species list, boss mechanics or a screenshot of an incomplete combat.
5. Set unavailable counts, reference IDs and levels to `null`; include their field names in `unknown_fields`. Use `role: "unknown"` when the source does not establish whether an actor is a boss. Names alone do not establish native reference IDs: verify them against the client catalog and attach separate `client_catalog` evidence.
6. Attach evidence to each room and monster. `source_url` identifies the original source; `archive_path` identifies the local article/image/catalog; `locator` identifies the heading, paragraph, image region or catalog entry. Text excerpts should be short and limited to what supports the claim. Image evidence may use a null excerpt.
7. Use `composition_status: "complete"` only when all species and their counts are established. Unknown levels or unmatched reference IDs still prevent importing a runtime encounter even if the room composition is complete. A partial composition must preserve known facts without filling gaps.
8. Keep client definition ID, entry template ID and asset map ID distinct. Leave each null until separately verified. Set `client_version_match: "unverified"` unless positive version evidence exists. Do not transform a guide's stated recommended player level into monster levels.
9. Do not invent spawn positions, gates, victory requirements, difficulty scaling or progression rules. This schema deliberately does not supply those runtime fields. Record necessary missing information in `unresolved_questions`.
10. Validate each JSON against the schema. Check semantic invariants as well: room orders must be unique and increasing; any known maximum level must be at least the known minimum; `unknown_fields` must agree with null fields and unknown role; complete room compositions must have at least one monster and known counts. Mark `reviewed` true only after an independent review.

## Offline validation

From the repository root, with `jsonschema` available:

```python
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

schema = json.loads(Path("server/protocol/dungeon-room-composition.schema.json").read_text())
Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema, format_checker=FormatChecker())
for path in Path(".runtime/local/methodwakfu-dungeons/compositions").glob("*.json"):
    validator.validate(json.loads(path.read_text()))
```

Schema validation checks structure and value types. It does not establish factual correctness or replace the semantic and independent evidence review above.
