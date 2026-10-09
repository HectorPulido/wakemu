# Shared class summon and beacon lifecycle boundaries

## Native local and global events

Summons created by eZl307 are eGj fighters with the same eZV/Qf manager as ordinary fighters. `eGj.a(BitSet,Qe,byte)` forwards directly to `drJ().a(...)`; there is no summon, master or controller filter. `Qe.L` sends local caster channels 10/20/30/40 and target channels 1/2/3/4. A summon recipient stays the summon; it is not replaced by its controller. Physical carry relationships are a separate authority boundary.

`eZR.L` then invokes the fight iterator for global channels 11/21/31/41. Registered summons are included in the fighter population. An audited native global iterator order is still required when several matching listeners can observe a source. Timeline insertion order alone does not prove that iterator order; a beacon excluded by property114 is still a registered fighter and potential event manager.

The existing blanket rejection of identities in `native_summon_registrations` is a policy guard, not a native event restriction. `RegisteredSummonAuthority` already validates owned registrations and composes ordinary actors with summons. Its creation producer must expose all native relationships before the shared event producer can use it safely.

## Fresh creation relationship proof

The installed client `big.a(long,aBn,short,eHD,SQ,boolean,eHN)` first looks up the UID. A missing UID creates a new `bje` via `bje.dsi()` (`new bje`, not a pooled existing actor). Fresh pGW/pGV carry relationships are null. Existing-UID recreation is a distinct contract and must remain unsupported by a fresh-only producer.

`big` creation chooses the new summon as controller when selfControlled is true; otherwise it chooses the immediate caster. It registers that exact actor through `fcb.a(newActor,team,true,controller)` → `fdt.a(...)`. The native fdy constructor stores controller.Sn in both `saH` and `saJ`:

- `dpr` / `dTD`: `big.dnH` → `fcb.aV` → fdy.saH → direct registered actor.
- `dpu`: `big.dnG` → `fcb.aU` → fdy.saJ → direct registered actor.

Both initially identify the immediate controller, including the summon itself in selfControlled mode. Native controller lookup does not recursively walk the summon root. A later `fdt.e(controlled,controller)` updates mutable saJ/dpu while saH/dpr stays unchanged. Thus controller, current master and recursive summon root need separate fields.

Current `NativeSummonBuilder` computes `controller_id` and targeting.dpu_id, but leaves `NativeActorAuthority.native_controller_id` at None and targeting.dpr_id absent. Registration retains controller_id in its row but lacks validation against later explicit carry/master mutations. A general repair should populate direct controller metadata and separately attest fresh null pGW/pGV. Missing or changed relationships need updated native producers or explicit rejection, rather than stale creation defaults.

## Creation effect lifecycle and packet ownership

`eZl.bbA=false`, `bbB=true`: it is a cell effect. `eZl.bbx` preserves base event0 and adds event2130; producing summon effects should pass the shared Qe lifecycle with those IDs and native masks. The current effect factory does not attach event_lifecycle to the summon handler. Creation itself and later events from the summon are separate gaps.

`eZl.c` constructs/registers the creature, applies descriptor transformations and orientation, and records its UID separately from the running effect UID. Additional data encodes the creature ID through ProtoRunningEffect field12 / iR field4. Keep effect identity, creature identity, controller identity and Qf owner separate.

`eZl.bbF` calls parent cleanup and clears its descriptor fields; it does **not** remove the created creature. Retained/subscribed creation needs a retained running-effect record with the native actor UID additional data and clone/application lifecycle. Removing that record must not implicitly unsummon. Native creature removal requires its own producer and timeline/controller cleanup contract.

## Impact-first modular order

1. Complete fresh summon relationship authority and live snapshot validation; allow shared local Qe events for every owned registered summon/beacon under that authority.
2. Attach the generic event0/2130 lifecycle to summon creation; verify event timing and reaction order without creature spellcasting or AI.
3. Implement central retained/subscribed summon creation records and packet owner normalization, preserving the separate creature lifetime.
4. Verify movement, damage, state, glyph/beacon interactions and removal across the registered roster. Require actual native iterator order for competing global reactions.
5. Implement class-specific control/commands and creature abilities only after these shared foundations pass.

Other general guards remain: property callback effects reject summoned actors and mixed rosters; summon-count predicates become unknown when registrations exist; cosmetic-copy branches have explicit missing-source guards. These must be inventoried separately rather than hidden by lifting the local event guard.

## Fresh authority repair

The fresh creator now supplies explicit native_controller_id and native_master_id, dpr/dpu metadata and empty physical-carry fields, plus the new-bje/fdt creation provenance. Registration and every registered-authority read revalidate these facts against the source. Changed master/carry relations remain rejected until their separate native producers exist; missing legacy facts are not backfilled. Both AP and range modifier snapshots must be complete. Six focused tests cover direct/self control, controller/root distinction, changed master, physical carry, legacy facts and independent range snapshots.

The local lifecycle guard removal and broader summon event/retention integration remain separate parent-owned work.

No monster spell or AI implementation, runtime execution, Docker, DB or world changes were made. Investigation used targeted native javap files and current creation/authority/event modules.
