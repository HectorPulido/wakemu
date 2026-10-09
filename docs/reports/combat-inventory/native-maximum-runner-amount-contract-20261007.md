# Native maximum-resource runner amount sources

The two full-audit rejections saying `Missing native triggering maximum amount` occur in family41/eWN under an eYy865 value-transfer group. The error wording does not identify a native `GetTriggeringEffectMaximumAmount` criterion. No such lexer string was found in original eQb or current shared condition grammar. Family412 group ownership does not define an independent maximum-amount source.

## Original eWN calculation/application

`eWN.C(Qe)` reads its actual selected PK/eVn parameters at native fRR level: parameter1/2 become applyCurrent/removeCurrent booleans, parameter0 becomes the literal running amount. It does **not** replace -1 during calculation. It handles -2 separately: if actual PS/eVt has a non-null fLP source and that source's current getValue is positive, multiply that value by2 with signed-int overflow. Otherwise leave -2 unchanged.

`eZR.n(Qe)` then calls C, invokes actual eVt callbacks, and applies the context's forced value if fLR. Absolute context replaces getValue, including zero/negative values. Percent context wraps the multiplication, truncates integer division toward zero, and clamps at least1. This stage precedes L2 and eWN.c application.

`eWN.c(Qe,boolean)` resolves target characteristic presence first. Only if the **current runner amount** equals -1 and its actual argument Qe is non-null does it replace the amount with that source Qe.getValue. Null source leaves literal -1 unchanged, allowing a normal maximum decrease. It then applies the native cap/raw maximum updates, rewrites aSg to actual raw maximum delta on the server, and rCn to effective maximum delta. Optional current-resource application uses the effective delta.

These are three distinct authorities: actual eVt.fLP source used only by the -2 C transform; forced-value eVt context applied after C; actual application Qe trigger argument used conditionally by -1. A parameter count, spell level or subscription definition cannot substitute for any source.

## Original-client probe

`ProbeNativeMaximumAmountSource.java` uses original eWN and PA arithmetic with a native proxy PV and no catalogs/services. Four cases pass:

- literal -1 with absent Qe/context: max100 becomes99;
- literal -1 with actual source value7: max100 becomes107;
- literal -1 with actual eVt forced7 and no Qe: max100 becomes107;
- literal -1 with eVt forced0 and actual source9: max100 stays100.

The final case proves that resolving the parameter's -1 before applying its actual context changes behavior.

## Existing gaps and minimal general repair

NativeMaximumResourceHandler currently consumes the literal parameter directly and demands StatExecutionContext.trigger_value for every -1, although the ordinary timing provider supplies None. It ignores native_context_hex entirely. The two observed eYy children already carry an authoritative forced-value context from the first child's final runner callback; applying that exact context before the -1 application branch resolves their shared cause without case exceptions.

A general amount resolver should run: eWN C amount/-2 transform → current eVt callback/forced-context amount → L2 mutations → application-time -1 substitution if actual Qe exists. Explicit application-source absence preserves literal -1. A supplied non-null source with unavailable identity/current value must reject. NativeEventSource plus its scoped NativeRunnerAmount can provide current getValue; validate UID/family against the actual invocation trigger and read the live amount after synchronous mutations. Snapshot-only values are sufficient only when their producer attests they are the actual current source amount.

The maximum handler currently lacks prepared running UID, NativeRunnerAmount and L1..L4 wiring/final value observer. Reusing the existing generic source lifecycle requires a producer for eWN.bbx events (0 plus ffw.fZr when fZv), complete native PK suppression/flags and actual container identity. The stored/packet amount is actual raw delta, not requested amount; the effective delta remains separate. This must stay consistent when adding the live amount to NativeEventSource. This report changes no Python source/catalog while integrated validation is active.

## Implemented general amount-source correction

The maximum-resource handler now applies the actual forced-value context before checking the application-time -1 sentinel. A null invocation trigger leaves literal -1 unchanged, regardless of the timing context's trigger_value. A supplied trigger must validate as a verified NativeEventSource with actual UID, runner family, identity and signed current value. When a matching scoped source exists, its live NativeRunnerAmount takes precedence over the serialized source value; identity or missing live amount rejects. Replay-produced verified source snapshots remain accepted when no scoped source is available. A present but incomplete descriptor is not treated as source absence.

The -2 calculation transform remains unsupported and explicitly rejected before context application. Full eWN lifecycle/prepared UID/L1..L4/final observer remains pending. Raw/effective maxima, minima, caps and reversible stored values were not changed.

Six new regressions plus existing maximum-resource, maximum-reduction and parameter-maximum tests pass: 22 tests, 0.549 seconds. They cover transferred 7, forced zero despite a source value of 9, literal -1 without Qe despite timing trigger_value=9, actual source snapshots, live updated value, missing value and source identity, unresolved -2, and unchanged cap/raw/effective/minimum behavior. Command: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python -m unittest server.tests.test_combat_maximum_amount_source server.tests.test_combat_maximum_resource server.tests.test_combat_maximum_reduction server.tests.test_combat_parameter_maximum`. No heavyweight catalog audit or services were used; no source-manifest stability claim is made for this focused run.
