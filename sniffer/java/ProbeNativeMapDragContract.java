import java.io.InputStream;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import jdk.internal.org.objectweb.asm.*;

/** Audits the reachable native map palette path without patching client classes. */
public final class ProbeNativeMapDragContract {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    private static final class MethodFacts {
        final Set<String> calls = new HashSet<>();
        final List<String> events = new ArrayList<>();
        final Set<String> strings = new HashSet<>();
    }

    private static MethodFacts inspect(String owner, String method, String descriptor,
                                       boolean dropCaseOne) throws Exception {
        MethodFacts result = new MethodFacts();
        try (InputStream stream = ProbeNativeMapDragContract.class.getResourceAsStream("/" + owner + ".class")) {
            check(stream != null, "Missing installed class " + owner);
            new ClassReader(stream.readAllBytes()).accept(new ClassVisitor(Opcodes.ASM8) {
                public MethodVisitor visitMethod(int access, String name, String desc,
                                                 String signature, String[] exceptions) {
                    if (method != null && (!name.equals(method) || !desc.equals(descriptor))) return null;
                    return new MethodVisitor(Opcodes.ASM8) {
                        Label selected;
                        boolean recording = !dropCaseOne;
                        public void visitTableSwitchInsn(int min, int max, Label fallback, Label... labels) {
                            if (dropCaseOne && min <= 1 && max >= 1) selected = labels[1 - min];
                        }
                        public void visitLabel(Label label) {
                            if (dropCaseOne && label == selected) recording = true;
                        }
                        public void visitJumpInsn(int opcode, Label label) {
                            if (recording && dropCaseOne && opcode == Opcodes.GOTO) recording = false;
                        }
                        public void visitInsn(int opcode) {
                            if (recording) result.events.add("INSN " + opcode);
                        }
                        public void visitLdcInsn(Object value) {
                            if (recording && value instanceof String) result.strings.add((String)value);
                        }
                        public void visitFieldInsn(int opcode, String type, String field, String desc) {
                            if (recording) result.events.add("FIELD " + opcode + " " + type + "." + field);
                        }
                        public void visitMethodInsn(int opcode, String type, String name, String desc, boolean iface) {
                            if (recording) result.calls.add(type + "." + name + desc);
                        }
                        public void visitTypeInsn(int opcode, String type) {
                            if (recording) result.events.add("TYPE " + opcode + " " + type);
                        }
                    };
                }
            }, ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
        }
        return result;
    }

    private static void noCompassOrSocket(MethodFacts facts, String path) {
        check(facts.calls.stream().noneMatch(call -> call.startsWith("bLp.")
                || call.startsWith("axR.") || call.startsWith("java/net/")
                || call.startsWith("java/nio/channels/Socket")),
                path + " unexpectedly reaches compass or socket directly");
    }

    public static void main(String[] args) throws Exception {
        MethodFacts ui = inspect("cRI", null, null, false);
        check(ui.strings.contains("wakfu.map:onLandMarkDrag"), "Native map palette must bind drag handler");
        check(ui.strings.contains("wakfu.map:onMapClick(map)"), "Native map must bind map click handler");
        MethodFacts drag = inspect("cLa", "onLandMarkDrag", "(LfUd;)V", false);
        int modeWrite = drag.events.indexOf("FIELD " + Opcodes.PUTSTATIC + " cLa.gwo");
        check(modeWrite > 0 && drag.events.get(modeWrite - 1).equals("INSN " + Opcodes.ICONST_1),
                "Palette drag must select note mode1, not destination mode2");
        check(drag.events.contains("FIELD " + Opcodes.PUTSTATIC + " cLa.npJ"), "Palette drag must retain note icon");
        MethodFacts drop = inspect("cLa", "onDrop", "(LfUj;)V", true);
        check(drop.calls.contains("bLa.aa(III)LbUY;"), "Mode1 drop must create native personal note");
        check(drop.calls.contains("cLa.setCurrentNote(LbUY;)V"), "Mode1 drop must select new personal note");
        check(drop.calls.stream().noneMatch(call -> call.startsWith("bLc.a(")),
                "Mode1 drop must not invoke destination placement overload");
        noCompassOrSocket(drop, "Mode1 drop");
        MethodFacts save = inspect("cLa", "applyNote", "(LfQX;)V", false);
        check(save.calls.contains("bUZ.esc()V"), "Apply note must use native local persistence");
        noCompassOrSocket(save, "Apply note");
        MethodFacts constructor = inspect("bKM", "<init>", "()V", false);
        check(constructor.events.contains("TYPE " + Opcodes.NEW + " bLa")
                && constructor.events.contains("FIELD " + Opcodes.PUTFIELD + " bKM.kpl"),
                "Map context must own a newly allocated personal-note store");
        bUY note = new bUY(7, 12, -9, "native note", 4);
        check(note.getX() == 12 && note.getY() == -9 && note.hF().equals("native note"),
                "Original personal-note object must preserve coordinates and text");
        System.out.println("PASS actual cRI palette binding -> cLa drag mode1 -> onDrop creates bUY personal note");
        System.out.println("PASS mode1 drop/applyNote have no direct compass/socket calls; applyNote uses local persistence");
        System.out.println("PASS bKM allocates per-instance bLa; original bUY note preserves coordinates and text");
        System.out.println("LIMIT destination mode2 was not injected; GUI rendering and destination entry remain unverified");
    }
}
