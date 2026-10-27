import java.lang.instrument.ClassFileTransformer;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.jar.JarFile;
import jdk.internal.org.objectweb.asm.ClassReader;
import jdk.internal.org.objectweb.asm.ClassVisitor;
import jdk.internal.org.objectweb.asm.MethodVisitor;
import jdk.internal.org.objectweb.asm.Opcodes;

/** Offline qualification: no native class loading, premain, inspector, or attachment. */
public final class VerifyObserverOnlyCaptureAgent {
    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static Map<String, List<String>> instructions(byte[] data) {
        Map<String, List<String>> methods = new HashMap<>();
        new ClassReader(data).accept(new ClassVisitor(Opcodes.ASM8) {
            @Override public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
                List<String> code = new ArrayList<>();
                methods.put(name + desc, code);
                return new MethodVisitor(Opcodes.ASM8) {
                    @Override public void visitInsn(int opcode) { code.add("op:" + opcode); }
                    @Override public void visitIntInsn(int opcode, int value) { code.add("int:" + opcode + ":" + value); }
                    @Override public void visitVarInsn(int opcode, int variable) { code.add("var:" + opcode + ":" + variable); }
                    @Override public void visitTypeInsn(int opcode, String type) { code.add("type:" + opcode + ":" + type); }
                    @Override public void visitFieldInsn(int opcode, String owner, String field, String descriptor) { code.add("field:" + opcode + ":" + owner + ":" + field + ":" + descriptor); }
                    @Override public void visitMethodInsn(int opcode, String owner, String method, String descriptor, boolean iface) { code.add("call:" + opcode + ":" + owner + ":" + method + ":" + descriptor + ":" + iface); }
                    @Override public void visitInvokeDynamicInsn(String name, String desc, jdk.internal.org.objectweb.asm.Handle handle, Object... args) { code.add("dynamic:" + name + desc + handle + Arrays.deepToString(args)); }
                    @Override public void visitJumpInsn(int opcode, jdk.internal.org.objectweb.asm.Label label) { code.add("jump:" + opcode); }
                    @Override public void visitLdcInsn(Object value) { code.add("ldc:" + value); }
                    @Override public void visitIincInsn(int variable, int value) { code.add("inc:" + variable + ":" + value); }
                    @Override public void visitTableSwitchInsn(int min, int max, jdk.internal.org.objectweb.asm.Label dflt, jdk.internal.org.objectweb.asm.Label... labels) { code.add("table:" + min + ":" + max + ":" + labels.length); }
                    @Override public void visitLookupSwitchInsn(jdk.internal.org.objectweb.asm.Label dflt, int[] keys, jdk.internal.org.objectweb.asm.Label[] labels) { code.add("lookup:" + Arrays.toString(keys) + ":" + labels.length); }
                    @Override public void visitMultiANewArrayInsn(String desc, int dimensions) { code.add("array:" + desc + ":" + dimensions); }
                };
            }
        }, 0);
        return methods;
    }

    public static void main(String[] args) throws Exception {
        Path library = Path.of(args[0]);
        Path agent = Path.of(args[1]);
        ClassFileTransformer transformer = CaptureAgent.networkTransformer();
        int untouched = 0;
        try (JarFile original = new JarFile(library.resolve("wakfu-client.jar").toFile())) {
            for (var entry : original.stream().filter(e -> e.getName().endsWith(".class")).toList()) {
                byte[] bytes = original.getInputStream(entry).readAllBytes();
                String name = entry.getName().substring(0, entry.getName().length() - 6);
                require(transformer.transform(null, name, null, null, bytes) == null, "Native class transformed: " + name);
                untouched++;
            }
        }
        require(untouched > 10000, "Incomplete original client inventory");
        int observerCalls = 0;
        try (JarFile netty = new JarFile(library.resolve("netty-transport-4.1.131.Final.jar").toFile())) {
            for (String name : Set.of("io/netty/channel/AbstractChannelHandlerContext", "io/netty/channel/AbstractChannel$AbstractUnsafe")) {
                byte[] original = netty.getInputStream(netty.getJarEntry(name + ".class")).readAllBytes();
                byte[] transformed = transformer.transform(null, name, null, null, original);
                require(transformed != null, "Transport observation absent: " + name);
                var before = instructions(original);
                var after = instructions(transformed);
                require(before.keySet().equals(after.keySet()), "Transport methods changed");
                for (var method : before.entrySet()) {
                    List<String> oldCode = method.getValue();
                    List<String> newCode = after.get(method.getKey());
                    if (oldCode.equals(newCode)) continue;
                    require(newCode.size() == oldCode.size() + 4, "Unexpected instruction change: " + method.getKey());
                    require(newCode.subList(4, newCode.size()).equals(oldCode), "Original transport instructions changed");
                    require(newCode.get(0).equals("var:25:0"), "Observer receiver changed");
                    require(newCode.get(3).startsWith("call:184:CaptureAgent:observe:") || newCode.get(3).startsWith("call:184:CaptureAgent:observeLifecycle:"), "Non-observer call inserted");
                    observerCalls++;
                }
            }
        }
        // Six context boundaries plus five unsafe boundaries (including both close overloads).
        require(observerCalls == 11, "Transport observation boundary count changed: " + observerCalls);
        int registrations = 0;
        int factories = 0;
        try (JarFile built = new JarFile(agent.toFile())) {
            for (var entry : built.stream().filter(e -> e.getName().endsWith(".class")).toList()) {
                require(!entry.getName().startsWith("NativeSpell") && !entry.getName().startsWith("NativeMovement") && !entry.getName().startsWith("NativePet") && !entry.getName().startsWith("NativeDecoded"), "Semantic helper packaged: " + entry.getName());
                byte[] bytes = built.getInputStream(entry).readAllBytes();
                String pool = new String(bytes, java.nio.charset.StandardCharsets.ISO_8859_1);
                for (String forbidden : List.of("NativeSpellPreflight", "NativeSpellAvailability", "NativeMovementStop", "NativePetStateRefresh", "NativeDecodedAreaRemoval", "/native-replay"))
                    require(!pool.contains(forbidden), "Forbidden semantic reference: " + forbidden);
                for (var method : instructions(bytes).values()) {
                    for (String instruction : method) {
                        if (instruction.contains(":java/lang/instrument/Instrumentation:addTransformer:")) registrations++;
                        if (instruction.contains(":CaptureAgent:networkTransformer:")) factories++;
                    }
                }
            }
        }
        require(registrations == 1 && factories == 1, "Unexpected transformer registration path");
        System.out.println("PASS native_classes_untouched=" + untouched + " transport_observer_prefixes=" + observerCalls + " transformer_registrations=" + registrations + " forbidden_helpers=0");
    }
}
