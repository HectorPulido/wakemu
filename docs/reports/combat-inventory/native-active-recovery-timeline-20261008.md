# Active recovery timeline authority

Recovery now separates the complete actor roster from native timeline members.
Fresh summon PB114 (`NOT_PRESENT_IN_TIMELINE`) keeps beacons in actor snapshots
without placing them in the Tc/SY arrays. Ordinary actors without a matching
member counter are rejected; failed lookup is not interpreted as exclusion.

`combat_timeline_snapshot` records actual mutations as checkpoint-safe plain
facts. Ready creates the initial SY zero counters. `Fight._advance` increments
the ended current member, matching SU end → Tc.bit → SY.bif. Fresh summon
registration records SU round plus one when insertion is at/before the current
slot, matching Tc.a(long,short,SQ) offsets 170–205. Death reconciliation records
the current SY value plus one for the current member, and the exact former
position, before removing it; fem.eT calls Tb.fb, checks current eJ, and obtains
ez before removal. PB114 has no SY entry and no removed timeline status.

The encoder uses `native_timeline_round`, current `order`, and the explicit
`native_base_turn_order` when extra turns have a different next-round order.
It no longer derives a round from the current actor's activation count or
reconstructs deaths using initiative sorting of the current roster. Pending
removed-turn modifications remain unsupported rather than silently discarded.
Restored fights without the new producer marker fail explicitly; no roster
retrofit is claimed to recover lost progress facts.

Native source evidence: `.runtime/local/combat-timeline-SXSY.txt`,
`.runtime/local/combat-timeline-fem.txt`, and targeted javap output
`/tmp/recovery-Tc.txt`, `/tmp/recovery-SU.txt`. No world restart or live writes
were used for this change.
