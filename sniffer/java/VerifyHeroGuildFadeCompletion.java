import java.nio.*;
import java.nio.file.*;
import java.lang.reflect.*;
/** Applies the actual native 15548 handler to a selected owned actor offline. */
public final class VerifyHeroGuildFadeCompletion {
    static void set(Object target, String name, Object value) throws Exception {
        Field f=target.getClass().getDeclaredField(name);f.setAccessible(true);f.set(target,value);
    }
    public static void main(String[] args) throws Exception {
        try {
            cue admission=new cue();admission.dp(Files.readAllBytes(Path.of(args[0])));
            byte[] owned=admission.eGo();biB actor=new biB(false);
            actor.dtj().a(actor.dtj().fsS(),owned);actor.dtj().a(actor.dtj().fsR(),owned);
            aTJ account=new aTJ();account.oh(actor.Xi());set(aTx.cWt(),"hsh",account);set(aTx.cWt(),"hsi",actor);
            fkK.suH.d(actor.Xi(),actor);fkJ.suE.av(actor.Xi(),actor.Sn());
            frk.a(new aHd());frp.sZy.o(frk.XE(30));biz.dpY().al(actor);actor.fX(true);actor.fU(false);
            byte[] captured=Files.readAllBytes(Path.of(args[1]));ByteBuffer.wrap(captured).putLong(actor.Sn());
            cyo update=new cyo();update.dp(captured);
            if(update.eLp()[0]!=22)throw new AssertionError("expected native format22");
            dbV.omD.kN(false);
            Constructor<?> ctor=dbW.class.getDeclaredConstructors()[0];ctor.setAccessible(true);
            Object transition=ctor.newInstance(dbV.omD,null,actor,aTx.cWt(),actor,0L,(byte)0);
            set(transition,"omI",true);
            Field f=dbW.class.getDeclaredField("omJ");f.setAccessible(true);ark gate=(ark)f.get(transition);
            if(gate.isValid())throw new AssertionError("fade unexpectedly complete before guild update");
            ciu.eDi().b(update);
            if(!gate.isValid())throw new AssertionError("actual native15548 did not release fade");
            if(aTx.cWt().cWu()!=actor||fkK.suH.sY(actor.Sn())!=actor)throw new AssertionError("actor identity replaced");
            System.out.println("PASS actual ciu15548→biB.as(format22)→biK→bkY releases dbX fade gate and preserves selected owned actor");
        }catch(Throwable t){t.printStackTrace();System.exit(1);}System.exit(0);
    }
}
