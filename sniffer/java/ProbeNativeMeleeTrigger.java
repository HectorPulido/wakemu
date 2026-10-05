import java.lang.reflect.Proxy;
import java.util.ArrayList;

/** Actual eYE.b and ePa null-source contract; no game client or server. */
public class ProbeNativeMeleeTrigger {
    static PV actor(int x, int y, byte radius) {
        return (PV) Proxy.newProxyInstance(PV.class.getClassLoader(), new Class<?>[]{PV.class},
            (p,m,a)->switch(m.getName()) {
                case "bcz" -> x;
                case "bcA" -> y;
                case "bcL" -> radius;
                default -> throw new UnsupportedOperationException(m.getName());
            });
    }
    static eVn definition(boolean melee, boolean ranged) {
        return (eVn) Proxy.newProxyInstance(eVn.class.getClassLoader(), new Class<?>[]{eVn.class},
            (p,m,a)-> {
                if (m.getName().equals("a") && a.length == 1)
                    return a[0] == eVl.rwT ? melee : a[0] == eVl.rwU && ranged;
                throw new UnsupportedOperationException(m.getName());
            });
    }
    public static void main(String[] args) {
        int count=0;
        for (int distance : new int[]{0,2,3,100}) {
            for(boolean melee : new boolean[]{false,true}) {
                for(boolean ranged : new boolean[]{false,true}) {
                    boolean expected=melee || !ranged && distance<=2;
                    if(eYE.b(actor(0,0,(byte)0),actor(distance,0,(byte)0),definition(melee,ranged)) != expected)
                        throw new AssertionError("flag precedence/range");
                    count++;
                }
            }
        }
        if(!eYE.b(actor(0,0,(byte)1),actor(3,3,(byte)1),definition(false,false)))
            throw new AssertionError("native per-axis physical radius");
        if(new ePa(new ArrayList<alS>()).a(null,null,null,null) != -1)
            throw new AssertionError("null source");
        System.out.println("PASS "+(count+2)+" original melee contracts");
    }
}
