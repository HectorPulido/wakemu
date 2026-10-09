# Native conditional casting selection and AP arithmetic

## Selection is last matching entry

`fyF.A(caster,target,spell,fight)` initializes its result with baseline `twf`. It iterates the keys of `twg`; each criterion returning true replaces the selected fyP. It does not stop after a match and does not reject multiple distinct matching tables. The final result is the **last matching entry in the actual native map iterator**; no matches preserve the baseline.

All relevant getters call the same selector: cost-map `fyF.g`, maximum/minimum `i/j`, selected range-modifiable and geometry/LOS flags. Select one complete casting table; do not merge costs from one matching branch with geometry from another.

Native criteria `amb.b` treat `a(...) == 0` as true, with their native negation handling. This does not authorize treating missing Python authority as false. A Python unknown means the underlying native facts have not been established.

## Export ordering is not native runtime ordering

`aNr.cwI` is `HashMap<String,aNs>`. `bPS` iterates those raw definitions, parses each criterion to amb and adds it through `fyT.a(amb,fyP)`. `fyT` creates a distinct `HashMap<amb,fyP>`; the fyF constructor retains that map directly. The selector iterates this second map.

The current casting/range exporters iterate the first string-keyed map. The resulting conditional JSON array is therefore not proof of selector precedence. Do not fix the Python selector by taking the last matching JSON rule.

Base classes amb/alS do not override equals/hashCode. Concrete criterion types require inspection before claiming portable stable ordering; identity-hashed criteria can have different iteration order between native processes. A staging export of native `twg.keySet` order proves that process only unless deterministic concrete key hashes are established. If all reachable simultaneous matches produce the same complete table, priority is irrelevant. Otherwise exact native ordering needs an authoritative source or the discrepancy must stay explicitly unresolved. The existing distinct-table ambiguity rejection is a conservative guard, not native selection semantics.

## AP arithmetic

`fyF.g` evaluates each entry in selected `fyP.guh` at spell level, then sums `eHl.a(stat,category)` across the spell's EnumSet categories. `eHl.a` returns AP pOJ for ffw.sgD, range pOK for ffw.sgK, and zero for other characteristics. Addition uses signed Java int wrap. Ordinary costs then use `Math.max(0, wrapped(base + categorySum))`; `fyQ.g` omits nonpositive entries. No further AP upper cap is present here.

The special ffw.sid branch bypasses the ordinary zero clamp and stores through fyQ.h; do not generalize AP policy to every possible native cost characteristic.

Python unbounded `max(0, base + sum(modifiers))` differs at integer overflow. Wrap category accumulation and base addition to int32 before clamping. Summing all categories then wrapping once is arithmetically equivalent to native sequential int addition, but the selected category set and live modifier snapshot must still be authoritative.

## Next verification

A pure original Java selector oracle can install explicit map order and always-true/false criteria without loading catalogs, proving baseline fallback and last-match behavior. A separate actual-key-order exporter is needed to investigate real overlapping definitions. An AP oracle should compare signed-int boundary modifiers and zero omission to the production resolver. No production edits or catalog audits were run during this investigation; the class bulk audit retained source stability.
