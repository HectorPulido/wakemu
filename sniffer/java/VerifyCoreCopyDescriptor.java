import java.lang.reflect.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
/** Original vJ/vK/up book codec and actual eZw.fRo native fTc selection. */
public final class VerifyCoreCopyDescriptor {
    public static void main(String[] args)throws Exception{
        Path output=Path.of(args[0]);Files.createDirectories(output);eGM.a(null);
        Method method=eZw.class.getDeclaredMethod("fRo");method.setAccessible(true);
        faB factory=(faB)method.invoke(new eZw());
        if(factory.fTc())throw new AssertionError("Native1002 fTc must disable level trailer");
        vJ original=new vJ();original.agn=2382;original.VY="Copied Héctor";original.ago=1;original.agp=-1;original.Yf=200;original.Uj=17;original.ags=-1;original.agt=7;original.agu=false;original.agq=new vK();
        up appearance=original.agq.agv;appearance.ade=100;appearance.adf=12345;appearance.Su=new byte[]{8,1,16,2};appearance.adg=1;
        yD action=new yD();action.amt.aaq=123456789012L;action.amt.amm=6266;action.amt.Yf=200;appearance.adh.ams.add(action);
        tB stat=new tB();stat.Sj=1;stat.abj=140;stat.abk=330;stat.abl=0;stat.abm=10000;appearance.adi.abi.add(stat);
        uq category=new uq();category.TU=-3;category.abE=9876;appearance.adj.add(category);
        ByteBuffer wire=ByteBuffer.allocate(4096);if(!original.aF(wire))throw new AssertionError("native descriptor writer");byte[] bytes=Arrays.copyOf(wire.array(),wire.position());
        vJ decoded=new vJ();if(!decoded.aG(ByteBuffer.wrap(bytes)))throw new AssertionError("native descriptor reader");
        if(decoded.agp!=-1||decoded.agt!=7||decoded.agq.agv.adh.ams.size()!=1||decoded.agq.agv.adh.ams.get(0).amt.aaq!=123456789012L)throw new AssertionError("native book/owner identity");
        Files.write(output.resolve("copy-descriptor.bin"),bytes);
        Map<String,Object> facts=new LinkedHashMap<>();facts.put("completed_normally",true);facts.put("include_levels",factory.fTc());facts.put("reference",decoded.agn);facts.put("constructor_actor",decoded.agp);facts.put("owner",decoded.agt);facts.put("book_uid",decoded.agq.agv.adh.ams.get(0).amt.aaq);facts.put("book_reference",decoded.agq.agv.adh.ams.get(0).amt.amm);facts.put("book_level",decoded.agq.agv.adh.ams.get(0).amt.Yf);
        Files.writeString(output.resolve("observations.json"),VerifyCombatReconstructionSlice.json(facts));
        System.out.println("PASS original eZw.fRo/faB.fTc false and vJ/vK/up owner/book identities");
    }
}
