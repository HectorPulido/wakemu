# Native healing contract

Evidence: bundled client eXs.fOA/fOC/c/fOz, eYE.a(int,far,PJ,PJ),
far.fd(byte), fat.fSy/fSD and Qe.bca; reproduced offline by
sniffer/java/ProbeHealingParameters.java. No official connection required.

Classes25/251/253/258/259 use eXs with native elemental constructor variants.
Its fOA accepts one to three evaluated parameters: base, coefficient mask
(default3), signed-byte far mode(defaultCLASSIC). The value-mode and HP
percentage conversion are identical to eXt: only real HP, Java int product
before float32 division, UP.bt stochastic rounding, invalid far bytes default
CLASSIC. Helper currently rejects negative results and unknown coefficient
bits rather than implementing their downstream behavior.

fOC passes rDv to fat.Tg (additional final healing). Bit1 of the coefficient
mask enables mastery and final bonuses, bit2 enables healing resistance.
SX accumulates rDv as a Java int. rDv is not a flat amount added after healing
and is not serialized as AdditionalDatas. Critical is effect.dd(1), distinct
from eVl flags. fat evaluates melee and ranged predicates independently:
forced flags23 and24 can both apply. Parameter p1 does not select the range.

The normal fOz branch heals real HP first, then virtual HP when its maximum
is positive. It subtracts any remaining overflow from aSg. The call eGj.PO
receives that final aSg, including both real and virtual HP gains. Qe.bca writes
the current aSg via iP.eL; eXs has no b(iP) override and no healing-specific
additional fields. Thus computed100 may serialize25 when capacity is25.

Undead targets convert to eXt unless native flag33
HEAL_EFFECT_BYPASS_UNDEAD_PROPERTY is present. Depending on the native
fKK/aZB booleans the synthetic effect IDs are -11/-3/-8/-12. This branch does
not run fOz; its healing runner value must not be mistaken for actual healed
HP. The helper identifies this branch but requires the runtime to execute
and serialize the child damage separately.

Limitations: fixture actor is PV, so the PO argument is proven from fOz's
bytecode rather than an eGj fixture. Generic codec shape is proven by Qe.bca
and the absence of eXs.b(iP), not by a new encoded packet fixture. Source and
target presence, HP characteristic existence, undead property, fKK/aZB,
critical variant and authoritative rounding are explicit caller inputs.
