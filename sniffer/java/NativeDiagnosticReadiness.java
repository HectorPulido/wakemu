import java.lang.reflect.Field;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.util.Map;
import sun.misc.Unsafe;

/** Diagnostics may inspect initialized game classes, never initialize them. */
public final class NativeDiagnosticReadiness {
    private static final Unsafe UNSAFE = unsafe();
    private static final MethodHandle SHOULD_INITIALIZE = initializationQuery();

    private NativeDiagnosticReadiness() {}

    private static Unsafe unsafe() {
        try {
            Field field = Unsafe.class.getDeclaredField("theUnsafe");
            field.setAccessible(true);
            return (Unsafe)field.get(null);
        } catch (ReflectiveOperationException error) {
            throw new ExceptionInInitializerError(error);
        }
    }

    public static final class NotReady extends IllegalStateException {
        NotReady(String name) { super("Native class is not initialized: " + name); }
    }

    private static MethodHandle initializationQuery() {
        try {
            // sun.misc.Unsafe removed this query in JDK22; the native query
            // remains on its internal delegate. Read it without opening game
            // modules or invoking ensureClassInitialized.
            Field delegate = Unsafe.class.getDeclaredField("theInternalUnsafe");
            delegate.setAccessible(true);
            Object internal = delegate.get(null);
            Field trusted = MethodHandles.Lookup.class.getDeclaredField("IMPL_LOOKUP");
            MethodHandles.Lookup lookup = (MethodHandles.Lookup)UNSAFE.getObject(
                UNSAFE.staticFieldBase(trusted), UNSAFE.staticFieldOffset(trusted));
            return lookup.findVirtual(internal.getClass(), "shouldBeInitialized",
                MethodType.methodType(boolean.class, Class.class)).bindTo(internal);
        } catch (ReflectiveOperationException error) {
            throw new ExceptionInInitializerError(error);
        }
    }

    @SuppressWarnings("removal")
    public static Class<?> initializedClass(String name) throws ClassNotFoundException {
        Class<?> type = Class.forName(name, false, NativeDiagnosticReadiness.class.getClassLoader());
        try {
            if ((boolean)SHOULD_INITIALIZE.invokeExact(type)) throw new NotReady(name);
        } catch (NotReady error) { throw error; }
        catch (Throwable error) { throw new NotReady(name); }
        return type;
    }

    public static boolean ready(Map<String, Object> result, String... names) {
        for (String name : names) {
            try { initializedClass(name); }
            catch (ClassNotFoundException | NotReady error) {
                result.put("status", "not_ready");
                result.put("native_class", name);
                return false;
            }
        }
        return true;
    }
}
