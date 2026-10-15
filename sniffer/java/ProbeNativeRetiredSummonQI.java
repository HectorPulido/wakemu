import java.lang.reflect.*;

/** Original QI cleanup after premature pW/QK.M(-1), without UI or catalogs. */
public final class ProbeNativeRetiredSummonQI {
    static final class Grid extends QI {
        Grid() {
            bpZ = 0; bqa = 0; bqd = 4; bqe = 4;
            biD = new short[16]; biE = 16;
        }
    }
    static final class State implements InvocationHandler {
        byte slot = -1;
        final int x, y;
        State(int x, int y) { this.x = x; this.y = y; }
        QK actor() {
            return (QK) Proxy.newProxyInstance(QK.class.getClassLoader(),
                new Class<?>[]{QK.class}, this);
        }
        public Object invoke(Object actor, Method method, Object[] args) {
            return switch (method.getName()) {
                case "M" -> { slot = (Byte) args[0]; yield null; }
                case "bcN" -> slot;
                case "bcO", "bcP", "bcQ" -> true;
                case "bcz" -> x;
                case "bcA" -> y;
                case "bcL", "bcK" -> (byte) 0;
                case "equals" -> actor == args[0];
                case "hashCode" -> System.identityHashCode(actor);
                case "toString" -> "retired-native-summon";
                default -> throw new UnsupportedOperationException(method.getName());
            };
        }
    }
    public static void main(String[] args) {
        for (boolean prematureSnapshot : new boolean[]{true, false}) {
            Grid grid = new Grid();
            for (int n = 0; n < 6; n++) grid.f(new State(-1, -1).actor());
            State state = new State(1, 1);
            QK actor = state.actor();
            grid.f(actor);
            if (state.slot != 6 || !grid.g(1, 1, (short) 0))
                throw new AssertionError("Native slot6 birth must block its cell");
            if (prematureSnapshot) actor.M((byte) -1);
            // Native fcb.H -> aQ uses this exact QI.g(QK) cleanup method.
            grid.g(actor);
            boolean registered = grid.O((byte) 6) == actor;
            boolean occupied = grid.U(1, 1).contains((byte) 6);
            boolean blocked = grid.g(1, 1, (short) 0);
            if (registered != prematureSnapshot || occupied != prematureSnapshot
                    || blocked != prematureSnapshot || state.slot != -1)
                throw new AssertionError("Unexpected native final cleanup state");
            System.out.println("PASS " + (prematureSnapshot ? "OLD snapshot-1 then death" : "FIX death with original slot")
                + " slot6=" + registered + " footprint=" + occupied + " blocked=" + blocked);
        }
    }
}
