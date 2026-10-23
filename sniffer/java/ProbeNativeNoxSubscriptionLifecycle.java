import java.nio.file.Path;
import java.util.BitSet;

/** Original selection/registration probe, not a combat or phase simulation. */
public final class ProbeNativeNoxSubscriptionLifecycle {
    static int checks;
    static void check(boolean condition, String label) {
        if (!condition) throw new AssertionError(label);
        checks++;
    }
    static BitSet event(int value) {
        BitSet events = new BitSet(); events.set(value); return events;
    }
    static final class Manager extends Qf {
        final Qi dispatcher = new eZX(this);
        public Qi bci() { return dispatcher; }
    }
    static final class Group extends eYg {
        int fired;
        Runnable callback;
        Group(int reference, long uid) {
            bfp = bcA.dcX().AH(reference);
            bfx = uid;
        }
        public void k(Qe source) {
            fired++;
            if (callback != null) callback.run();
        }
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        Group opening = new Group(401534, 9001);
        Group late = new Group(401610, 9002);
        Group phaseEnd = new Group(401540, 9003);
        check(opening.aZN() && late.aZN() && phaseEnd.aZN(), "actual Nox definitions subscribe");
        check(late.aZx() && !late.aZw(), "actual401610 global and nonreverse");
        check(late.bbv().get(1003), "actual401610 aZL receives1003");
        check(!late.bbw().get(1003), "actual401610 does not emit1003 through aZO");
        check(phaseEnd.bbv().get(1002) && phaseEnd.aZw(), "actual401540 receives reverse1002");

        Manager afterPastEvent = new Manager();
        check(!afterPastEvent.a(event(1003), null, (byte)61), "no listeners at historical1003");
        afterPastEvent.p(late);
        check(afterPastEvent.dk(9002) == late && late.bbp() == afterPastEvent, "original Qf.p registers and attaches");
        check(late.fired == 0, "registration does not replay historical1003");
        afterPastEvent.a(event(1002), null, (byte)61);
        check(late.fired == 0, "later1002 does not activate1003 listener");
        afterPastEvent.a(event(1003), null, (byte)61);
        check(late.fired == 1, "a genuine new matching1003 selects listener");

        Manager duringEvent = new Manager();
        Group bornDuringSelection = new Group(401610, 9012);
        opening.callback = () -> duringEvent.p(bornDuringSelection);
        duringEvent.p(opening);
        duringEvent.a(event(1003), null, (byte)61);
        check(opening.fired == 1, "original eZX selects existing1003 listener");
        check(duringEvent.dk(9012) == bornDuringSelection, "callback registers late listener");
        check(bornDuringSelection.fired == 0, "late listener does not join current selected-event snapshot");
        duringEvent.a(event(1003), null, (byte)61);
        check(bornDuringSelection.fired == 1, "late listener waits for the next matching publication");
        System.out.println("PASS " + checks + " original Qf/Qi/eZX registration and Nox definition-mask checks; no eager or historical-event replay");
    }
}
