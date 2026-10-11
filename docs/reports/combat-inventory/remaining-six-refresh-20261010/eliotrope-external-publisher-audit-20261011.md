# Eliotrope external publication audit

Authority: published PostgreSQL revision `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`. Installed `client/lib/wakfu-client.jar` SHA256 `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`. This investigation changed no server code, catalog, service or native event stream.

## Result

No original1044/1045 publisher has been recovered. This is stronger than a literal search, but it does not establish that the original server lacks these events. Current enabled subscriptions require an explicit unresolved external boundary; dispatcher support alone does not close them.

| Event | Current enabled subscribers | Publication evidence |
|---|---|---|
|1044|Interstellar7202:377010→377011 return-to1856,377012/377013 cleanup,378571 marker removal|No authored emission or recovered installed-client publisher.|
|1045|Transitory5131:376993→3769943305/395861;EndShield7207:377041→3770427807|No authored emission or recovered installed-client publisher.|
|1049|Interstellar7202:377002 installs1856 and377010|Distinct from1044/1045: current directnull400356103 declares1049 and can publish through normal phases.|

## Call graph and argument qualification

The runtime-only scanner visits every JAR under `client/`, parses field/method/interface constant-pool references and superclass links, and includes erased bridge signatures. It covers57,299 distinct classes (57,619 class-file entries including duplicates). The resulting48 symbolic references include47 publication-related calls and the classifier's own field initialization.

`eFK` has only its private constructor, static initialization and `pyl` event-classification set. Its sole typed field reference is its own initializer; there are no typed method callers. Referring to an `eFK publisher` is therefore incorrect. Earlier textual matches in cgN/ctC/aPx refer to unrelated methods/constants with the same obfuscated name.

The actual routing is `Qe.L(byte)`→`PV.a(BitSet,Object,byte)`→typed bridge→actor/area Qf→Qi. The only symbolic caller of the erased PV publication API is Qe. Qe obtains the published mask from `bbw()`, merging native `PK.aZO()` with the instance `bfA` set. `ox(int)` adds to that set; `c(Collection<Integer>)` could bulk-add but has no recovered direct or inherited callers.

All41 caller classes were disassembled, including inherited `ox` references. There are67 `ox` instructions. No immediate argument is1044/1045. Dynamic arguments are characteristic event getters `ffw.fZr/fZs/fZt/fZu` or element getter `eVg.fLG`. A lightweight actual-enum probe enumerated every value: neither namespace contains1044/1045. Its raw output is retained; no combat/catalog initialization or event was performed by that probe.

A separate read-only query over all published effect collections found zero `target_masks[6]` authored-emission rows containing1044/1045. This query deliberately distinguishes emission index6 from subscription indexes3/5. The absence of an authored emission does not exclude an original server-owned external caller.

## Portal modes

Native `fee.a` delegates casting geometry to `fed`; entry/exit eligibility is separate from action resolution. `faX` is the portal-area superclass and has no movement-enter/exit producer in its inspected overrides (`aQc` is empty; the inspected occupant callbacks return null/false). Generic displacement runners retain their own native notifications: eWM declares3 and eWB declares2224, neither1044/1045. No call-chain evidence justifies aliasing these generic teleport/swap notifications to portal-hop events.

Actual current tests prove a normal4692 cast beyond ordinary range through two actual owned portals and preserve source rollback. They do not prove a movement-through-portals action, Interstellar return action, or1045 reaction. Alternate modes5131/7202/7207 still need a legitimate action boundary before positive event-dependent gameplay can be claimed. No synthetic event injection or guessed walking policy has been added.

## Artifacts and reproduction

Runtime-only files under `.runtime/eliotrope-review-20261011/`:

- `audit-publishers.py`, `publisher-inherited-callers.json` and `.log`: all-JAR symbolic publication/hierarchy scan.
- `native-all-publisher-callers.txt`, `native-ox-call-arguments.json`: disassembled caller instructions and argument neighborhoods.
- `native-publisher-routing.txt`: actor, area, Qf/Qi routing.
- `native-dynamic-event-enums.txt`, `ProbeDynamicEventEnums.java`, `dynamic-event-enum-values.txt`: complete actual dynamic getter values.
- `native-portal-action-modes.txt`: fee/fed/faX and generic displacement modes.
- `global-authored-emit1044-1045.json`: independent published-catalog emission query.

Reproduce the static scan with `python3 .runtime/eliotrope-review-20261011/audit-publishers.py`; it reads installed JARs only. Runtime positive/negative passive observations are separately queued in `probe_owned_passives.py`; their results must not be inferred from this static audit.
