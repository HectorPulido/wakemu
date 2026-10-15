import java.util.LinkedHashMap;
import java.util.Map;

/** Readiness probes must not execute native or deliberately failing initializers. */
public final class ProbeNativeDiagnosticReadiness {
    static int poisonInitializations;
    static int readyInitializations;

    static class Poison {
        static { poisonInitializations++; fail(); }
        static void fail() { throw new IllegalStateException("Must not run from a diagnostic"); }
    }

    static class Ready {
        static { readyInitializations++; }
        static int value = 17;
    }

    public static void main(String[] args) throws Exception {
        String poison = "ProbeNativeDiagnosticReadiness$Poison";
        String good = "ProbeNativeDiagnosticReadiness$Ready";
        Map<String, Object> result = new LinkedHashMap<>();
        if (NativeDiagnosticReadiness.ready(result, poison)) throw new AssertionError("Uninitialized poison reported ready");
        if (!"not_ready".equals(result.get("status")) || poisonInitializations != 0) throw new AssertionError("Probe initialized poison");
        try { NativeDiagnosticReadiness.initializedClass(poison); throw new AssertionError("Guard accepted poison"); }
        catch (NativeDiagnosticReadiness.NotReady expected) { }
        if (poisonInitializations != 0) throw new AssertionError("Repeated probe initialized poison");
        try { Class.forName(poison); throw new AssertionError("Deliberate poison did not fail"); }
        catch (ExceptionInInitializerError expected) { }
        if (NativeDiagnosticReadiness.ready(new LinkedHashMap<>(), poison) || poisonInitializations != 1)
            throw new AssertionError("Failed initialization was accepted or repeated");
        if (NativeDiagnosticReadiness.ready(new LinkedHashMap<>(), good) || readyInitializations != 0)
            throw new AssertionError("Readiness initialized ordinary class");
        Class.forName(good); // Explicit application initialization, independent of diagnostics.
        if (!NativeDiagnosticReadiness.ready(new LinkedHashMap<>(), good) || readyInitializations != 1 || Ready.value != 17)
            throw new AssertionError("Initialized class was rejected or rerun");
        Map<String, Object> path = CombatPathDiagnostic.snapshot();
        Map<String, Object> areas = CombatAreaDiagnosticAgent.snapshot();
        if (!"not_ready".equals(path.get("status")) || !"not_ready".equals(areas.get("status")))
            throw new AssertionError("Combat startup diagnostic bypassed guard");
        for (String method : new String[]{"combatDiagnostic", "movementDiagnostic"}) {
            var diagnostic = CaptureAgent.class.getDeclaredMethod(method); diagnostic.setAccessible(true);
            Map<?, ?> state = (Map<?, ?>)diagnostic.invoke(null);
            if (!"not_ready".equals(state.get("status"))) throw new AssertionError(method + " bypassed guard");
        }
        try { NativeDiagnosticReadiness.initializedClass("dba"); throw new AssertionError("Combat probe initialized dba"); }
        catch (NativeDiagnosticReadiness.NotReady expected) { }
        if (poisonInitializations != 1) throw new AssertionError("Poison reinitialized during endpoint checks");
        System.out.println("PASS uninitialized/failing initializer untouched; initialized class ready exactly once; native path/areas/combat/movement startup returns not_ready without dba initialization");
    }
}
