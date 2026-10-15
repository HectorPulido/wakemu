/** Restore native eYc private selection operands at decoded cvX execution. */
public final class NativeDecodedAreaRemoval {
    private NativeDecodedAreaRemoval() {}

    static boolean initialize(eZR runner, boolean immediate) {
        if (!immediate || !(runner instanceof eYc removal) || removal.baZ() == null) return false;
        // eYc does not serialize rFc/rFd/rFe. Its original C only reads the
        // installed definition and actual container level; it changes no stats.
        removal.C(null);
        // aVo.cYg clears Qe.bfD before applying a decoded runner. eYc.c
        // requires this gate even for an authoritative immediate removal.
        removal.bbr();
        return true;
    }

    public static void execute(eZR runner, Qe source, boolean forced) {
        initialize(runner, forced);
        runner.a(source, forced);
    }
}
