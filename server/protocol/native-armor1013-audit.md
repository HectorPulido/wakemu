# Native eWx armor1013

eVi registry offset1507 constructs class1013 with eWx, not a displacement
runner. eWx extends eWQ with fixed ffw.shQ (ARMOR97). Its native C reads
amount0; coefficient mode1 defaults3. Modes0/1/2/3 select no armor bonus,
giver120 (only different actors), receiver121, or their sum. Each stage uses
float32 arithmetic and GS.B (floor), not a single rounding at the end.
Optional parameter2 selects signed-byte eVg elemental enum. Enum0 disables
mastery; enum1..6 read21/22/23/24/90/109 respectively, plus damage20,
critical52 or noncritical102 and applicable flags4/22/23/24 mastery.
Range and berserk use the previously audited eYE helpers, including HP+92.

Fresh eWx.rBA is0. It clamps requested armor to0..room before native eWQ.d
applies PA.nG, storing actual applied delta for removal. For ordinary player
eGj.frJ with ARMOR_MAX88 present, the cap is Math.round(int32(maxHP*88)/100f).
Parameter3==2 bypasses this cap. Ordinary NPCs without player master have no
cap. Room uses Java int32(cap-current97), clamped at0. Erosion89 is not used
on this path because native fNn assigns its local ignore flag true.
eWW.bbH/fMz rejects computed amount0 before application; frozen/clamped
postapplication delta0 remains an application when the initial amount passed.

AdditionalDatas12 stores97;19 stores room;25 stores preapplication request.
Native packet13497 applies;13560 removes the owned actual delta via eWQ.
The handler retains the original payload, state UID and native timer in the
existing central ownership machinery. It allocates fresh UID and uses the
common preview/outbox and removal route. No spell/class IDs select behavior.

ProbeNativeArmor runs the actual eWx and eWQ.d/fNM methods. All four modes
passed (100,150,120,170), with exact AdditionalDatas bytes matched in Python.
Four small tests cover arithmetic, cap/bypass, elemental mastery, application,
owned removal and zero-before-allocation. Real5030 level20 enemy common entry
passed with effect packets12613/13497, movement301 and preserved source
resources/rollback. Durable reports are in docs/reports/combat-inventory.
`armor1013-cross-breed-audit.json` records Sacro5030 and the distinct enemy
branch of Sadida925. `armor1013-sadida-ally-audit.json` validates the latter
spell's armor branch through the actual common entry on an ordinary allied
NPC (third ordinary NPC preserves the opposite team). It produced13497,
changed actor stats beyond costs, preserved source resources/rollback and
recorded stable source hashes. Reproduce using
`PYTHONPATH=server:server/tools python3 server/tools/audit_armor_ally.py 925 1 OUTPUT`.
Other attempted self roots preserve independent blockers: Pandawa4792 and
Mask7089 stop at LOS; Ougi7551 stops at GetAlliesCountInRange. These are not
reported as armor execution or complete class coverage.

Limits: subscribed/cloned eWx requiring a nonzero live rBA modifier is rejected
until that event field is authoritative. Nonordinary actor/master relationships
and unverified flags reject through explicit authority. This audit does not
claim full breed/passive gameplay or GUI validation; real entry reports retain
their first distinct upstream blocker.
