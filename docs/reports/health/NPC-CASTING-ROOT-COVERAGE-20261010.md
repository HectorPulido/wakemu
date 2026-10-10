# NPC ability casting root coverage

Date: 2026-10-10. Trigger: Wonejo appeared to skip its turn after a controlled Jamajam died in fight 164.

## Actual turn sequence

At 16:14:27.577 UTC, Jamajam actor 97 used its lethal action during global turn 6. Authoritative settlement advanced to enemy turn 7 and held presentation behind acknowledgement 6. At 16:14:29.742 UTC, acknowledgement 6 released the enemy AI. Its decision took 427 ms and selected end-turn. At 16:14:29.796 UTC, acknowledgement 7 released owner 19's turn 8. There was no double turn advance in the new death acknowledgement path.

The enemy decision explicitly reported `native_casting_root_metadata_missing:7962:2:361119`, and its planner used movement-only search. The enemy's position was `(-12,-7,-1)` and owner 19 was at `(-12,-6,-1)`, with enemy AP 6. Thus an adjacent target existed; the recorded reason for not considering a cast was missing authority metadata, rather than range or a slow search.

## Root cause

Original monster reference 5525 owns ability 7962. Native `aMb.csd` ownership passes through `bbo` / `blj.du` / `bPD.a`; level parameter -1 selects the actor level. Actual native casting table level 2 has range `[1,1]`, root `[361119]`, and costs `[0,0,0]`. These values are original data, not inferred from the historical local Wonejo attack helper.

The runtime's casting-root authority loaded the class root domain, plus scoped morph and captured-class dependencies. It did not contain all ordinary NPC ability roots. As a result, the source-certified AI prerequisite check correctly rejected Wonejo's root metadata; removing that check would only move the rejection into the authoritative cast path.

## Complete original NPC domain export

The original `ExportNativeCastingRoots.java` exporter read `eVn.fKX()` and `eVn.aZF()` from the installed client for **9,213 distinct roots**, covering **3,091 monster-owned ability references** across their positive native casting table levels. There were no absent ability casting tables in this domain. Every root had an original selector.

For root 361119, the original export is:

```json
{
  "native_casting_collision_area": null,
  "native_selector_present": true,
  "native_target_selector": {"class": "fcE", "mask": 1}
}
```

The import preserves the distinction between casting collision geometry (`fKX`) and effect damage geometry (`aZP`); it does not substitute one for the other.

## Immutable staged release

`server/tools/stage_npc_casting_roots.py` stages a complete PostgreSQL catalog release without activating it. It verifies the complete exported domain, selector contracts, global metadata, unchanged class roots, and conflicting overlap. All existing **2,152 class root records** remain equal. The combined root authority contains **10,897 records**.

- Base revision: `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.
- Staged revision: `a3272ec3b722c5923cdfb619041bab41a14c85d9838364440e5f71b9b2254095`.
- Complete release documents: **7,483**.
- Only changed document: `native-class-casting-roots.json`.
- Changed document SHA-256: `bc94263a943117878238bfe04e4bb0b0500eae7e23a315bcbac1e6abbbd32d9e`.

Unchanged documents and their records are copied server-side into the new immutable release. The previous published revision remains untouched. The coordinator must activate the new complete release together with matching image revision pins; this agent did not activate or restart services.

## Validation and practical limits

Five import regression tests passed: exact class preservation and NPC selector import, missing-domain rejection, pinned monster/casting source domain derivation, conflicting-root rejection, and missing selector/global metadata rejection. The staging tool derives the expected complete domain directly from the pinned PostgreSQL monster ownership and casting documents before accepting the external export. Read-only SQL checks confirmed the actual staged database document contains all 9,213 NPC roots and preserves all 2,152 old class records. All 7,482 unchanged documents have identical source checksums, sizes, and record counts. Its full staged manifest matches the derived revision.

A separate read-only process substituted only the staged root document into the actual `casting_root_catalog()` loader. The actual `NativeOracle.native_casting_root_prerequisites` for Wonejo 5525, level 2, owned ability 7962 returned `complete=true`, `unavailable=[]`. Private evidence lives under `.runtime/local/diagnostics/npc-casting-root-export/`.

This verifies the missing-root metadata prerequisite, not every NPC effect family's complete execution. Existing authoritative legality, target selection, resources, per-action transactions, `max_actions=12`, and the owner-turn deadline remain in force. Original zero-cost abilities retain their actual costs; no invented AP cost or per-monster shortcut was added.

Manual acceptance after coordinated deployment: start a fresh Wonejo fight, leave an adjacent target alive, and pass the player turn. Confirm ability 7962 produces its native attack and HP change. Repeat after controlled summon self-defeat to verify old-turn acknowledgement, Wonejo action, and owner resumption. Test another NPC ability family to check the general domain import; unsupported effects must report their true dependency rather than silently bypass native authority.
