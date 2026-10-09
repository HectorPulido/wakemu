/** Stack-preserving adapter for the original native UI query. */
public final class NativeSpellPreflight {
    private NativeSpellPreflight() {}

    public static fyJ query(buH fight, eGj caster, fyG book, aBn cell, boolean check) {
        fyJ original = fight.a(caster, book, cell, check);
        if (cell != null || !check) return original;
        return (fyJ) NativeSpellAvailability.withNativeContext(original, fight, caster, book);
    }
}
