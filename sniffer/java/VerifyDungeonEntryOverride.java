import java.lang.reflect.Constructor;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Properties;

/** Offline native-parser and constructor-agent oracle; never starts the client. */
public final class VerifyDungeonEntryOverride {
    private static amb parse(String expression) throws Exception {
        org.antlr.runtime.ANTLRStringStream source =
            new org.antlr.runtime.ANTLRStringStream(expression);
        eQb lexer = new eQb(source);
        org.antlr.runtime.CommonTokenStream tokens =
            new org.antlr.runtime.CommonTokenStream(lexer);
        eQd parser = new eQd(tokens);
        List<?> values = parser.fGv();
        if (lexer.getNumberOfSyntaxErrors() != 0 || parser.getNumberOfSyntaxErrors() != 0
                || tokens.LA(1) != org.antlr.runtime.Token.EOF || values.isEmpty()
                || !(values.get(values.size() - 1) instanceof amb)) {
            throw new AssertionError("Native parser rejected criterion: " + expression);
        }
        return (amb) values.get(values.size() - 1);
    }

    private static boolean evaluate(amb criterion) {
        return criterion.b(null, null, null, null);
    }

    private static flF destination(int id, amb criterion) throws Exception {
        Constructor<flF> constructor = flF.class.getConstructor(
            int.class, int.class, int.class, int.class, int.class, short.class,
            aAS.class, amb.class, int.class, short.class, int.class, short.class,
            boolean.class, short.class, boolean.class, boolean.class, int.class);
        return constructor.newInstance(id, 0, 0, 0, 0, (short) 0,
            aAS.values()[0], criterion, 0, (short) 0, 0, (short) 0,
            false, (short) 0, false, false, 0);
    }

    public static void main(String[] args) throws Exception {
        boolean expectHashRejection = args.length == 1 && args[0].equals("expect-hash-rejection");
        if (args.length > (expectHashRejection ? 1 : 0)) {
            throw new IllegalArgumentException("Unexpected verifier arguments");
        }
        System.setProperty("wakfu.local.openDungeonMissions", "true");
        amb originalFalse = parse("IsNeoServer() and not IsNeoServer()");
        if (evaluate(originalFalse)) {
            throw new AssertionError("Native 1=0 criterion was not false before projection");
        }
        if (expectHashRejection) {
            try {
                OpenPlantingAgent.dungeonCriterion(4689, originalFalse);
                throw new AssertionError("Mismatched native client hash was accepted");
            } catch (IllegalStateException expected) {
                boolean mismatch = false;
                for (Throwable cause = expected; cause != null; cause = cause.getCause()) {
                    if (cause.getMessage() != null && cause.getMessage().contains("version mismatch")) {
                        mismatch = true;
                        break;
                    }
                }
                if (!mismatch) throw expected;
            }
            System.out.println("PASS native entrance override rejected mismatched client hash");
            return;
        }

        System.setProperty("wakfu.local.openDungeonMissions", "false");
        if (OpenPlantingAgent.dungeonCriterion(4689, originalFalse) != originalFalse
                || OpenPlantingAgent.patch("flF", new byte[] {0}) != null) {
            throw new AssertionError("Disabled opt-in changed the original native policy");
        }
        System.setProperty("wakfu.local.openDungeonMissions", "true");

        Properties rules = new Properties();
        try (var input = OpenPlantingAgent.class.getResourceAsStream("/dungeon-entry-overrides.properties")) {
            if (input == null) throw new AssertionError("Missing generated policy resource");
            rules.load(input);
        }
        int[] mapped = {720, 4578, 4689, 4714, 4751};
        for (int identity : mapped) {
            String expression = rules.getProperty(Integer.toString(identity));
            if (expression == null) throw new AssertionError("Missing mapping " + identity);
            amb projected = (amb) OpenPlantingAgent.dungeonCriterion(identity, originalFalse);
            if (projected == originalFalse) throw new AssertionError("Mapping not applied " + identity);
        }
        for (int identity : new int[] {4689, 4714}) {
            flF patched = destination(identity, originalFalse);
            if (!evaluate(patched.bdt())) {
                throw new AssertionError("Entrance mission criterion was not waived: " + identity);
            }
        }
        flF unrelated = destination(999, originalFalse);
        if (evaluate(unrelated.bdt())) {
            throw new AssertionError("Unmapped destination changed its original criterion");
        }
        System.out.println("PASS native flF/amb/eQb/eQd: mapped=5, waived=2, unrelated=false, opt-in=false-path=preserved");
    }
}
