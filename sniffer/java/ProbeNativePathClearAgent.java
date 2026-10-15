import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;

/** Offline-only verification agent: transforms acS inside the real application loader. */
public final class ProbeNativePathClearAgent {
    public static void premain(String args, Instrumentation instrumentation) {
        instrumentation.addTransformer(new ClassFileTransformer() {
            @Override public byte[] transform(ClassLoader loader, String name, Class<?> type, ProtectionDomain domain, byte[] bytes) {
                return name.equals("acS") ? CaptureAgent.movementPathCleared(bytes) : null;
            }
        });
    }
}
