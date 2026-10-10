import org.antlr.runtime.*;
import java.util.*;
/** Real native criterion + actual NPC world DEAD property, no graphics. */
public final class VerifyCorpseHarvestCriteria {
    static amb parse(String text) {
        eQd parser = new eQd(new CommonTokenStream(new eQb(new ANTLRStringStream(text))));
        ArrayList<alS> expressions = parser.fGv();
        if (parser.getNumberOfSyntaxErrors() != 0 || expressions.size() != 1)
            throw new AssertionError("Cannot parse " + text);
        return (amb) expressions.get(0);
    }
    public static void main(String[] args) {
        bje target = bje.dsi();
        amb corpse = parse("IsDead(\"target\")");
        amb living = parse("not IsDead(\"target\")");
        if (corpse.b(null,target,null,null) || !living.b(null,target,null,null))
            throw new AssertionError("Living target criterion mismatch");
        target.a(eHQ.pSA, (byte) 1);
        if (!target.dsA() || !corpse.b(null,target,null,null)
                || living.b(null,target,null,null))
            throw new AssertionError("Dead target criterion mismatch");
        System.out.println("PASS native parsed IsDead/not IsDead: actual NPC DEAD19 selects corpse only");
    }
}
