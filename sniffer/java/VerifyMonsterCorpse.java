import java.nio.file.Files;
import java.nio.file.Path;
import org.antlr.runtime.ANTLRStringStream;
import org.antlr.runtime.CommonTokenStream;

/** Verify the installed native world codec, without changing any client state. */
public class VerifyMonsterCorpse {
    static void check(boolean value) {
        if (!value) throw new AssertionError("Invalid native corpse appearance");
    }

    static amb criterion(String expression) throws Exception {
        eQb lexer = new eQb(new ANTLRStringStream(expression));
        eQd parser = new eQd(new CommonTokenStream(lexer));
        alS result = parser.fGw();
        check(parser.getNumberOfSyntaxErrors() == 0 && result instanceof amb);
        return (amb) result;
    }

    public static void main(String[] args) throws Exception {
        ctE packet = new ctE();
        check(packet.dp(Files.readAllBytes(Path.of(args[0]))));
        check(packet.eFQ().size() == 1);
        ctF entry = packet.eFQ().get(0);
        eHj actor = new eHj();
        actor.ew(entry.aLJ());
        check(entry.aGJ() == 1 && actor.fsS().Vc == entry.Sn());
        pW fight = actor.fsW();
        check(fight.Ue == -1 && !fight.Uf && fight.Ug);
        check(!fight.Uh && !fight.Ui && fight.Uj == -1);
        check(actor.fuY().ZX.size() == 1);
        check(eHQ.pSA.aKg() == 19);
        rK properties = actor.fta();
        check(properties.XP != null && properties.XP.XT.aiN.size() == 1);
        wV dead = properties.XP.XT.aiN.get(0);
        check(dead.RW == eHQ.pSA.aKg() && dead.aiO == 1);
        // Exercise the real exploration consumer, not just the wire decoder.
        bje npc = new bje();
        new eGn(npc, actor.fsW()).zm();
        check(!npc.dsA()); // Legacy isDead-only payload was ineffective here.
        new eGv(npc, actor.fta()).zm();
        check(npc.dsA() && npc.a(eHQ.pSA));
        cWi attack = new cWi(null);
        attack.aK(npc);
        java.lang.reflect.Field failures = cWi.class.getDeclaredField("nFv");
        failures.setAccessible(true);
        check(((java.util.BitSet) failures.get(attack)).get(cWk.nFG.ordinal()));
        check(!actor.fva().ZR.isEmpty());
        new bjh(npc, actor.fva()).zm();
        for (sT action : actor.fva().ZR) check(!npc.Ds(action.ZU));
        check(npc.Ds(Integer.parseInt(args[1])));
        if (args.length > 2) check(npc.Ds(Integer.parseInt(args[2])));
        check(criterion("IsDead(\"target\")").b(null, npc, null, null));
        check(!criterion("not IsDead(\"target\")").b(null, npc, null, null));
        System.out.println("PASS native corpse: DEAD19, attack forbidden, life-state criteria retain truthful availability");
    }
}
