import java.lang.reflect.Field;
import java.lang.reflect.Method;

/** Original aTS final-state dispatcher, with explicit fight collection boundaries. */
public class ProbeNativeFighterRemovalDispatch {
    static class Actor extends ProbeNativeFightersBreedRange.A {
        Fight fight;
        boolean offPlay;
        boolean fled;
        public buH doI() { return fight; }
        public boolean baG() { return offPlay; }
        public void lC(boolean value) { fled = value; }
    }
    static class Fight extends buH {
        int offPlayCalls;
        int outOfPlayCalls;
        Fight() { super(0, null, null, null, null); }
        public boolean aC(big actor) {
            offPlayCalls++;
            ((Actor) actor).offPlay = true;
            return true;
        }
        public boolean aD(big actor) {
            outOfPlayCalls++;
            return true;
        }
    }
    static void check(boolean value, String label) {
        if (!value) throw new AssertionError(label);
        System.out.println("PASS " + label);
    }
    public static void main(String[] args) throws Exception {
        Field state = aTS.class.getDeclaredField("htE");
        state.setAccessible(true);
        Method dispatch = aTS.class.getDeclaredMethod("E", big.class);
        dispatch.setAccessible(true);
        for (byte mode : new byte[] {0, 2, 3}) {
            Actor actor = (Actor) ProbeNativeFightersBreedRange.U.allocateInstance(Actor.class);
            Fight fight = (Fight) ProbeNativeFightersBreedRange.U.allocateInstance(Fight.class);
            actor.fight = fight;
            aTS action = (aTS) ProbeNativeFightersBreedRange.U.allocateInstance(aTS.class);
            state.setByte(action, mode);
            dispatch.invoke(action, actor);
            check(fight.offPlayCalls == 1, "state " + mode + " ensures off-play");
            check(fight.outOfPlayCalls == (mode == 0 ? 0 : 1),
                    "state " + mode + " final-removal dispatch");
            check(actor.fled == (mode == 3), "state " + mode + " flee flag");
        }
        System.out.println("9 original aTS dispatcher assertions PASS; no GUI/session claim");
    }
}
