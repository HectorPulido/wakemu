# Complete acceptance command audit

Bounded source review of the17 sections in
[SYSTEMS-ACCEPTANCE-20261011.md](SYSTEMS-ACCEPTANCE-20261011.md).
No command was executed against gameplay; no service or client was changed.

Two concrete wording defects were corrected:

- Dungeon return previously requested restoration of the original owned level
  after using `!nivel`. `maps/test_console.py::execute` explicitly rejects
  decreases. The guide now restores owned build/deck/equipment and states that
  development level increases persist.
- Ban acceptance asked for a second active-gameplay sanction immediately after
  the first ban had disconnected B. The first timed sanction now explicitly
  occurs while B moves or performs inventory work; later expiry/unban steps
  already supply the required fresh login.

Actual `maps/test_console.py` dispatch confirms `!tp map x y z`,
`!item reference quantity`, `!nivel level`, and argument-free `!pos`.
`parse_target` accepts an optional final target name, which the guide does not
need. Grants are reference/quantity, not UID/quantity. Commands remain subject
to existing authorization, native stack limits, inventory space and real
walkable geometry. The nation command is handled separately by the actual
native chooser dispatcher and remains `/l !nacion`.

Physical board20158 approach527(90,1,4), boat18259 approach504(4,3,9) and
Door15411 approach337(51,-246,4) agree with their dedicated original-client and
geometry qualification reports. Boat outbound794(-3,-4,6) and return504(4,2,9)
match that recorded native contract. No new geometry claim was inferred or
unreceipted coordinate substituted. The Otomai guide follows its dedicated
142 acceptance route; seats141 and ordinary doors143 remain explicitly staged.

The mount phase retains the current source-qualified two-unit then eight-unit
food sequence, configured daily-limit check and replay-window wait. Public
bag gem4266/garden and4264/crafting identities agree with existing native
bag regression fixtures. Full recipe/catalog and visible UI behavior still
require their existing acceptance; static command arity is not that proof.

No additional invalid command ordering was found. This review does not claim
that the pending publication, all17 manual sections, geometry on a different
catalog release or graphical outcomes passed.
