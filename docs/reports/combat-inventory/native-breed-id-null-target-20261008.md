# Native breed-ID predicate on absent/nonfighter targets

The full normal-cast audit recorded unresolved empty-cell target candidates for
class7 action1535 at levels20/200 and class14 action7086 at level200:
`Missing native breed: target`. The existing IsBreed named predicate already
handled authoritative null/nonfighter selections, but IsBreedId did not.

Original eNu.a uses eII.a to select the eHg. Offsets14–20 return -1 for a null
selection; offsets23–36 call dsG and return -1 for a null eGH breed descriptor.
A false predicate is therefore source-defined for actual absent recipients and
registered Qq/faV recipients without a breed descriptor. It is not a fabricated
breed0 and does not imply a human or monster classification.

IsBreedId now returns false for the context's authoritative null alias/absent
target marker and for a registered recipient typed is_native_fighter=False.
Missing recipient evidence and a qualified fighter without breed authority
remain UnknownCondition. Thirty condition tests pass, including variadic signed
breed IDs, actual null selections, registered nonfighter facts, negation and
unknown authority rejection. Actual legal-cast reruns remain separate evidence.
