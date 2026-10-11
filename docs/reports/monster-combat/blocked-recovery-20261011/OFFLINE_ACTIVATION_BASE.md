# Offline activation base for the1817-family-covered scope

The reusable candidate is `.runtime/monster-blocker-recovery-20261011/candidate-all-dependency-ready`, with721 selected references and declared base revision `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`. All six base-document SHA seals match the six changed-document seals in `.runtime/monster-bulk-1297-20261011/candidate-final-fede`. The latter selected607 references and declares base `fede6fdff60656b6be4d71d501d919511493407501d53f10c45c0376a1ea1a05`. Thus the exact six bd79 base raw documents are already available as candidate721's `base-*` files; no database query is needed to recover those bytes.

The six files are NPC spell trees, casting roots, summon abilities, summon initial states, state resistance and cell groups. The largest base file is44,616,693 bytes. The candidate declares7478 unchanged documents, whose raw availability is separate from their manifest seals. e18 snapshots contain only860–865 of those relative paths; they must not be described as a complete bd79 release.

`prepare_monster_spell_activation.py` currently runs Java spell extraction before its read-only PostgreSQL phase. That phase reads the active revision, document manifest, selected monster records, raw base documents, and state/effect existence. `SET TRANSACTION READ ONLY` prevents writes, but unavailable PostgreSQL still prevents this preparation path. Do not retry pools or relabel an offline fixture as an active database.

`server/tools/offline_monster_catalog.py` provides an explicit diagnostic bootstrap. It declares the offline candidate base revision, verifies every consumed document against its manifest SHA, and records actual verified raw sources separately from all declared seals. The candidate's `base-*` documents have priority. Other snapshot roots are usable only when their exact bytes (or decompressed gzip bytes) match the pinned SHA. Missing or mismatching documents fail closed and should become individual monster diagnostics.

```python
from pathlib import Path
from offline_monster_catalog import OfflineMonsterCatalog
from validate_monster_spell_activation import install_overlay

candidate = Path('.runtime/monster-blocker-recovery-20261011/candidate-all-dependency-ready')
snapshot = OfflineMonsterCatalog(candidate, [
    Path('.runtime/e18-deploy-server/protocol'),
    Path('.runtime/e18-world-live-4b1bf7092447/protocol'),
    Path('.runtime/monster-bulk-1297-20261011/candidate-final-fede'),
])
with snapshot.install():
    install_overlay(candidate)
    # Run bounded monster diagnostics with the existing validator.
receipt = snapshot.receipt()
```

Set `PYTHONPATH=server:server/tools:server/tests` when using this API. It patches only the explicit context and restores catalog functions on exit. `record` resolves through the current loader so validated candidate overlays apply. The receipt identifies `declared_offline_candidate_base_not_active_database`; this is source-qualified offline diagnostic evidence for consumed documents, not live release qualification. Final publication still requires rebasing against the then-active release.

## Explicit offline variants

The original bd79 snapshot cannot currently supply exact raw `native-spell-casting.json` or `spells.json`. Searches of named and renamed snapshots and common JSON serialization variants did not recover their expected seals. Existing bytes are therefore not silently accepted under bd79.

Two immutable private variants were produced for local qualification. The latest is `.runtime/monster-activation-1817-20261011/candidate721-offline-native-casting-spells`, declaring offline base `offline-1b7f3e39602fc8beef377dcf231164bce5cb0cf2475d3bad8a7d1a8bec40bc90`.

- Casting uses the original sealed bundle `casting.json.gz`, verified against its compressed provenance SHA, actual installed client JAR, and all three casting exporter source hashes. Its raw document SHA is `3279b05aff0d9cc6a52c7b1d3a8a5e1652eb1fe849f1d6cb5fa0d4527a8e45c1`.
- Spells use the named historical snapshot's actual native export, whose embedded client JAR and bdata66 SHA values match both installed files and the sealed bundle evidence. Its raw document SHA is `290395dcd5ad392fe4eb62f6ac4fbe8d06c1d4b19302325ec94718b5e0269432`.

Each variant manifest records its parent manifest digest, old expected seal, new actual seal, source evidence and offline-only status. Previous candidates were not edited; unchanged data files are immutable hard links and new manifests/raw replacement files are separate. Because the old active raw documents are unavailable, these variants explicitly make no claim that every historical class record was preserved against the live release. This boundary does not prevent source-qualified local monster execution; it requires a live rebase before publication.

Reproduction scripts are `.runtime/monster-activation-1817-20261011/rebase_casting.py` and `rebase_spells.py`. They require new destinations and verify their native inputs before writing. The provider's five focused tests passed, including rejected changed bytes, undeclared reads, `exists`/`open` without database access and gzip SHA qualification. The original direct bd79 attempts remain recorded separately as infrastructure failures.
