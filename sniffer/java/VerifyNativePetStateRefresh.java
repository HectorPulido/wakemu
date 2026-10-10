import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;

/** Standalone oracle for NativePetStateRefresh.reconcileState. */
public final class VerifyNativePetStateRefresh {
    private VerifyNativePetStateRefresh() {}

    public static void main(String[] args) {
        fwr model = (fwr) Proxy.newProxyInstance(
                fwr.class.getClassLoader(), new Class<?>[] {fwr.class}, new ModelHandler());
        fvN original = pet(model, 100, 100, "old", 0, 1);
        fvN latest = pet(model, 73, 73, "refreshed", 50, 2);
        int[] callbacks = {0};
        fvO observer = (fvO) Proxy.newProxyInstance(
                fvO.class.getClassLoader(), new Class<?>[] {fvO.class}, new ObserverHandler(callbacks));
        require(original.a(observer), "observer registration failed");

        fvH returned = NativePetStateRefresh.reconcileState(original, latest);
        require(returned == original, "refresh did not preserve native pet identity");
        require(original.agO() == 50, "XP was not updated to 50: " + original.agO());
        require(original.agN() == 73, "health was not updated to 73: " + original.agN());
        require("refreshed".equals(original.getName()), "name was not refreshed");
        require(original.gpJ().equals(latest.gpJ()), "first date was not refreshed");
        require(original.gpV().equals(latest.gpV()), "second date was not refreshed");
        require(original.gpL().equals(latest.gpL()), "third date was not refreshed");
        require(callbacks[0] > 0, "native observer received no callbacks");

        fvH repeated = NativePetStateRefresh.reconcileState(original, latest);
        require(repeated == original, "idempotent refresh changed identity");
        fvN nonPet = pet(model, 100, 0, "untouched", 0, 3);
        fvH nonPetResult = NativePetStateRefresh.reconcileState(nonPet, nonPet);
        require(nonPetResult == nonPet, "same native pet snapshot should pass through unchanged");

        try {
            Class.forName("fnR");
        } catch (ClassNotFoundException e) {
            throw new AssertionError("fnR native client class did not load", e);
        }

        fvN remembered = pet(model, 100, 0, "retained", 0, 4);
        require(NativePetStateRefresh.reconcileSnapshot(987L, null, remembered) == remembered,
            "initial snapshot identity");
        fvN replacement = pet(model, 73, 0, "retained", 50, 5);
        require(NativePetStateRefresh.reconcileSnapshot(987L, null, replacement) == remembered,
            "registry removal must not abandon panel state");
        require(remembered.agO() == 50, "detached panel XP must refresh");

        fnR emptyItem = new fnR(123L);
        emptyItem.f(null);
        emptyItem.a((wS) null);
        require(!emptyItem.adO(), "empty hydration must remain unchanged");
        require(NativePetStateRefresh.reconcile(emptyItem, null) == null, "non-pet passthrough");

        System.out.println("PASS identity, XP, health, name, dates, observer callbacks, idempotency, non-pet passthrough");
        System.exit(0);
    }

    private static fvN pet(fwr model, int health, int currentHealth, String name, int xp, int seed) {
        TP timestamp = TP.fl(1_700_000_000_000L + seed * 1000L);
        fvN pet = new fvN();
        pet.a(model, timestamp);
        pet.setName(name);
        pet.Yz(currentHealth);
        pet.YA(seed);
        pet.YB(seed + 1);
        pet.mb(xp);
        pet.ad(TP.fl(timestamp.bjC() + 10_000L));
        pet.ae(TP.fl(timestamp.bjC() + 20_000L));
        pet.ag(TP.fl(timestamp.bjC() + 30_000L));
        pet.Yy(seed + 2);
        pet.Yz(health);
        return pet;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static final class ModelHandler implements InvocationHandler {
        @Override public Object invoke(Object proxy, Method method, Object[] args) {
            switch (method.getName()) {
                case "agN": return 100; // max health
                case "csW": return (short) 100; // XP factor used by mb()
                case "aWa": return (short) 10; // max level
                case "gqA": return 1;
                case "d": return 1;
                case "toString": return "NativePetTestModel";
                case "hashCode": return System.identityHashCode(proxy);
                case "equals": return proxy == args[0];
                default: return defaultValue(method.getReturnType());
            }
        }
    }

    private static final class ObserverHandler implements InvocationHandler {
        private final int[] callbacks;
        ObserverHandler(int[] callbacks) { this.callbacks = callbacks; }
        @Override public Object invoke(Object proxy, Method method, Object[] args) {
            if (method.getDeclaringClass() == fvO.class) callbacks[0]++;
            if (method.getName().equals("toString")) return "NativePetTestObserver";
            if (method.getName().equals("hashCode")) return System.identityHashCode(proxy);
            if (method.getName().equals("equals")) return proxy == args[0];
            return defaultValue(method.getReturnType());
        }
    }

    private static Object defaultValue(Class<?> type) {
        if (!type.isPrimitive() || type == void.class) return null;
        if (type == boolean.class) return false;
        if (type == char.class) return '\0';
        if (type == byte.class) return (byte) 0;
        if (type == short.class) return (short) 0;
        if (type == int.class) return 0;
        if (type == long.class) return 0L;
        if (type == float.class) return 0f;
        if (type == double.class) return 0d;
        return null;
    }
}
