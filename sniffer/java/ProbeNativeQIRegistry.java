import java.lang.reflect.*;

/** QI.f/j/g slot authority using the original client, without catalogs. */
public class ProbeNativeQIRegistry {
    static class Grid extends QI {
        Grid() {
            bpZ = 0; bqa = 0; bqd = 4; bqe = 4;
            biD = new short[16]; biE = 16;
        }
    }
    static class ObjectState implements InvocationHandler {
        byte slot = -1;
        int x, y;
        boolean eligible;
        ObjectState(int x, int y, boolean eligible) {
            this.x = x; this.y = y; this.eligible = eligible;
        }
        QK proxy() {
            return (QK) Proxy.newProxyInstance(QK.class.getClassLoader(),
                new Class<?>[]{QK.class}, this);
        }
        public Object invoke(Object proxy, Method method, Object[] args) {
            switch (method.getName()) {
                case "M": slot = (Byte) args[0]; return null;
                case "bcN": return slot;
                case "bcO": return eligible;
                case "bcP": case "bcQ": return false;
                case "bcz": return x;
                case "bcA": return y;
                case "bcL": case "bcK": return (byte) 0;
                case "equals": return proxy == args[0];
                case "hashCode": return System.identityHashCode(proxy);
                case "toString": return "native-probe-qk";
                default:
                    Class<?> result = method.getReturnType();
                    if (result == boolean.class) return false;
                    if (result == byte.class) return (byte) 0;
                    if (result == short.class) return (short) 0;
                    if (result == int.class) return 0;
                    if (result == long.class) return 0L;
                    return null;
            }
        }
    }
    public static void main(String[] args) {
        Grid grid = new Grid();
        ObjectState outside = new ObjectState(-1, 1, true);
        QK first = outside.proxy(); grid.f(first);
        if (outside.slot != 0 || grid.U(0, 1) != null) throw new AssertionError("outside reserve");
        ObjectState inside = new ObjectState(1, 1, true);
        QK second = inside.proxy(); grid.f(second);
        if (inside.slot != 1 || !grid.U(1, 1).contains((byte) 1)) throw new AssertionError("inside reserve");
        grid.g(first);
        if (outside.slot != -1) throw new AssertionError("remove reset");
        ObjectState hole = new ObjectState(1, 1, true); grid.f(hole.proxy());
        if (hole.slot != 0) throw new AssertionError("first free hole");
        ObjectState ignored = new ObjectState(1, 1, false); grid.f(ignored.proxy());
        if (ignored.slot != -1) throw new AssertionError("bcO false");
        grid.a(second, false);
        if (inside.slot != 1 || grid.U(1, 1).contains((byte) 1)) throw new AssertionError("toggle keeps slot");
        grid.a(second, 2, 2); inside.x = 2; inside.y = 2;
        if (!grid.U(2, 2).contains((byte) 1)) throw new AssertionError("move reindexes toggled object");
        grid.a(second, -1, 2); inside.x = -1; inside.y = 2;
        if (grid.U(2, 2).contains((byte) 1)) throw new AssertionError("outside move removes membership");
        grid.a(second, true);
        if (inside.slot != 1 || grid.U(0, 2) != null) throw new AssertionError("outside toggle");
        for (int i = 2; i < 127; i++) {
            ObjectState state = new ObjectState(-1, 1, true); grid.f(state.proxy());
            if (state.slot != i) throw new AssertionError("ordered capacity " + i);
        }
        ObjectState full = new ObjectState(-1, 1, true); grid.f(full.proxy());
        if (full.slot != -1) throw new AssertionError("capacity exhausted");
        System.out.println("PASS original QI: first-free, out-of-bounds reservation, removal, bcO false, 127-slot capacity");
    }
}
