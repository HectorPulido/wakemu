# Native dungeon name index

`server/tools/export_native_dungeon_index.py` links every reviewed guide against the complete native dungeon catalog in one operation. It produces a separate evidence index and does not change compositions or runtime data.

The localization contract is verified from client bytecode: `bqf.getName()` calls `aTF.a(137, eQL.d())`; `bpU.DK(int)` uses the same content category. Native definition IDs therefore select `content.137.<id>` in `texts_fr.properties`. The `bam` loader passes `aKU.d()` to the native dungeon constructor.

Matching checks the reviewed guide name and the canonical website title. Only a trailing `Niv.<number>` display suffix is removed. Case, accents, punctuation, articles, translations and spelling remain significant. Duplicate matches remain ambiguous; unmatched entries retain no selected definition ID.

The current private export is `.runtime/local/methodwakfu-dungeons/native-dungeon-index.json`: 151 native definitions have French names; 66 of 87 guides have a unique exact match, 21 remain unmatched, and none is ambiguous. Each candidate preserves native fields, including map and species lists. Those lists do not establish room compositions, placements, levels or progression rules. Source paths and SHA-256 hashes accompany the export.

Reproduce from the repository root:

```sh
python3 server/tools/export_native_dungeon_index.py \
  --definitions .runtime/local/review-continuacion-20261004/dungeon-definitions-private.json \
  --i18n client/contents/i18n/i18n_fr.jar \
  --catalog .runtime/local/methodwakfu-dungeons/composition-catalog.json \
  --canonical-index .runtime/local/methodwakfu-dungeons/canonical-index.json \
  --output .runtime/local/methodwakfu-dungeons/native-dungeon-index.json
PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_native_dungeon_index.py -v
```

The four regression tests pass. They cover exact evidence preservation, ambiguity, rejection of guessed typography matches and suffix boundaries. This establishes catalog linking only; it does not establish that dungeon entry or room encounters are playable.
