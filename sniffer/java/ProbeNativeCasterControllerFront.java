import java.lang.reflect.Field;
import java.lang.reflect.Proxy;
import java.util.ArrayList;

/** eKa reads listener bbb; eNP uses the installed eIG/Sl facing contract. */
public final class ProbeNativeCasterControllerFront {
    static int checks;
    static void expect(long actual, long expected) {
        if (actual != expected) throw new AssertionError(actual + " != " + expected);
        checks++;
    }
    static eNP front(String selector) {
        ArrayList<alS> args = new ArrayList<>();
        if (selector != null) args.add(new amc(selector));
        return new eNP(args);
    }
    public static void main(String[] args) throws Exception {
        eKa controller = new eKa(new ArrayList<alS>());
        eHg original = (eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),
            new Class<?>[]{eHg.class, PV.class}, (p,m,a) -> {
                if (m.getName().equals("dTD")) return 91L;
                throw new UnsupportedOperationException(m.getName());
            });
        eXE listener = new eXE();
        Field caster = Qe.class.getDeclaredField("bfr"); caster.setAccessible(true);
        caster.set(listener, original);
        expect(controller.d(null, null, listener, null), 91);
        expect(controller.d(null, original, listener, null), 91);
        expect(controller.d(original, original, null, null), 0);
        caster.set(listener, null);
        expect(controller.d(original, original, listener, null), 0);
        try {
            controller.d(null, null, original, null);
            throw new AssertionError("non-Qe should reject");
        } catch (alA expected) { checks++; }
        ProbeNativeBackstabbed.Actor selected = ProbeNativeBackstabbed.actor(0,0,0,1);
        ProbeNativeBackstabbed.Actor opposite = ProbeNativeBackstabbed.actor(1,0,0,5);
        expect(front(null).a(selected, opposite, null, null), 0);
        expect(front("anything").a(selected, opposite, null, null), 0);
        expect(front("TARGET").a(selected, opposite, null, null), 0);
        expect(front(null).a(selected, new aBn(1,0,(short)0), null, null), -1);
        expect(front(null).a(null, opposite, null, null), -1);
        int[][] points = {{0,0,0},{0,0,1},{1,0,0},{-1,0,0},{0,1,0},{0,-1,0},
            {1,1,0},{-1,1,0},{1,-1,0},{-1,-1,0},{10,9,0},{10,11,0},
            {Integer.MIN_VALUE,0,0},{Integer.MAX_VALUE,0,0}};
        for (int direction=0; direction<8; direction++) {
            selected = ProbeNativeBackstabbed.actor(0,0,0,direction);
            for (int[] point : points) {
                opposite = ProbeNativeBackstabbed.actor(point[0],point[1],point[2],1);
                System.out.println("ROW " + direction + " " + point[0] + " " + point[1]
                    + " " + point[2] + " " + front(null).a(selected,opposite,null,null));
            }
        }
        System.out.println("PASS " + checks + " original caster-controller/front contract checks;112 native facing rows");
        System.exit(0);
    }
}
