# Validated low-level monster deployment

Deployed locally on 2026-10-10 at approximately 22:30 UTC. Active catalog revision:

`c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`

## Result

All 30 fully validated references are active. Of 69 static candidates whose entire level range is 1–9, 39 remain disabled; 21 have native initial states lacking an ordinary-NPC construction producer. Other pending cases include incomplete casting authority, unproven resistance/condition semantics, encounter-specific scenarios and resource constraints. Static family coverage is not a gameplay certificate.

The complete [JSON inventory](ACTIVATION_STATUS.json) and [CSV inventory](ACTIVATION_STATUS.csv) contain 2,874 references: 30 activated, 39 pending and 2,805 inventory-only. High-level and epic references were not activated.

Enabled native references:

```text
2, 6, 39, 2089, 2105, 2205, 2245, 2253, 2373, 2428,
2598, 2612, 2616, 2624, 3114, 3236, 3237, 3259, 3278, 3766,
4010, 4011, 4691, 5455, 5456, 5525, 5526, 5527, 5590, 5704
```

## Validation evidence

- Final baseline and candidate: **179 tests passed each**, no failures/errors/skips, no added failures. The suite includes Huppermage, Sram and Feca. Both receipts have matching runtime and test-dependency hashes.
- All 69 candidates were evaluated across **169 actor-level/spell cases**; 129 cases were effectful. A reference passes only when every owned spell at every selected native actor level passes and initialization is supported.
- All 30 passing references passed AI forecast source isolation, serialized commit with observable actor changes, retained actor identity, and rollback after an injected serializer failure.
- Post-deployment, the actual AI container's `NativeOracle.cast` executed an effectful cast for **all 30 enabled references**, producing packets without mutating the source fight. The probe read the active catalog and used the deployed engine, without an in-process candidate overlay or live player fights.
- Final activation-tool suite: **83 tests passed**.
- World and AI images matched 633 current server source files each; ecology matched 632. All images passed Python compilation. `world`, `ai` and `ecology` are healthy and pinned to the same active release; world HTTP health returned `ok: true`.

Only `native-npc-spell-effect-trees.json` and `native-class-casting-roots.json` changed in the catalog; **7,482 other documents retain their exact published hashes**. Existing casting-root entries and NPC baseline effects were preserved. The complete shared checkout was built, including concurrent class implementations. Normal startup also applied the checkout's additive dungeon branch-selection migration; no separate monster-specific database schema was introduced.

Private receipts are retained in `.runtime/monster-activation-under10-final-20261010/`: execution validation, source hashes, staging/activation receipts, image proof, deployment receipt, deployed-oracle results and activation-tool output. Earlier unsuccessful/unstable diagnostic receipts remain historical evidence and were not reused for certification.

The broad repository diagnostic suite is **not fully green**. Disputed legacy expectations remain unchanged and are documented in [failure investigation](FAILURE_FIX_PROGRESS.md), including explicit-PV fanout, packet envelope offsets and partial-area healing. The active copied-book flag metadata repair also remains a separate pending catalog change. Passing the selected regression suite does not erase those findings.

## Manual acceptance

Follow the [complete client test](MANUAL_ACCEPTANCE.md). Reconnect, teleport to map 1134, create the listed groups and let their turns execute while also exercising normal class spells. Visual animation and a complete live-client fight cycle still require that acceptance test.

## Rollback

The previous complete catalog remains stored as `1d428d93dd4eeea23c81d10230b33e7bfd897671930efaf8d56ac1c0e82b19f6`. Before deployment, world, AI and ecology images were preserved with tags ending `before-monster-spells-20261010`; the prior Compose file is retained privately. Rollback must stop the three affected services, guard the active pointer against the deployed revision, restore the previous complete pointer, and recreate all three with the previous images and matching catalog pins. Preserve the additive shared database migration rather than destructively reverting unrelated work.
