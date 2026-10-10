# Native heroes protocol and ownership

Research uses the installed Wakfu client. No service restart, deployment, or live database mutation was performed.

## Requests and acknowledgement

| Operation | Native class | Wire opcode | Body / frame |
| --- | --- | --- | --- |
| Add owned hero | `cnY` | 12219 | `>q characterId`, type3 |
| Switch controlled hero leader | `cnZ` | 12006 | `>q characterId`, type3 |
| Remove party member / hero | `Ou` | 1074 | `>qq partyId,targetId`, default type6 |
| Add result | `cwC` | 12587 | one result byte |

`cJL.addHeroToParty` emits `cnY`. Remove UI command16130 is **local**, not a wire opcode: `cJL.k` dispatches `dgH`, `ddS.pd` asks confirmation, then `bxK.kP` → `bxI.kP` emits `Ou1074`. Native default `Ou.baA=true` selects frame type6; false selects type2.

`SwitchHeroCommand.il` rejects a current fight, resolves an already loaded owned actor in `fkK`, switches local active ownership through `fkJ.av`, and sends `cnZ12006`. A network reply alone cannot compensate for missing owned actors in the client.

Result values from native `eEQ.aKg()`:

1 NO_ERROR; 2 INVITER_BAD_INSTANCE; 3 INVITED_BAD_INSTANCE; 4 LEADER_DOESNT_EXISTS; 5 SUBSCRIPTION_WEAKNESS; 6 NOT_SAME_GUILD; 7 NOT_SAME_NATION; 8 COMPANY_NOT_ACTIVATED; 9 LEADER_NOT_SAME_GUILD; 10 NULL_COMPANY; 11 FULL_OWN_PARTY; 12 NEED_RECUSTOM; 13 DEAD_PLAYER; 14 LEADER_IN_FIGHT; 15 UNKNOWN_HERO.

Native `clA` handles12587 and re-enables `bns` networking after success or failure. Rejected additions must return a native result to avoid leaving the UI disabled.

## Entitlement and company

`fkD` (SUBSCRIPTION eligibility) allows adding while own hero count is below `eEL.pcq` (`party.max.own.heroes`, config ID622, default2), provided `fkx.gdv()` is true. Otherwise the effective cap is zero.

`bns.a` sets that flag through `fkx.nc` from either:

- `fkH.gdA()`: config602 `heroes.forceAddToParty` (defaultfalse); or
- native character rights `eDv.c(eEp.oVk)`, HEROES numeric ID21.

This is not inferred booster state. Additional native settings: config431 `heroes.enabled` defaulttrue and config603 `companies.enabled` defaulttrue. `bns` has explicit leader + heroSlot0 + heroSlot1 layout.

Account COMPANY component1 is `eSJ`. Its final boolean is `aPU()` / activated, and its second long is chief character ID. Native COMPANY eligibility `fkA` requires the component and activated=true when companies.enabled is true. Existing false activation will reject additions even if subscription eligibility passes.

## Owned actor hydration

Roster23548 (`cEk`) carries a signed-byte character count, repeated `>I blobLength + entityBlob`, then a signed-byte companion count and companion records. It does not carry extra slots. Consumer `cgY` passes the roster to `biz.a`.

`biz.a` clears `fkJ/fkK`, then private `biz.dV(blob)` creates `biB(false)`, calls `fX(true)`, `fU(false)`, `as(blob)`, and registers each actor through `fkK.d(accountId,actor)`. Thus the native initial roster is the owned-actor bootstrap, not just a list of IDs and levels. Account section0 alone does not create these actors. Replaying23548 mid-session clears ownership and is unsuitable as a routine hero-add update.

World appearance12608 consumer `cgN` skips identities already registered in `fkK`; it cannot serve as creation of a second independent owned actor. Existing owned actors can receive `csZ13046`: `>q characterId`, signed `>h blobLength`, then entity blob. Native `ciu` resolves the existing owned `biB` and calls `as(blob)`.

