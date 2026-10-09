import java.util.ArrayList;
import org.antlr.runtime.*;
/** Original eLm deliberately ignores its parsed constructor arguments. */
public final class ProbeNativeSymbiotSpaceArguments {
    public static void main(String[] args) throws Exception {
        int count = 0;
        for (String arguments : new String[]{"", "\"caster\"", "\"target\"", "1", "\"ignored\", 1 / 0"}) {
            String expression = "GetSpaceInSymbiot(" + arguments + ")";
            eQb lexer = new eQb(new ANTLRStringStream(expression));
            eQd parser = new eQd(new CommonTokenStream(lexer));
            ArrayList<alS> rows = parser.fGv();
            if (parser.getNumberOfSyntaxErrors() != 0 || lexer.getNumberOfSyntaxErrors() != 0)
                throw new AssertionError(expression);
            alS node = rows.getFirst();
            if (!(node instanceof eLm) || ((eLm) node).d(null,null,null,null) != -1)
                throw new AssertionError(expression);
            count++;
        }
        System.out.println("PASS " + count + " original eLm ignored-argument parse/evaluation cases");
    }
}
