import org.antlr.runtime.*;
import java.util.*;

/** eQd percent uses alI double remainder, retaining dividend sign. */
public class ProbeNativeRemainder {
    static void check(String source) {
        eQd parser = new eQd(new CommonTokenStream(new eQb(new ANTLRStringStream(source))));
        ArrayList<alS> result = parser.fGv();
        if (parser.getNumberOfSyntaxErrors() != 0 || !((amb)result.get(result.size()-1)).b(null,null,null,null)) throw new AssertionError(source);
    }
    public static void main(String[] args) {
        for(String source : new String[]{"(5 % 2) == 1", "((-5) % 2) == -1", "(5 % (-2)) == 1", "((-5) % (-2)) == -1", "(5.5 % 2) == 1.5", "(5 % 2.5) == 0", "(if (True) then ((-5) % 2) else (0)) == -1"}) check(source);
        System.out.println("PASS native eQd/alI signed and fractional remainders");
    }
}