Remote party member rows and membership publication still require the ordinary party protocol integration. The findings above do not establish that a visual world actor alone activates an owned hero or its combat control.

## Executed checks

`sniffer/java/VerifyHeroesProtocol.java` passed native request opcode identities, real12587 decoding, company activated/chief decoding, and actual `fky.SUBSCRIPTION` eligibility at entitled count0 / count2 and unentitled count0. It prints the complete native result enum. It does not execute graphics, inventory ownership switches, or combat turns.

`sniffer/java/VerifyCharacterCapacity.java` passed actual23992 `cEl` → `bkg` UI model capacity1/5/24/127 and actual23548 signed roster count127/128 boundary. Native base free slots are5; coherent roster capacity is127, even though an extra-slots byte127 could mathematically display132.

```sh
javac -proc:none -cp 'client/lib/*' -d /tmp/wakemu-rift-native-oracle sniffer/java/VerifyHeroesProtocol.java sniffer/java/VerifyCharacterCapacity.java
java -cp '/tmp/wakemu-rift-native-oracle:client/lib/*' VerifyHeroesProtocol
java -cp '/tmp/wakemu-rift-native-oracle:client/lib/*' VerifyCharacterCapacity
```

## Owned hero admission: 12093

The `cue` message (opcode 12093) carries three consecutive blocks, each prefixed
with a big-endian unsigned 32-bit byte length: entity blob, build-set
snapshot (`eQW`, `eK` protobuf), then aptitude registry (`eQJ`, `ef` protobuf). These
snapshots use the same decoders as the corresponding `csY` login fields.
`cue.dp` returns false after decoding successfully; field contents, rather than
that return value, establish successful envelope decoding.

Its actual consumer `aZr.a(cue)` constructs `biB(true)`, sets `fU(false)`, applies
the build set and aptitude registry, loads the entity and invokes `aQc()`. It registers the
actor with `cdE`, synchronizes build state through `bQm.a`, and calls
`fkw(account).bI(actor)` followed by `bJ(actor)`. The latter invokes
`fkK.ay(account, actorID)`, which inserts the hero into the active owned-character
set. If a world actor already exists, the consumer also refreshes its snapshots,
reinitializes it and hides that old world representation.

Consequently, sending only `13046` and party rows does not execute the native
owned-hero admission or activation sequence. The admission packet is required
when adding an active hero and when restoring active heroes after login.

`VerifyHeroAdmission.java` passed against the installed client for the complete
12093 envelope. Actual visual consumer execution requires the graphical client;
constructing `biB(false)` in a headless JVM aborts in native graphics code.

### Party identity and removal

The boolean immediately following the breed short in party identity section zero
is the hero flag: `fgj.a(ByteBuffer,int)` calls `fga.mX(byte == 1)`, and `fgb`
stores that value for `dpL()`. It must be true for hero rows and false for the
main character. On removal, `cZT.a(fgu,fga,boolean)` checks the owned account and
`dpL()`, then calls `fkK.az(accountID, characterID)` to deactivate the hero.
A party row published with this flag false misses native hero cleanup.

The admission oracle also accepts a real Python-generated body and expected
actor ID. In that mode it decodes the entity using `eHk`, the build set through
`eQV.ez`, and aptitudes through `eQx.ey`; it checks the selected build exists and
all build indices have aptitude sheets.

Actual generated-payload validation passed on 2026-10-10: Parfit exported
`.runtime/local/hero-activation-actual.bin` from the current Python activation
codec using a Store-created character in an isolated PostgreSQL test schema.
The installed native decoders recovered actor ID 2, build index 0 with a valid
selected build, and aptitude index 0. Luna independently generated
`.runtime/local/hero-review/activation.bin` (actor ID 1, 1988 bytes) through the
same real Store/captured-template flow and passed the native oracle as well.
These checks exercise all three actual payload blocks; they do not claim
headless execution of the graphical admission consumer.

