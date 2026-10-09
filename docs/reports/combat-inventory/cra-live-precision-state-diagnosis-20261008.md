# Live Cra conditional LOS diagnosis

Read-only fight58/map527/actor6 level50 logs show state3420 level30 and Tiro Preciso7757 level1, but no state7792 before either Buscadora4813 request at16:59:04 or16:59:09 UTC. Native state-name keys distinguish3420 **Esquivo**,7792 **Precisión**,7757 **Tiro Preciso**. Esquivo's level30 cannot satisfy `GetStateLevel(7792)>=30`.

Tiro Preciso was enabled at16:57:43: native effect347093 completed. Both subsequent Buscadora casts reached the actual owner postcast1025 listener350554 and branch352070. Its state producer350575 was skipped with the exact native criterion `not HasState(7757,"caster")`. Thus these casts intentionally did not install the7793 carrier which produces Precision7792. This is a legitimate native branch, not evidence that304/2287 or LOS state lookup lost an existing Precision state.

A source-proven preparation route is to build Precision before enabling Tiro Preciso. Fulminante4820 is selected by postcast branch352071 and creates its level3 precision carrier; state7793's effect349856 applies7792 with parameter growth10 (30 at carrier level3). The earlier actual normal-cast Precision/wall transaction evidence covers this order. Enabling Tiro Preciso first prevents this preparation branch. Already having Esquivo30 does not change the requirement.

Both live requests succeeded as ordinary casts; absent Precision means the native LOS-required table remains selected. Whether a specific requested ray is genuinely blocked must be checked separately against its native geometry. This evidence does not claim the live client displayed Precision correctly or that those two accepted targets were behind a native blocking wall.

Curated JSON includes only relevant before/after state and effect trace records, with log-tail checksum. No services, databases or casting tests were used.
