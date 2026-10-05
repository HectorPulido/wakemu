import java.lang.reflect.Field;
import java.util.ArrayList;

/** Native eNw uses frA/pGV, independent of carried buX/pGW. */
public class ProbeNativeIsCarrying {
    static eNw criterion(String selector) {
        ArrayList<alS> arguments = new ArrayList<>();
        if (selector != null) arguments.add(new amc(selector));
        return new eNw(arguments);
    }
    public static void main(String[] args) throws Exception {
        biB caster = new biB(false), target = new biB(false);
        Field carried = eGj.class.getDeclaredField("pGV");
        carried.setAccessible(true);
        carried.set(caster, target);
        if (!caster.frA() || caster.buX() || target.frA()) throw new AssertionError("separate native relations");
        if (criterion(null).a(caster, target, null, null) != 0 || criterion("other").a(caster, target, null, null) != 0) throw new AssertionError("default caster");
        if (criterion("TaRgEt").a(caster, target, null, null) != -1 || criterion(null).a(null,target,null,null) != -1) throw new AssertionError("target/null");
        System.out.println("eNw default and arbitrary strings caster; target case-insensitive; pGV independent from pGW");
        System.exit(0);
    }
}
