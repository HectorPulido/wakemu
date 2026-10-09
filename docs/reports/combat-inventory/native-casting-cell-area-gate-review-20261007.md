# Shared class casting predicates

Original `eQb` tokens 309, 335 and 363 route through `eQd` to `eNR`
(`IsFreeCell`), `eOz` (`IsOwnArea`) and `ePn` (`NbGates`). The offline
`ProbeNativeCastingPredicates` confirms the real parser classes and exports
289 original `aBn.y` direction results. The helper regression compares all
289 rows rather than substituting the other casting orientation algorithms.

`IsFreeCell` takes a selector string and two constructor-evaluated integer
offsets. The selected point faces the opposite point through `aBn.y`; tied
diagonal distances select the Y cardinal direction, and coincident points
reject. Offsets rotate with signed Java integer arithmetic. The resulting
cell must satisfy `QI.R`, must have no center-matching `Qs` area whose `bcP`
blocks movement, and must have no first `QI.V` obstacle. The runtime reads
the existing authoritative terrain, registered area constructor contracts and
persisted Trove slot topology. This differs from casting's `QI.g` mask and
movement-override rule. Missing authority rejects explicitly.

`IsOwnArea` accepts zero arguments or one literal boolean. It compares
canonical `eII.aT` PV identities, including the area's actual owner, across
every registered area type. Area targets inspect the selected area; null
targets scan `Qs`; cell targets require native area containment. In cell form,
true additionally requires the area's center to equal the target X/Y. It does
not exclude the center. Ordinary non-area actor targets reject. The existing
deposit predicate is separate and was not modified by this change.

`NbGates` takes two literal strings and counts active `Qs` entries with native
type 19. `forOwner` compares the area's actual owner identity to the selected
native fighter; `forTeam` compares the area's captured affiliation. Unknown
modes or authoritatively absent selected fighters return zero. A missing
fighter type or affiliation remains unknown. Cell-to-fighter resolution for
`NbGates("target", ...)` remains explicitly unsupported; the current class
casting inventory uses `"caster", "forTeam"`.

The casting inventory's current instances use the implemented literal
signatures: two spells include `IsFreeCell`, seven include `IsOwnArea`, and
one includes `NbGates`. These are structural affected counts, not complete
spell certification. `IsSelectedCreatureAvailable` remains unknown until the
selected captured-creature roster has an authoritative native producer.
Other predicates in each original expression still require their own proven
contracts. Unit validation is delegated to the offline validation agent; no
services, containers, databases or AI code were changed.
