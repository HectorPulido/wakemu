# Fresh rebound group selection: Zobal resurrection regression

The actual 7086 regression binds 314358 to the registered corpse (caster 7, target 8), then executes 314360 with native rebind byte 2. Its child 314361 receives caster 8, target 7 and its `HasEffectWithSpecificId("target",314358)` condition is false. These identities are reproducible; this is not a missing resurrection runner.

## Original client contract

`eYg.c(Qe,boolean)` calls `fPP()` before executing children. `fPP` byte 2 exchanges both `bfr` and `bfs`. `eYg.a(iterator,eVt)` passes the current `bfs` coordinates and, when `rFn` is true, that same PV argument. `C` evaluates parameter slot 4 as the transmit boolean and slot 5 as the rebind byte. `eZR.I` passes current `bfr` and `bfs` to the criterion; `eMj` resolves the target and checks its actual `Qf.oG(id)`. The original native explicit-PV path skips selector enumeration. No alternate interpretation of SELF, criterion aliases or original pre-swap target is justified.

Selector bit 1 is IN_AREA; SELF is bit 2. The marker's `owner_on_caster` is false. Previous speculation that mask 1 implicitly marks the caster was incorrect.

## General fresh-server policy proposal

Wakemu already distinguishes fresh child relationship selection from replay of a native chosen PV. A dedicated fresh rebound-selection provenance flag can request enumeration for a mask-zero actor-group child after an actual parent swap, while preserving native explicit-target replay. The flag must be produced from actual non-null swap inputs, never inferred from spell IDs or criterion text. Groups that themselves perform the swap retain their explicit incoming target before their own transformation; this preserves the Cunejo behavior. PT and event replay must not acquire this fresh policy implicitly.

A read-only PostgreSQL review of 17,425 distinct family-330 definitions across spell trees, granted trees, state trees and area trees found two direct swap-2 parent → mask-zero actor-group child templates: 165670 → 166392 and 314360 → 314361. Both child groups have no own rebind and use a retained-marker target criterion. This supports a shared fresh-server mechanism rather than a Zobal ID exception. It does not recover an unavailable original server selection callsite.

Production changes require coordinated ownership and regressions covering both retained-marker resurrection and Cunejo's explicit recipient. No production selection change was applied during this investigation.

## Implemented bounded policy

The coordinated implementation now produces `wakemu_rebound_child_selection` only when a fresh ordered parent actually swaps two non-null actor identities. A fresh mask-zero family-330 actor child with a nonempty native criterion and evaluated own rebind zero enumerates its native criterion candidates in that changed source context. The criterion itself still executes normally; neither its text nor reference ID controls this policy. PT entry clears the fresh rebound provenance. Native replay, groups owning their own swap, leaf effects and groups without a criterion preserve their transmitted recipient.

This is explicitly Wakemu fresh-server reconstruction policy, not a change to the recovered native client chosen-PV replay contract. Four focused regressions cover the two native child parameter shapes, preserved replay, preserved swap-owning Cunejo recipient, and preserved leaf/unconditional binding. Actual resurrection and cross-class regression execution remain delegated to the coordinated validator.
