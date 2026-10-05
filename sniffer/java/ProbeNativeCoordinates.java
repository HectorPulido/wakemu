import java.lang.reflect.Proxy;
import java.util.ArrayList;

/** Compare actual original coordinate criteria, including null and aBn. */
public class ProbeNativeCoordinates {
    static ArrayList<alS> args(String selector) {
        ArrayList<alS> result = new ArrayList<>();
        if (selector != null) result.add(new amc(selector));
        return result;
    }
    static eHg actor() {
        return (eHg) Proxy.newProxyInstance(eHg.class.getClassLoader(), new Class[]{eHg.class},
            (p,m,a) -> switch(m.getName()) {
                case "bcz" -> -12;
                case "bcA" -> 9;
                case "bcB" -> (short)-1;
                default -> throw new AssertionError(m);
            });
    }
    public static void main(String[] ignored) {
        eHg caster = actor();
        if(new eLT(args(null)).d(caster,null,null,null)!=-12) throw new AssertionError("caster");
        if(new eLT(args("anything")).d(caster,null,null,null)!=-12) throw new AssertionError("selector");
        aBn cell = new aBn(4,-7,(short)2);
        if(new eLT(args("TARGET")).d(caster,cell,null,null)!=4) throw new AssertionError("cell x");
        if(new eLU(args("target")).d(caster,cell,null,null)!=-7) throw new AssertionError("cell y");
        if(new eLW(args("target")).d(caster,cell,null,null)!=2) throw new AssertionError("cell z");
        if(new eLT(args(null)).d(null,null,null,null)!=Long.MIN_VALUE) throw new AssertionError("null");
        if(new eLW(args(null)).d(caster,null,null,null)!=-1) throw new AssertionError("actor z");
        System.out.println("PASS original eLT/eLU/eLW: 7 actor/cell/selector/null cases");
    }
}
