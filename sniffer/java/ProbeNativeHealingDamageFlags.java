import java.lang.reflect.*;
import java.util.*;

/** Actual eVl IDs and fat arithmetic for HP-loss-only flags on HP gain. */
public class ProbeNativeHealingDamageFlags {
    static eVn definition(Set<Integer> flags) {
        return (eVn) Proxy.newProxyInstance(eVn.class.getClassLoader(),
            new Class[]{eVn.class}, (proxy, method, args) -> {
                if (method.getName().equals("a") && args != null
                        && args.length == 1 && args[0] instanceof eVl flag)
                    return flags.contains((int) flag.fLK());
                if (method.getReturnType() == boolean.class) return false;
                if (method.getReturnType() == int.class) return 0;
                if (method.getReturnType() == short.class) return (short) 0;
                return null;
            });
    }

    static PV actor() {
        return (PV) Proxy.newProxyInstance(PV.class.getClassLoader(),
            new Class[]{PV.class}, (proxy, method, args) -> {
                if (method.getReturnType() == boolean.class) return false;
                if (method.getReturnType() == int.class) return 0;
                if (method.getReturnType() == short.class) return (short) 0;
                if (method.getReturnType() == byte.class) return (byte) 0;
                if (method.getReturnType() == long.class) return 1L;
                return null;
            });
    }

    public static void main(String[] args) throws Exception {
        Map<Integer, String> names = new HashMap<>();
        for (eVl flag : eVl.values()) names.put((int) flag.fLK(), flag.name());
        if (!"DONT_USE_BLOCK".equals(names.get(2))
                || !"BYPASS_ARMOR_AND_BARRIER".equals(names.get(28)))
            throw new AssertionError(names);
        eXs heal = null;
        for (Field field : eVi.class.getDeclaredFields()) {
            if (field.getType() != eVj.class) continue;
            field.setAccessible(true);
            eVj prototype = (eVj) field.get(null);
            if (prototype.d() == 25) heal = (eXs) prototype.bkv();
        }
        if (heal == null) throw new AssertionError("Missing native healing25");
        int cases = 0;
        for (Set<Integer> flags : List.of(Set.<Integer>of(), Set.of(2),
                Set.of(28), Set.of(2, 28))) {
            for (int mode = 0; mode < 4; mode++) {
                fat arithmetic = new fat(actor(), actor(), heal.dYF(), definition(flags));
                arithmetic.setValue(30);
                arithmetic.Tf(mode);
                arithmetic.Tg(0);
                arithmetic.mq(false);
                arithmetic.mw(false);
                arithmetic.fSy();
                if (arithmetic.getValue() != 30)
                    throw new AssertionError(flags + ":" + mode + "=" + arithmetic.getValue());
                cases++;
            }
        }
        System.out.println("PASS native healing damage-only flags2/28: " + cases + " cases");
    }
}
