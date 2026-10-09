import java.util.ArrayList;
import org.antlr.runtime.*;

/** Offline exact native predicate prototypes and unsupported/null target forms. */
public class ProbeNativeAreaPredicates {
    private static amb parse(String source, String expectedClass) {
        eQb lexer = new eQb(new ANTLRStringStream(source));
        CommonTokenStream tokens = new CommonTokenStream(lexer);
        eQd parser = new eQd(tokens);
        ArrayList<alS> expressions = parser.fGv();
        alS result = expressions.get(expressions.size() - 1);
        if (lexer.getNumberOfSyntaxErrors() != 0 || parser.getNumberOfSyntaxErrors() != 0
                || tokens.LA(1) != Token.EOF || !result.getClass().getName().equals(expectedClass)) {
            throw new AssertionError(source);
        }
        return (amb) result;
    }
    private static void rejects(String source) {
        try { parse(source, "unused"); } catch (alR expected) { return; }
        throw new AssertionError("Invalid native prototype accepted: " + source);
    }
    public static void main(String[] args) {
        for (amb predicate : new amb[]{parse("IsAreaType(12)", "eNm"),
                                       parse("IsSpecificArea(823)", "eOQ")}) {
            if (predicate.a(null, new Object(), null, null) != -2
                    || predicate.a(null, (Qz) () -> null, null, null) != -1) {
                throw new AssertionError("Native target form mismatch");
            }
        }
        for (String source : new String[]{"IsOwnDeposit()", "IsOwnDeposit(True)", "IsOwnDeposit(False)"}) {
            if (parse(source, "eOC").a(null, null, null, null) != -1) {
                throw new AssertionError("Null caster must reject");
            }
        }
        rejects("IsAreaType(12, \"target\")");
        rejects("IsSpecificArea(823, \"caster\")");
        rejects("IsOwnDeposit(12)");
        if (fbp.rNR.aIc() != 12) throw new AssertionError("Deposit type mismatch");
        System.out.println("PASS native eNm/eOQ numeric-only, eOC optional-boolean prototypes; "
                + "null/unsupported target forms and deposit type12");
    }
}
