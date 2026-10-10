# Pesante targeting in Dragon form

Incident: the 2026-10-10 06:28:38 UTC screenshot showed Pesante7313 selected against Iop4 while Osamodas13 had 2 AP and 1 MP. The server log contains no7313 request or rejection during that window. Its last movement at06:28:14.692 left Osamodas at(-130,-30,0), Iop at(-132,-30,0): native distance2. This is not evidence of a range failure.

The published original casting definition has the following criterion:

```
not #HasState(7123, "caster")#
or #HasState(7123, "caster")# and #((GetEffectCaster() == GetEffectTarget()) or HasStateFromUser(7134, "target"))#
```

The level200 Dragon conditional table preserves cost2 AP, range1–2, adjustable range and LOS, and enables self-targeting. Therefore, with Forma Dracónica7123 active, the permitted target is the caster itself or a target carrying Invocación7134 from that caster. It is not an unrestricted enemy attack in that form. The actual Iop target ledger in this window contains4464,7553,8920,8918,3464,3442, and no7134. Osamodas13 has7123. The native target criterion consequently rejects that Iop even though resources and range are sufficient. No server-side relaxation or spell-specific patch is justified.

Localization provenance: original `i18n_es.jar/texts_es.properties`, `content.3.7313=Pesante`, `content.8.7123=Forma Dracónica`, `content.8.7134=Invocación`. Spell and state localization namespaces are distinct.

Verification uses the current published `native-spell-casting.json` entry7313 and bounded server-log records. A bounded original Java probe also resolves all six level200 root definitions; no definition is missing. This establishes the target prerequisite, not a live client LOS measurement. Manual acceptance: while in Dragon form, select Pesante and target the caster or its marked owned summon; an unmarked enemy remains unavailable under the original rule.

The original Java subtree further confirms the center semantics: root326667 requires Dragon and either self or `HasStateFromUser(7134, "target") and IsOwnSummon("target")`. Its normal Dragon child326668 has `ring-1-1` geometry, with damage326669 and characteristic effects326671/326672. A separate shape branch326673 is selected with passive7333 and no8909. Thus the chosen self/summon is the area center, not an enemy that must first be marked. Original-probe source and output are retained privately under `.runtime/combat-review-20261010/pesante/`.
