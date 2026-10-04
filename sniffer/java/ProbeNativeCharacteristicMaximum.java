import java.lang.reflect.Proxy;
import java.util.ArrayList;

/** Offline execution of the installed client's maximum characteristic predicate. */
public class ProbeNativeCharacteristicMaximum {
    static eHg actor(int maximum, boolean present) {
        return (eHg) Proxy.newProxyInstance(eHg.class.getClassLoader(),
            new Class<?>[]{eHg.class}, (proxy, method, args) -> switch (method.getName()) {
                case "a" -> present;
                case "d" -> maximum;
                case "toString" -> "maximum-probe";
                default -> throw new UnsupportedOperationException(method.getName());
            });
    }
    static eJA criterion(String alias, boolean target) {
        ArrayList<alS> parameters = new ArrayList<>();
        parameters.add(new amc(alias));
        if (target) parameters.add(new amc("target"));
        return new eJA(parameters);
    }
    static void expect(long actual, long expected) {
        if (actual != expected) throw new AssertionError(actual + " != " + expected);
    }
    public static void main(String[] args) {
        Object caster = actor(7, true), target = actor(100, true);
        expect(criterion("PA", false).d(caster, target, null, null), 7);
        expect(criterion("HP", true).d(caster, target, null, null), 100);
        expect(criterion("DMG_FIRE", false).d(actor(60, true), target, null, null), 60);
        expect(criterion("ARMOR", false).d(actor(0, false), target, null, null), -1);
        expect(criterion("HP", false).d(null, target, null, null), -1);
        System.out.println("Native maximum: PA=7, target HP=100, DMG_FIRE=60, absent PC/actor=-1; PASS");
    }
}