## Live account 2 capture replay

`VerifyHeroRoster` decoded the actual 06:25:59 roster: all ten format-5 actors
(1, 5, 6, 9, 10, 13, 14, 15, 16, 17) have account 2 and nation, list nation,
and guild all zero. The real main actor 13 format-10 entity also decodes these
three fields as zero.

`VerifyCompanyReplay` replayed all twenty ordered actual account-component
messages through native `eDP.d(2, bytes)`. COMPANY first appears at message
index 9 (06:26:02.091711 UTC), with chief 13, nation 0, guild 0, activated true.
It remains present through every later cosmetic update, including the final
06:29:44.914174 UTC message. Thus these captured cosmetic updates do not erase
COMPANY and these actual payloads contain no nation/guild mismatch.

The UI predicate `bit.dpH` additionally requires that the COMPANY component
exists in the running client's account registry, and compares its nation with
`biz.an(actor)`, the roster nation cache. `bit.dpI` returns true for a character
without a guild; otherwise it compares guild IDs. Actual live getter results
remain required before attributing a grey row to any particular condition.

### Executed native UI predicates

With `-Djava.awt.headless=true -Djava.library.path=client/natives`, real
`biB(false)` construction succeeds. `VerifyHeroUiActual` loads all ten actual
format-5 entities through `actor.as`, including their native roster-cache
consumers, and replays the actual company updates. Main-character hydration
uses native identity/account/nation/guild component consumers individually;
full format-10 hydration requires graphical health callbacks.

For every captured character, actual `bit.eH("isInCompanyNation")` and
`bit.eH("isInCompanyGuild")` returned true. Context built by actual `bit.dpK`
passed native COMPANY, GUILD, NATION, and SUBSCRIPTION validators (`NO_ERROR`).
An empty recipe-150 object supplies the unrelated `bns` reward-list static
initialization dependency; it does not participate in these validators.
Full `canAddToParty` additionally requires a real initialized world/instance
manager, which this offline fixture does not supply. These results establish
that the decoded capture does not fail the four tested predicates; they do not
identify the running client's failing predicate.

### Actual live company eligibility regression: late nation update

The account 5 / main actor 4 inspector showed company nation 0, main nation 30, and both cached actor rows at nation 30. The actual capture frame 71, opcode 15548, contains format 22 with `NATION_ID=30`; this later update overwrote the neutral primary actor. Format 4 is unrelated and contains no nation section.

`VerifyHeroNationReplay.java` now executes the installed client's real `cyo` decoder, the real `bjG` nation component consumer, native nation factory `aHd`, `biz` cached nation, and `bit.isInCompanyNation` against the original captured frame and the actual Python `wire.adapt` output. Original output: native nation 30, actor nation 30, cached nation 30, eligibility false. Adapted output: all three nation values 0, eligibility true. This establishes both the original failure and the corrected consumer behavior beyond packet decoding. The fixture remains private under `.runtime/local/hero-review/`.

Validation:

```sh
javac -proc:none -cp 'client/lib/*' -d /tmp/wakemu-rift-native-oracle sniffer/java/VerifyHeroNationReplay.java
java -Djava.awt.headless=true -Djava.library.path=client/natives -cp '/tmp/wakemu-rift-native-oracle:client/lib/*' VerifyHeroNationReplay .runtime/local/hero-review/actor4-71-15548.bin .runtime/local/hero-review/actor4-71-15548-patched.bin
```

Result: PASS. This verifies the company nation predicate; graphical presentation and actual hero addition still require the combined manual acceptance test.

### Owned hero spellbook hydration and repeated selection

`VerifyHeroSpellHydration.java` passed against actual PostgreSQL Store-created characters of breeds 1 and 8 exported by Luna through the current `hero_wire.activate` and `OWNED_HERO_TEMPLATE` format 10. The native `cue` envelope and `eHk` decoder retain each character's own spell UIDs, different class references, and deck references. With the installed native bdata catalog loaded, the real `biS` spellbook consumer retains all three available entries for each level-one character; the real `biR` deck consumer retains build 0. Both consumers are applied twice per actor. Three rounds of native `fkJ` selected-character updates and `fkK` active-owned lookup preserve each actor's populated spellbook/deck.

