import java.util.ArrayList;
import org.antlr.runtime.ANTLRStringStream;
import org.antlr.runtime.CommonTokenStream;
import org.antlr.runtime.Token;

/** Offline native SHARP expression grammar and alS localization metadata. */
public class ProbeNativeLocalMarkers {
    private static alS parse(String source) {
        eQb lexer = new eQb(new ANTLRStringStream(source));
        CommonTokenStream tokens = new CommonTokenStream(lexer);
        eQd parser = new eQd(tokens);
        ArrayList<alS> expressions = parser.fGv();
        if (lexer.getNumberOfSyntaxErrors() != 0 || parser.getNumberOfSyntaxErrors() != 0
                || tokens.LA(1) != Token.EOF || expressions.isEmpty()) {
            throw new AssertionError("Native parser rejected: " + source);
        }
        return expressions.get(expressions.size() - 1);
    }

    private static void expect(String source, boolean expected, Boolean localized) {
        alS expression = parse(source);
        boolean actual = ((amb) expression).b(null, null, null, null);
        if (actual != expected || (localized != null && expression.bDA() != localized)) {
            throw new AssertionError(source + " => value=" + actual
                    + ", localized=" + expression.bDA());
        }
    }

    public static void main(String[] args) {
        expect("#(True)#", true, false);
        expect("#True#", true, false);
        expect("True or False", true, true);
        expect("#(False)# or #(True)#", true, false);
        expect("#(True)# and #(False)#", false, false);
        expect("#(True)# or #(False)# and #(False)#", true, null);
        expect("True or #(False)#", true, null);
        expect("#(#True#)#", true, false);
        expect("a = 2; #(a == 2)# and #((a + 1) == 3)#", true, null);
        expect("#(if (True) then (True) else (False))#", true, false);
        System.out.println("PASS native multiple SHARP subexpressions preserve precedence, aliases, "
                + "conditionals and alS localization metadata");
    }
}
