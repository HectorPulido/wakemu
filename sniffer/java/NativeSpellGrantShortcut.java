/** Idempotent shortcut insertion only at the original eWn temporary-grant callsite. */
public final class NativeSpellGrantShortcut {
    private NativeSpellGrantShortcut() {}

    public static fyt ensure(eGj actor, byte barIndex, short slot, fyG<?> spell) {
        if (actor instanceof big fighter && spell != null && fighter.doz()
                && fighter.dpt() instanceof buH fight && fight.rj(fighter.Sn()) == fighter) {
            // Preserve bje.a's own local-controller gate before returning a shortcut.
            boolean owned = !(fighter instanceof bje)
                    || (fighter.dnG() != null && aTx.cWt().cWu() != null
                    && fighter.dnG().Xi() == aTx.cWt().cWu().Xi());
            if (owned) {
                bOY manager = fighter.dpp();
                bOX bar = manager == null ? null : manager.c(fyv.tuO, barIndex);
                bOS existing = bar == null ? null : bar.lY(spell.LV());
                if (existing != null && existing.gtr() == fyw.tvb
                        && existing.awe() == spell.awe()
                        && existing.gts() == spell.bwX()) {
                    return existing;
                }
            }
        }
        return actor.a(barIndex, slot, spell);
    }
}
