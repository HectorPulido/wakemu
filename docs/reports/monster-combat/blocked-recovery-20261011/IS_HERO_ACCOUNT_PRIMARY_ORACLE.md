# IsHero: actual account-primary table and missing producer

Offline native oracle for blocked reference5482 Monstruo admin yopuka. No
runtime predicate implementation, catalog update, ownership change or service
operation was added. Its actual initial state7544 includes effect389776
(family171, criterion `IsHero()`, raw parameters `[13376, 0]`) and effect340220
(family171, criterion `not IsHero()`, raw parameters `[13377, 0]`). Choosing a
convenient default would therefore select a different native initialization
branch.

## Actual native result, including missing entries

`sniffer/java/VerifyNativeHeroPrimary.java` creates an actual installed `bje`
NPC, parses `IsHero()` through the actual lexer/parser and evaluates the actual
predicate. It explicitly controls native `eGj.ePn` (Xi account) and `aHm` (Sn
actor identity), and populates or clears the actual `fkJ.suE` table. These are
isolated oracle fixtures, not mutations to any game instance.

All six native predicate cases passed:

| Account Xi | Actor Sn | Table entry | sS result | IsHero |
|---:|---:|---|---:|---|
| 0 | -200 | Absent | 0 | true |
| 0 | -200 | Primary -200 | -200 | false |
| 99 | 42 | Absent | 0 | true |
| 99 | 42 | Primary 7 | 7 | true |
| 99 | 42 | Primary 42 | 42 | false |
| 0 | 0 | Absent | 0 | false |

`fkJ` constructs `TLongLongHashMap` with its default constructor. Its direct
`sS(account)` lookup returns **zero for an absent entry**. `eNT` does not check
`containsKey` or the hero feature switch: it directly compares this lookup with
`actor.Sn()`. The oracle also verifies explicit removal, matching conditional
removal and nonmatching conditional-removal preservation.

Therefore **NPC classification does not imply IsHero=false**. An actual NPC
with account0 and a nonzero actor ID evaluates true when account0 is absent.
Likewise, an absent table entry is not equivalent to unknown authority: the
former has the demonstrated native zero result, while the latter cannot be
substituted by a default empty Python dictionary.

## Exact native table producers and lifecycle

An installed client JAR constant-pool scan found30 classes referring to `fkJ`.
Their bytecode contains these writes/reset operations:

- `ciu.b(aAa)` installs the selected-main account/actor pair through
  `fkJ.av(main.cBt(), main.Sn())` during main hydration.
- `SwitchHeroCommand.il(long)` replaces the current account's primary actor
  using the current account identity and selected actor ID.
- `clC.a(cwE)` restores the selected main's pair on the inspected failed switch
  response path.
- `biz.a(ArrayList<byte[]>, Runnable)` clears the account-primary table before
  company roster reconstruction.

The audit is scoped to direct bytecode references in this installed JAR. It is
not a claim about external server implementations or reflective producers.
Private evidence preserves all30 referring class names, their bytecode and
exact producer call neighborhoods.

Native `eGj.Xi()` reads `ePn`; `Sn()` reads `aHm`; `pK(long)` writes `ePn`.
The native reset path zeroes both fields. This does not authorize replacing
Python NPC `owner_id=None` with account0 without connecting the actual native
actor identity producer, including creator-dependent summons.

## Python authority boundary and next implementation step

`combat_heroes.frozen_main_sessions` resolves actual selected-main sessions and
checks the owned roster. `admit_owned_heroes` validates durable main membership
and creates admitted player actors using their real account IDs. These are
useful actual inputs, but current combat condition contexts do not carry the
native account-primary table or its replacement/reset lifecycle.

The missing producer is a source-qualified account-primary snapshot/query,
installed from actual selected-main admission and updated consistently on
selection, company reload and restoration. It must distinguish a complete
known table with an absent key (native value0) from an unavailable table. The
selected eII actor also needs its actual native Xi identity, separate from
controller and summon owner identities. The query must cover normal players,
heroes, detached initialization and creator-dependent summons.

No helper is connected yet because synthesizing that authority from generic
NPC classification or the set of controlled fight actors would fabricate table
state. Reference5482 remains pending this producer. Once available, the native
comparison itself is simple and should be tested against all oracle cases and
real admission/switch/reset lifecycle events.

## Reproduce the tiny oracle

```sh
mkdir -p .runtime/hero-primary-oracle/classes
javac -proc:none -cp 'client/lib/*' \
  -d .runtime/hero-primary-oracle/classes \
  sniffer/java/VerifyNativeHeroPrimary.java
java -Xmx256m \
  -cp '.runtime/hero-primary-oracle/classes:client/lib/*' \
  VerifyNativeHeroPrimary
```

The original run completed successfully. Private evidence:
`.runtime/monster-blocker-recovery-20261011/hero-oracle/receipt.json` contains
source hashes, six actual predicate results, removal checks, the blocked
monster's exact relevant initial-state criteria and native producer witnesses.
Existing Python tests and runtime predicate behavior were left unchanged.