The native name consumer also preserves each character's name across hydration. Breed and appearance sections are present in native decoding; graphical appearance rendering is outside this headless oracle. No spell engine behavior was modified.

```sh
javac -proc:none -cp 'client/lib/*' -d /tmp/wakemu-rift-native-oracle sniffer/java/VerifyHeroSpellHydration.java
java -Djava.awt.headless=true -Djava.library.path=client/natives -cp '/tmp/wakemu-rift-native-oracle:client/lib/*' VerifyHeroSpellHydration .runtime/local/hero-review/spell-hydration/breed-1-actor-1.bin .runtime/local/hero-review/spell-hydration/breed-8-actor-2.bin
```

Result: PASS. Fixtures are private; each packet body comes from actual stored character data, not a synthetic spellbook.

### Admission callback and party slot lifecycle limits

Actual client logs at 02:28:37 through 02:29:13 show format-11 `12093` admission failing in `biB.aQc`: `bdF.jf(actorId)` is null before `.deq()`. Native `bjs`, the `oN` ACHIEVEMENTS consumer, initializes that registry. Admission `aZr` registers/activates the actor only after `aQc`, so these exceptions prevent admission. These timestamps precede the format-10 deployment; they do not prove a format-10 failure. The hydration oracle now also executes the real `bjs` consumer and asserts the registry exists for both format-10 PostgreSQL fixtures, twice each. This passes. The full graphical `aQc` callback is still outside that headless proof.

Repeated admission has a separate cache constraint: `fkK.d` replaces the stored actor, but its `bya.z` listener is a no-op. `fkK.ay` refreshes the heroes list through `bya.A` only when the active-ID set gains a new ID. Re-admitting an already-active ID therefore needs a subsequent native refresh event, such as the authoritative COMPANY update, to rebuild `cZT` rows.

Company rows and company slots are different models. COMPANY's `aZt` callback rebuilds `cZT.ogd`/`heroesList`; it does not populate `bns` slots. The real `chs` handler for 1184 reuses a same-ID group. Only previously absent members call `fgq.e` and emit ADD; existing members are decoded in place without ADD. `bnw` populates slots from those ADD callbacks. Registering `bns.s`/`bxI.a(bxJ)` or `fgq.a(fgv)` does not replay existing groups or members. A repeated identical 1184 snapshot therefore cannot be assumed to repair empty slots. Live slot/provider inspection is required before choosing a further lifecycle correction.

The switch UI's generic selected-main rejection also covers an absent target in `fkK.aA(account, actorId)`, so the translated message alone cannot distinguish a missing active actor from selecting the current leader.

### Same-map control switching must preserve the selected scene

Native `SwitchHeroCommand.il` updates `fkJ` locally before sending 12006. It transfers the existing group reference to the selected actor and registers the corresponding company group listener. In contrast, `ciu` handling 13256 explicitly resets `aTx.cWu()` (the original master). Handling 13974 clears the scene and world position registry, parses a temporary entity for destination coordinates, then retrieves `aTx.cWu()` again and repositions/reactivates that master's graphic and camera. It does not target `bxY.dQA()` or copy the selected hero's identity. Consequently these map-transition bootstrap packets are inappropriate as an automatic same-map control-switch response; the selected owned actor refresh is a separate operation.

At 09:56 the two concurrently launched clients share `.runtime/local/inspector.json`. PID 16667 listens on 64632 (account 5 / actor 4); PID 16668 listens on 64633. The second token was overwritten by the other launch, and using the surviving token on 64633 returns 403. The available account-5 empty slots must not be treated as evidence about account-2's reported hero group. Future inspector startup metadata should preserve per-process credentials privately so both live clients remain inspectable.

