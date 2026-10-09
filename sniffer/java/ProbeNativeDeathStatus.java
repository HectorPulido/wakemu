import java.lang.reflect.Field;

/** Original eGj.dsA/gg with actual bjm status and explicit world predicate. */
public class ProbeNativeDeathStatus {
    static class Actor extends ProbeNativeLevelGroup.Actor {
        boolean worldDead;
        boolean inFight;
        public boolean dnz() { return inFight; }
        public boolean i(PE property) { return property == eHQ.pSA && worldDead; }
    }
    public static void main(String[] args) throws Exception {
        Actor actor = new Actor();
        bjm status = new bjm();
        Field field = eGj.class.getDeclaredField("pGC");
        field.setAccessible(true);
        field.set(actor, status);
        if (actor.baF()) throw new AssertionError("Detached baF");
        actor.inFight = true;
        if (actor.baF()) throw new AssertionError("Null fcb cannot be IN_PLAY");
        if (actor.dsA() || status.dsA()) throw new AssertionError("Fresh status");
        actor.gg(true);
        if (!actor.dsA() || !status.dsA()) throw new AssertionError("Actual gg true");
        actor.gg(false);
        if (actor.dsA() || status.dsA()) throw new AssertionError("Actual gg false");
        actor.worldDead = true;
        if (!actor.dsA()) throw new AssertionError("World DEAD");
        actor.gg(true);
        if (status.dsA()) throw new AssertionError("Compound guard must skip mwD write");
        actor.worldDead = false;
        if (actor.dsA()) throw new AssertionError("World removal must not leave invented mwD");
        System.out.println("8 native death-status assertions PASS");
    }
}
