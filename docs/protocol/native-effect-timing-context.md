# Native runtime timing provider

`combat_native_timing_context.NativeEffectTimingProvider(catalog)` provides the
four-argument `state` and `stat` callbacks expected by RuntimeProvider. The
catalog must contain both effect and state definitions. Main is not modified.

Evidence from the installed offline client:

- `eVE.aZD` returns zero; compact metadata exports the actual virtual call for
  every reference, including subclass overrides. `eZR.bbW` requires mode two
  for an applying-effect delay. Modes one/two are explicitly rejected because
  their `ep/en/eo` evaluated clocks are not exported.
- `eZR.Ty` mode zero returns true (bytecode offset 127). An ordinary current-stat
  application remains an owned effect with no independent expiration timer;
  state-owned children retain their carrier UID for removal.
- `eZk.a/aWr` initialize `rHv=-1`, `dPa=0`, `rHy=false`, `rHz=false`.
  These are native fresh carrier defaults, not aliases for duration/end flags.
  `eWu.D` propagates the applying definition's `dd(1)` critical variant.
- State replacement/accumulation is planned before computing its final level's
  duration. Timer scheduling reuses the audited SU/TC helper. Additional22 is
  the evaluated `fyW.guH` realtime duration; Additional21 remains `rHv=-1`.
- `eZR.QH` serializes iB fields 1=false, 2=-1, 3=ix(actor, absolute round,
  end flag), 4=realtime remaining, 5=false for a fresh ordinary application.
  `Ts.biM` is actor zero, round minus one, end false. TimeDatas is emitted even
  when there is no timer. `ProbeNativeTimeDatas.java` proves both sentinel and
  scheduled payloads against the native protobuf implementation.

Local timeline uses `current.turn_count`, the same round contract as existing
CombatRuntimeMessages. It validates current index and eligible actor order;
removed dead actors do not invalidate subsequent state casts. During a spell
resolution dead actors may remain in order pending completion. An absent clock
actor is rejected; no policy for a dead removed clock is invented.

Limits: positive realtime clocks, mode one/two, trigger-dependent stat values,
new timeline insertion/capture/control rules and special carrier flag mutation
are unsupported. The stat context assumes ordinary actor/source guards are
validated by the actor provider; it does not certify companions or immunity.

## Correction after concrete metadata extraction

The native virtual call is essential: among 55,480 exported references, 55,174
are `eVy` (mode two), 255 `eVH` (mode one), and only 51 plain `eVE` (mode zero).
An earlier inference from the superclass alone would be wrong and is not used.
Both catalogs now preserve concrete `native_definition_class`,
`native_execution_mode`, `native_timing_definition`, and checks at levels
0/1/200/32767. State full export shares ExportSpellEffectTrees.metadata.

`eVy.en` evaluates signed-short(base + floor(float32(growth * level))),
end flag `esr`, boolean `ryG`, and signed-short(duration+1) secondary value.
`eo` uses the same arithmetic with `ryH/ryI`; its secondary fields stay zero.
`eVH.ep` uses `rzv/rzw` with signed-int addition and no short narrowing.
The provider implements this arithmetic from exact native fields, not a fit
from the sampled levels. Native 304 reference167716 and damage reference339526
both return en=(0,false,1,false), eo=(0,false,0,false) at all checked levels.

Supported mode-two effects currently require delay<=0 and duration<=0;
positive independent duration requires audited Qd/Qb clock routing, and positive
delay requires an execution queue. This supports native zero-clock ordinary
applications while leaving other modes explicit. Standalone mode-two duration
zero is not retained by its own Ty; a retained parent state owns reversible
stat children independently. The state duration itself uses fyW, not eVy.en.

## Positive turn timers and expiration

Positive mode-two en durations are now supported for current-stat effects.
`eZR.fRc` selects aZT caster first, aZU target second, then target/caster fallback;
these virtual-call booleans are exported inside native_timing_definition.
Qd/Qb application/removal actor selectors are not substituted for this clock.
`combat_effect_timing.schedule_effect_timer` follows SU.a and TC.a, including
`ryG`/Tt.biR's extra round when applied during the clock actor's active turn.
The native probe outputs (actor7,round4,start), (7,5,start) with extension,
(7,3,end), and (7,5,start) when that actor's turn already passed.

`StatExecutionContext.timer` stores the absolute actor/round/phase in the owned
stat entry, as a JSON-safe dictionary. `prepare_timed_expiration` performs all
removals in a copied fight and returns its outbox; commit preserves existing
Actor identities. State expiration removes reversible children before carrier
310 and clears both ledger and original wire payload. It never reconstructs a
missing wire payload. Missing payload or invalid inverse aborts the preview.

RuntimeMessages invokes end expiration before advancing the actor, round cleanup
once at a new round, then start expiration before serializing the next actor.
Next-turn removals remain behind the existing13510 ACK barrier. Action IDs are
committed only after successful expiration and preserve packet ordering. These
hooks dispatch timer callbacks directly, without inventing native event IDs.
Positive realtime clocks and positive execution delays remain explicit failures.
