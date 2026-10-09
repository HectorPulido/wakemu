# Native execution-context field 13

## Proven scalar contract

Original `eZR.c(iP)` serializes field 13 only when its current `PS` is an
`eVt`. The owner fields 9/10 and additional payload field 12 are independent.
Original `eVt.fLV()` constructs `ir` with explicit fields 1, 2, 4, 5, 6, 7,
8 and 9. False booleans and the NONE enum are serialized explicitly.

The original constructor initializes probability bypass=false, criterion
bypass=false, selection=-1, `ban`=true, forced value=0, `mc`=false,
`bbI`=false and forced mode=NONE (0). The source runner pointer is null and
is not an `ir` field. SET and PERCENT have native enum values 1 and 2.
The new typed scalar serializer preserves these facts and the original
SP/mb/mc/fLQ/force scalar mutations. Negative int32 values use protobuf's
sign-extended ten-byte varint.

## Validation

`ProbeNativeExecutionContext.java` executes the installed original constructor,
then actual scalar mutators. Its fresh and mutated serialized bytes match the
two Python regression fixtures exactly. Three Python tests pass, including
unknown boolean, int32 overflow and forcing with NONE rejection.

## Open producer boundary

The installed native callers inspected so far include client previews (`aJu`
and `fpN`). They do not prove the normal server dispatch constructor or its
mutations. The Python cast implementation alone cannot establish an original
normal-server `PS` identity. Consequently the constructor helper explicitly
does not certify that a dispatch has a fresh context; factory context13
binding remains pending that authority. No preview flags, selected variant,
or inferred all-false context are substituted. Source-runner propagation and
clone/fLP authority remain separate unclosed contracts.
