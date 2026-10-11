# Current-source class book and area regression triage

This investigation uses current source and the published PostgreSQL catalog,
without changing catalog activation or services. Fresh delegated execution:
`.runtime/full-regression-20261010/fresh-source-triage.log`.

## Source-correct test repairs

* Heart Blood: the unchanged AP1/MP0/WP1 cost now also reports empty extra-resource
  maps. Both exact expected dictionaries include these fields; payment,
  consumption, armor and usage-limit assertions remain. Fresh result:3/3 passed.
* Original-controller hours: configured area application can use native immediate
  opcode12613, whose class/body offsets are13/19 rather than13497's12/18.
  The test decodes the actual opcode and continues checking family1008, original
  wire caster, redirected owner, direction, affiliation and removal.4/4 passed.
* Wall area damage: typed Qq targets have native null baB locator, so the audited
  native facing contract is FRONT and does not emit back-hit29. An area direction
  is not an actor locator. The test retains actual wall PA damage, identity and
  HP-zero footprint checks.9/9 passed.

## Copied book: actual catalog completeness defect

Published revision:
`13c8122abba26ca40757c48df137540a5f0e6defdc6676cde6fd19ac6b84b33d`.
`native-class-copy-book-flags.json` SHA256:
`45ad71dae33829824da10f3b1e7c1929a74f171dd82bf12383a34fb00c62eb15`.
It contains813 references and lacks universal owned passives4956,4957,4958,
5144,5145,5146,5237,5621. The fresh coverage test fails144 subcases across18classes.
This is not a test-only mismatch: copied runtime book construction requires
native flags for the complete actual owned inventory and correctly rejects an
unknown entry.

The existing original-client export already proves821 rows with zero missing;
no new JVM export is needed. The current published document passes the existing
strict merge validator against that candidate: all813 existing flags, constructor
bounds and provenance remain identical. Current-base preparation artifacts:

* `.runtime/class-book-review-20261010/authority.json`
* `.runtime/class-book-review-20261010/copy-flags-plan.json`
* `.runtime/class-book-review-20261010/native-class-copy-book-flags-candidate.json`

Candidate SHA256:
`c2cf2511e55050c01bf666c0a783878b339f5eb2e7d18ada88ac187e221a36ac`.
The earlier staged879c0 release has an obsolete base. Restage the candidate using
`stage_native_copy_book_flags.py` and the current exact revision fence before
coordinated activation. This investigation has neither staged nor activated it.

## Summon entry

The current sphere integration still reports11 registered areas where the test
requires13 class-owned hours plus two environmental areas. The full13-hour
assertions remain intact. Actual selected cell and clipping diagnostics are
pending; this case is not marked validated.

The fenced staging command for the current base is:

```sh
PYTHONPATH=server:server/tools /tmp/wakemu-combat-review-venv/bin/python3 \
  server/tools/stage_native_copy_book_flags.py \
  .runtime/class-book-review-20261010/native-class-copy-book-flags-candidate.json \
  --expected-revision 13c8122abba26ca40757c48df137540a5f0e6defdc6676cde6fd19ac6b84b33d \
  --dsn 'host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu' \
  --password-file .runtime/local/secrets/postgres-password
```

Staging must be serialized with other catalog-heavy validation. It creates a
complete immutable release and verifies its full manifest; it never updates the
active pointer. Coordinated activation and the complete server build remain
with the parent release owner.

## Current-base staged result

Authorized staging completed as revision
`43ede6f86340a57ad3acd32a15ad48b892ff1a526a64ebc7c8937518e9bdac07`.
The complete7484-document manifest differs from the exact13c8122 base only at
`native-class-copy-book-flags.json`. Canonical staged metadata SHA256:
`a0c040686424b660220e7ccc7b34cdf30603e8e7c6153ab0e5711de138d46b1d`.
All821 flags are present. A separate read-only PostgreSQL verification confirmed
release completeness, manifest equality outside that single document, and the
unchanged active pointer. Evidence:
`.runtime/class-book-review-20261010/staged-verification.json`.

The earlier candidate-file SHA differs only because the staging tool applies its
canonical sorted compact serialization. The strict semantic merge was verified
before staging. Runtime coverage against the staged revision is delegated;
activation is still pending coordinated release verification.

Staged runtime qualification is complete: delegated
`test_combat_character_copy_runtime_book` passed5/5 using a pre-import pinned
`native_catalog.release()` callback for43ede6. No active revision was changed.

## Corrected sphere fixture contract

The initial13-area assumption mixed two native steps. Fresh313199 installs twelve
hours1546–1557 through directional point groups. The existing compact fixture's
random5–7 minimum yielded125 selected cells; three native group coordinates were
outside that selected region, so313214/313216/313219 correctly dispatched no
children. This does not demonstrate a production group or area-creation defect.

Center1558 is separately produced by state group313305→313306→313307→313308.
The actual criterion is `IsOwnSpecificArea(1557)`. Native eOF tests the selected
areaPV, or its explicit cell form; an ordinary actor recipient is not an areaPV.
This supersedes the preliminary hypothesis that merely standing on an hour would
satisfy the criterion. The actual source trace has313306 targeting actor7 and
returning false, so no313308 execution is expected from that branch.

The revised fixture retains production compact terrain with the supported
15×15 minimum and deterministic variation. A pure selection against the exact
published1134 geometry returns225 cells at the same summon center(-11,-7,-1),
with every native clock point present. The runtime test asserts twelve initial
hours, then executes actual native400 producer352198 on the registered owned
hour1557. Its2251 event passes through real Qq/Qf replay; only after that event
does the test require all13 hours and verify center delivery/removal. It retains
the border/environment checks and does not insert an event or center directly.
The delegated terminal run still reports14 total areas: all twelve initial hours plus the two environment areas, but no center after the attempted2251 route. The original15-area acceptance assertion remains intact. This is unresolved historical Xelor coverage; no production defect or successful center creation is certified by this fixture.
