# Remaining predicate authority audit

## IsSpecific — reference 4838

The original criterion tests references 1360 through 1368 with `IsSpecific`.
Installed lexer `eQb` accepts `IsSpecificArea` and `IsSpecific` in the same
rule, assigns the same token, and only changes the consumed spelling
(bytecode offsets 960–974). This is a lexical alias, not a species predicate.

The condition validator and evaluator now dispatch both spellings through the
existing `IsSpecificArea` callback. No actor or area authority was added.
Two new tests verify equivalent reference selection, malformed signatures and
rejection when actual area identity authority is absent. Together with the
glyph count tests, six focused tests pass. Native monster replay is pending.

## AIHasCastSpell — reference 4055

Parser `eQd` token 7 constructs `eIu`. Its evaluation requires the first
native context argument to implement `ffc`, requires `ffc.fZk()` to return
non-null `ffb`, and calls `ffb.TY(spell_id)`. Either missing context raises the
native expression exception. The spell id is obtained through `ayn`, including
the native constant/numeric expression checks and Java long-to-int narrowing.

A generic successful-cast log is not proof of `ffb.TY` semantics or its reset
boundary. The Python condition context has no actual source-qualified `ffc`
AI planner state or `ffb` query. This primitive must be extracted and connected
to the AI context before supporting the predicate. Do not substitute false,
an empty ledger, or lifetime cast history. No implementation was added.

## IsHero — reference 5482

Parser token 311 constructs `eNT`. Native evaluation resolves the actor through
`eII.l`, looks up its account with `eGj.Xi`, obtains the primary actor through
`fkJ.suE.sS(account_id)`, and compares it with `eGj.Sn`. It returns native true
zero when those identities differ, and false minus one when they agree.

The combat condition context lacks the actual account-to-primary-actor table
and its lifecycle. NPC classification alone does not prove the comparison.
An authoritative account/primary lookup and matching actor-selection contract
are required. No implementation or assumed NPC false result was added.

Private installed bytecode witnesses are in
`.runtime/monster-blocker-recovery-20261011/eQb-unknown-predicates.javap`,
`eQd-glyph.javap`, `eIu-ai-cast.javap` and `eNT-hero.javap`.
All work is offline; active catalogs and services are unchanged.

## Additional account-table source boundary

`fkJ-account-primary.javap` confirms `suF` is an actual `TLongLongHashMap`; `av(account, primary)` writes it, `sS(account)` directly calls `get`, and `sT`/`clear` remove entries. Other helper methods also inspect the hero-feature switch and `containsKey`, whereas the `eNT` predicate uses the direct lookup path described above. Therefore a generic `is_hero` label or NPC false shortcut cannot substitute for the native comparison.

Current Python hero admission does have real selected-main session and owned-roster authority (`combat_heroes.frozen_main_sessions` and `admit_owned_heroes`). It does not yet install the native account-primary table into every combat condition context, nor prove identical lifecycle for detached NPCs and creator-dependent summons. This is a possible provider source, not completed support.

An offline class-file interface scan of `client/lib/wakfu-client.jar` found no direct concrete `ffb` or `ffc` implementations. The interfaces and `eIu` consumer exist, but no actual AI-planner implementation was recovered from that direct-interface scan. This is limited negative evidence for this jar, not proof about other jars or server-side implementations. Generic cast logs remain insufficient.
