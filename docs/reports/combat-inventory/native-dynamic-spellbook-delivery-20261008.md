# Dynamic class spellbook delivery

Temporary class actions use family649 (`eWn`), rather than additions to the
ordinary progression/deck catalog. The same source path serves automatic innate
grants and conditional state grants. Availability still requires an actual owned
book object and native casting conditions; a displayed shortcut is not authority.

The production handler encodes the reference, requested level, signed byte bar
and signed short slot in native AdditionalDatas fields10/14/19/20. Application
uses12613 with `eIK=false`; removal uses13560 with the same exact retained
payload. The former13497 delivery only observed the runner and did not execute
`c()/fMO()`; server-side grant success alone therefore did not establish client
shortcut installation. Original
`eWn.f(iN)` reconstructs the raw-reference spell object, `fMO()` inserts it into
`dok()`, updates the execution book through `drs().aW`, and calls
`eGj.a(bar,slot,spell)`. Original `bbR()` removes that raw object and execution
entry, then removes the corresponding shortcut. This is native effect delivery,
not a separate server shortcut update or a fabricated UI grant.

The normal transaction preserves all effect packets before its action flush.
Ready captures the empty baseline before initialization, then delivers the actual
initialization outbox. Timed/state removal uses the common owned removal route
and the649 remover. Active join uses the complete13912 retained population,
including649, instead of an empty effect snapshot.

The original reconnect consumer explicitly removes old grants before replay:
`eZV.a(bytes,PN)` calls `clear`; `eZV.clear` invokes `Qf.clear`, which calls each
runner's `aW(false)`. `Qe.aW` invokes virtual `bbR`, so old649 book objects and
shortcuts are removed through the same native removal method. The subsequent
native deserialize/replay reconstructs the current retained grants. This source
chain avoids claiming that stable server bytes alone prove client idempotence.

The shared application delivery mismatch is now corrected. The remaining
validation gap is a differential client book/shortcut replay with649 present,
repeated snapshot replacement, and replacement after actual state/expiry removal.
Existing complete-snapshot regressions cover310/949/1066/500 and exact UID/payload
population; they do not establish that additional649 client acceptance case.
The class grant matrix establishes server ownership/preparation/removal separately
and does not replace live client acceptance.

Source disassemblies are `spell-access-eWn-native.txt` and
`spell-access-eZV-native.txt` under `.runtime/combat-review-20261007/`, plus the
original `Qf.clear` and `Qe.aW(boolean)` bytecode. No services, DB or AI were changed.

Focused verification after the delivery correction: `test_combat_spell_grant`
and `test_combat_morph_spellbook`, 19/19 pass. Regressions check the native false
execution byte, unchanged evaluated protobuf, raw-reference ownership and
removal. Original `aVo.cYg` retains persistent runners on the target manager,
then executes non-subscribed runners; subscribed runners remain deferred. No
new shortcut packet or UI workaround is introduced.

Authoritative649/933 unapplication now sets native `TimeDatas1` explicitly.
Original `aVz.cbj` checks `eZR.fMV()` before `Qf.q`; during a normal active fight,
a non-subscribed runner without a delay requires `rIZ` (decoded from this field)
to enter removal. Otherwise the server could remove its grant while the client
kept the spell/shortcut. The existing keep-after-removal native gate remains
untouched. `notify_unapplication=False` preserves the original bytes. Application
encoding explicitly disables removal notification, even though both outer packet
layouts share the identity validator. Validation: removal/grant/morph suites,
27/27 pass; checked clocks/identity preservation and distinct application/removal
notification bytes. Live client removal remains part of manual acceptance.

State replacement also preserves the original removal order: native `eWu.c`
calls `aS(oldCarriers)` (`ms(true)` then `Qf.q`) before `D/fNa` creates the new
carrier. The owned ledger now provides a callback before publishing replacement.
During cleanup the old carrier and its payload remain actual registered facts;
central area removal, ordinary child reversal and group cleanup run once before
retiring the old carrier. State-owned areas use their existing `keep_after`
contract and actual area callbacks. Callback-created states survive the later
replacement commit. This closes the previous omission where replacement only
removed stat/group children and left old state-owned areas active. Focused
replacement verification is delegated; this change is not live-client evidence.

`KEEP_WHEN_OFF_PLAY` is distinct from replacement: native `eZV.a(PV,bool,bool,bool)`
has separate flag9, `fyW.guQ`, runner-kind and execution-mode gates. No blanket
death/fight-end clearing is inferred from HP or substituted for that contract.

## Other evaluated client mutations

The same concrete observation/execution distinction was corrected for196 (`eXO`
current-HP/resource restore),986 (`eZI` percentage HP), maximum reduction and447
(`eWt` fight properties). Their original `c()` methods perform the actual native
PA/PB mutation; decoding/observation alone does not. Immediate, non-retained
applications use12613/eIK=true. Retained applications use the existing false
branch to keep the actual Qf registration contract. Kill28 and non-retained
recall859 use that same explicit immediate execution flag. UID, evaluated value,
AdditionalDatas, clocks and original containers remain unchanged; `C()` is not
re-run. The shared converter's default remains false for existing callers.
Focal suites for observation/current-HP/percentage/fight-property/kill/recall:
40/40 pass. Maximum-reduction focused verification is delegated separately.

The evaluated mutation helper is also used by the shared current-characteristic
handler/consumer (`eWW` with `eWQ/eWR` amount application) and `eWN` maximum/current
resource handler. Original `eWW.c` calls the actual PA application path;
`eWQ/eWR` use `PA.nG`, while `eWN.c` uses `PA.op` and optional `PA.nG`.
`evaluated_effect_delivery` requires an explicit boolean retention fact and
selects true for immediate application, false for retained application. It never
creates a server Qf record and does not change PA raw values, negative currents,
limits or callback ordering. Existing observation helpers retain their defaults.
The exact current-stat/maximum-resource/helper regression batch is delegated
before final delivery.
