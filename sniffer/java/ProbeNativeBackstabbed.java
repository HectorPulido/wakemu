import java.lang.reflect.*;
import java.util.*;

/** Execute eNn/eIG and Sl.o from the original client, without replacing them. */
public class ProbeNativeBackstabbed {
    static class Actor extends ProbeNativeLevelGroup.Actor {
        int x, y; short z; Sl locator;
        public int bcz() { return x; }
        public int bcA() { return y; }
        public short bcB() { return z; }
        public Sl baB() { return locator; }
    }
    static Actor actor(int x, int y, int z, int direction) throws Exception {
        Field field = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        sun.misc.Unsafe unsafe = (sun.misc.Unsafe) field.get(null);
        Actor result = (Actor) unsafe.allocateInstance(Actor.class);
        result.x = x; result.y = y; result.z = (short)z;
        result.locator = new Sl();
        result.locator.a(x, y, (short)z, aAS.wL(direction));
        return result;
    }
    static eNn criterion(String selector) {
        ArrayList<alS> args = new ArrayList<>();
        if (selector != null) args.add(new amc(selector));
        return new eNn(args);
    }
    static void check(eNn c, Object caster, Object target, int expected) {
        int actual = c.a(caster, target, null, null);
        if (actual != expected) throw new AssertionError(actual + " != " + expected);
    }
    public static void main(String[] ignored) throws Exception {
        Actor caster = actor(0,0,0,1), target = actor(-1,0,0,5);
        check(criterion(null), caster, target, 0);
        check(criterion("anything"), caster, target, 0);
        check(criterion("TARGET"), caster, target, 0);
        check(criterion(null), null, null, -1);
        check(criterion("target"), caster, null, -1);
        check(criterion(null), caster, new aBn(-1,0,(short)0), -1);
        target.locator = null;
        check(criterion("target"), caster, target, -1);
        Object nonFighter = Proxy.newProxyInstance(eHg.class.getClassLoader(),
            new Class[]{eHg.class}, (p,m,a) -> {throw new AssertionError(m);});
        check(criterion(null), nonFighter, caster, -1);
        System.out.println("CONTRACT PASS selectors/null/nonfighter/nonPV/locator:8; noFacingProperty="+ffe.ser.aKg());
        int[][] points={{0,0,0},{0,0,1},{1,0,0},{-1,0,0},{0,1,0},{0,-1,0},
            {1,1,0},{-1,1,0},{1,-1,0},{-1,-1,0},{10,9,0},{10,11,0},
            {Integer.MIN_VALUE,0,0},{Integer.MAX_VALUE,0,0}};
        for(int direction=0;direction<8;direction++) {
            caster=actor(0,0,0,direction);
            for(int[] point:points) {
                target=actor(point[0],point[1],point[2],1);
                int result=criterion(null).a(caster,target,null,null);
                System.out.println("ROW "+direction+" "+point[0]+" "+point[1]+" "+point[2]+" "+result);
            }
        }
        caster=actor(Integer.MIN_VALUE,0,0,1); target=actor(Integer.MAX_VALUE,0,0,1);
        System.out.println("OVERFLOW "+criterion(null).a(caster,target,null,null));
        System.exit(0);
    }
}