### Required native switch acknowledgement and completion

The local `fkJ` selection change is only the first stage of switching. Native `cwE` (13440) carries `>Bq result,targetId`; success is result **0**. Its `clC` consumer queues local event `dgH` (18987). `dbV` then invokes `bns.ka(targetId)` to exchange the main and matching hero slots and schedules the `dbW` cinematic callback. `dbY.eDx` calls `aTx.f(target)`, changing the actual master and transferring the world position, group and graphics. Thus the master is not immutable: it changes after the acknowledgement.

After that transition, `dbY.eDy` calls `dbV.as(target)`, sending native `csF` (12054), body `>q targetId`. This is an asynchronous post-switch completion marker. Company, group and inventory publication can safely follow the matching completion; publishing them immediately after 13440 can precede the native master transition.

`VerifyHeroSwitchProtocol.java` executes the installed `cwE` decoder and `csF` encoder, validates all seven result values, and applies real `bns.ka` to two PostgreSQL-generated owned actor fixtures. The native slots exchange actors and preserve both `fkK` object identities. This oracle passes; the graphical `dbV`/`dbY` lifecycle is established by bytecode rather than executed headlessly.

### Required guild synchronization releases the switch fade

The cinematic completion predicate `dbX.isValid()` requires both `dbW.omI` (local transition completed) and `dbV.omF` (guild synchronization received). `dbY.eDy` sets the former before sending 12054. The latter is reset at the start of switching and is set only by `bkY.a`, called through `biK` when native **GUILD_LOCAL_INFO** (`qH`) is applied. An empty guild is valid: six zero bytes encode null guild data and zero float value.

Owned format10 does not include this section. Native format22 includes `[NATION_ID, NATION_SYNCHRO, GUILD_LOCAL_INFO, NATION_PVP_MONEY]`. Therefore the matching 12054 must be followed by the existing adapted 15548 format22 update for the selected actor. A format10 refresh alone leaves the fade indefinitely blocked.

`VerifyHeroGuildFadeCompletion.java` executes the actual installed `ciu.b(cyo15548)` handler, which applies `biB.as(format22)`, invokes `biK`/`bkY`, and changes the real `dbX` predicate from false to true. It uses an actual PostgreSQL-generated owned actor and an adapted captured 15548, and asserts that the master and owned registry retain the same actor object. This complete handler oracle passes. `VerifyHeroFadeGate.java` separately verifies that neither completion flag alone releases the fade.

### Owned HP and spell-bar presentation

Format10 contains scalar HP (`qr`, signed int32), but does not contain PUBLIC_CHARACTERISTICS. Its real `bjD` consumer deliberately sets the HP maximum to `2147483647` before assigning current HP. Therefore an owned snapshot needs both an authoritative scalar HP replacement and a subsequent public-characteristics refresh. The existing outside-world progression format3 provides current/max HP and XP; its native `eGo` and progression consumers restore finite values.

`VerifyHeroWorldResources.java` applies those actual component consumers to current PostgreSQL-generated fixtures: actor19 changes from `70/2147483647` to `70/70`, real level2; actor4 changes from `997/2147483647` to `997/997`, real level60. The offline actor overrides graphical characteristic notifications only; the complete format3 handler additionally invokes graphical position initialization and cannot run in this headless fixture.

`VerifyHeroDeckBars.java` goes beyond checking stored deck bytes: it restores the native active build, spellbook and deck, sets the actor as master, and runs the installed `bQm` spell-bar presenter. Actor19 produces four icons (7307,7312,7313,7317), and actor4 produces its seven saved spell icons. The native deck gate is `deck.minimumLevel <= master.realLevel`. These presentation checks pass, but do not assert that a live graphical switch invokes or binds that presenter correctly. `biB.dov` is the native callback that invokes it; `biQ` separately restores world shortcuts and clears unspecified shortcut bars.
