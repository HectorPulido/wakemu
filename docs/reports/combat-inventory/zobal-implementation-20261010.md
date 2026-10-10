# Zobal implementation and acceptance — 2026-10-10

Work requested after the six user-provisionally accepted classes. Zobal is not yet user accepted; the project remains **6/18**. This report separates local implementation, staged catalog changes, automated evidence and client acceptance.

## Corrected shared dependencies

- Generic characteristic 35 writes now synchronize `Actor.initiative` with native effect stats. This prevents snapshot disagreement during the next real turn without changing the current timeline order. Application/removal and wire snapshots pass the 24-test stat/snapshot suite.
- The class-copy metadata omitted eight universal passive references present in current owned books. The native exporter now unions the current complete owned roster with class/grant roots. All 813 previous rows remain unchanged; the corrected document has 821 rows and zero missing. See [copy metadata provenance and staging](copied-class-book-scope-20261010.md).
- The complete catalog is staged as `879c0fcabd8e195869bff59f451605017b52666970643af8e1a912cb73ad6a51`, based on current active `a3272ec3b722c5923cdfb619041bab41a14c85d9838364440e5f71b9b2254095`. It preserves all 7483 documents and replaces only `native-class-copy-book-flags.json`. It is **not activated**. Local code and the staged release must be delivered together; the old active catalog still rejects the copy.

## Bounded automated evidence

The current owned-active audit covers six legal deck/Ready contexts at levels 20, 90 and 200: 56 spell-level pairs, 52 prepared and committed successfully, zero transaction failures. Four pairs (7086 and 7087 at levels 90/200) need specialized contexts rather than broader target searching; they are not counted as successful casts.

After the initiative correction, all 27 legal one-passive initialization/real turn-cycle cases complete with no failures and stable source/tool hashes. This verifies lifecycle stability, not every passive trigger or numerical outcome.

The native copy lifecycle now creates profile2382, reaches the copied fighter turn, commits allocated-book action7066, rejects foreign source/raw UIDs, and serializes checkpoints. The root corrected-document replay has stable source hashes. Independent staged-release replay confirms the same positive path and the seven focused copy/staging tests pass; its global source-stability flag is false only because the unrelated mining module changed concurrently. Copy retirement/QI release was also exercised by a separately labelled trusted PA lethal stress, not a normal class-spell kill.

Mask probes verify base grants7081/7082/7083/8559, passive7104 substitution of7081 by7226, legal granted casts, primary states and turn-derived charges9247/9248/9249. Primary masks last two turns and may coexist by native definition. Bonus6614/6615/6616 replacement applies to other eligible player/companion allies within radius four; self is excluded. See the [native audit](zobal-current-audit-20261010.md). Durable allied-recipient mask tests now pass with and without passive7104.

## Delivery and acceptance boundary

No service was restarted or deployed by this workstream. The active catalog was not switched. The combined local gate passes **170 tests, zero failures/errors/skips** against the complete staged catalog. It includes all six provisionally accepted classes, area/target selection, Sacrifice, healing, resurrection, copied books and Zobal special contexts. The gate includes the event-bound zero-selector regression. Danza Macabra7086 revives a genuinely killed allied player with positive HP, state1144 and restored timeline membership, while preserving the source transaction. Acrobatismo7087 relocates to the legal empty cell at exact range six.

The selector correction distinguishes fresh actor-group criterion searches from already transmitted leaf/event recipients. Point ally-area selectors preserve a rebound selected recipient; other point selectors retain their relationship rules. The first broad implementation failed Sacrifice and mask replacement regressions; those failures were resolved before the passing combined gate. No class-ID or spell-ID exception was added.

The [manual battery](zobal-manual-acceptance-20261010.md) includes exact setup commands and every owned active/passive. Four passives (7095/7103/7106/7113) have published push/collision event branches with literal `False` criteria; those branches remain inactive, while their independent stat roots still execute normally. Initialization checks for the other passives do not prove every numerical/event branch. The local implementation and catalog are ready for deployment review and manual validation; this is not a claim of 100% gameplay acceptance. Client rendering, party control, reconnect and real fight-end cleanup remain manual acceptance requirements.

## Reproduce the local regression gate

Run from the repository root with the existing PostgreSQL credentials. This command does not restart services or activate a catalog:

```sh
PYTHONPATH=.:server:server/tests:server/tools \
WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu' \
WAKFU_DATABASE_PASSWORD_FILE="$PWD/.runtime/local/secrets/postgres-password" \
WAKFU_TEST_GRANTEDCAST=1 \
/tmp/wakemu-combat-review-venv/bin/python3 server/tools/validate_zobal_runtime.py \
  --catalog-release 879c0fcabd8e195869bff59f451605017b52666970643af8e1a912cb73ad6a51
```

Evidence remains private in `.runtime/zobal-review-20261010/delivery-gate.log`. Deploy the complete shared checkout together with the staged catalog; do not overlay these files on an older image. The staging tool and provenance report describe the catalog content and immutable base.
