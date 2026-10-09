# Captured summon family324 codec

`combat_captured_summon_codec` implements original `eZs.as`: two float32 scaling
factors, the selected captured `eHD` serialized through `vJ`, selected slot byte,
then `SQ` anchor byte/caster long/offset int. It does not use the family307
descriptor's self-control byte, property list or trailing team byte.

The caller supplies a typed `CapturedDescriptor` with actual minimum HP, owner
UID, native direction and symbiot flag. The plan supplies actual captured name,
profile, level, actor UID, factors and timeline settings; obstacle identity is
separate. The `vJ` auxiliary records are null because original `eHD.a(vJ)` clears
the structure and does not populate them. Native NONE direction is -1.

The family324 running envelope preserves independent effect/actor UIDs,
position, timing, context and container identity. Its initial running value is
0, matching `eZr.C` without an `aSg` write; callers may provide an authoritative
current value. The application uses family324 in packet13497.

`ProbeNativeCapturedSummonCodec` executes actual original `eZs.zt/as`, `eHD` and
`vJ` with nine combinations of UTF-8 names and signed minimum HP. All nine
payloads match Python byte-for-byte. Three unit tests passed, covering the
native differential, selected slot/family envelope and missing or mismatched
descriptor authority. The probe used128MB and no combat catalog, services,
database or client execution.
