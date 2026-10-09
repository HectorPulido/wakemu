# Server-owned normal spell execution origin

Normal owned spell transactions now explicitly choose the original `eVt`
constructor scalar contract. This is Wakemu's server policy, not a claim that
the unavailable original normal server caller was recovered. The decision is
made after owned casting validation and runtime-factory validation, before root
dispatch, and bound to actual caster identity, spell reference and evaluation
level. It applies to normal owned class, extra and granted spell entry.

| Scalar | Chosen value | Native gameplay consequence |
| --- | --- | --- |
| Probability bypass | false | Retain native effect probability checks |
| Criterion bypass | false | Retain native effect criteria |
| Selection | -1 | `eZR.fRR` uses actual container level instead of forced selection |
| `ban` | true | Preserve original `Qe.a` processing reset behavior |
| Forced value/mode | 0/NONE | Retain evaluated effect value; no SET/PERCENT override |
| `mc` | false | No `eZR.fLb` override supplied by context |
| `bbI` | false | No child-runner marker supplied by the normal root |
| Source runner | null | Fresh external root has no originating effect runner |

All scalar defaults and serialized bytes are proven by original constructor
execution. Choosing that fresh context at the owned entry is the explicit
implementation policy. No preview-only bypass flags, critical-result flags,
variant IDs or guessed child mutations are substituted. Native child/group
producers continue to create their own source-backed selections/forced values.

`NormalExecutionOrigin` is typed and rejects identity/level mismatch. Root
invocations receive its context13 bytes. Existing incoming, trigger and restored
dispatch routes are not routed through this fresh-origin function; the shared
context accessor preserves supplied bytes unchanged. Source-runner pointers
remain separate from the scalar wire context.

The original JVM constructor and actual scalar mutation oracle was rerun at
128MB. Fresh and mutated bytes match the Python serializer fixtures exactly.
Eleven focused origin/serializer/cast-facing tests passed. Runtime packet and
effect-family acceptance remains part of the coordinated factory auditor; no
world process, services or database were changed.
