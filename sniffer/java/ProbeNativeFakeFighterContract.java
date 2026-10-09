import java.nio.file.*;
import java.util.*;
/** Installed faW prototype constructor state, no runtime connection. */
public class ProbeNativeFakeFighterContract {
 static class Owner extends biw { public byte bcM(){return 0;} public long Sn(){return 7;} public Qf bax(){return null;} }
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Set<Integer> wanted=new HashSet<>();for(String value:args)wanted.add(Integer.parseInt(value));
  Map<Integer,faV> prototypes=new HashMap<>();apw.bGL().a(new aKa(),new apB<aKa>(){public void load(aKa raw){if(wanted.contains(raw.d()))prototypes.put(raw.d(),bcN.hFx.a(raw));}});
  Owner owner=new Owner();
  for(int reference:wanted){faV area=prototypes.get(reference).b(new fbm(reference+900,2,3,(short)4,null,7,owner,(short)30,aAS.wL(7)));
   System.out.println(reference+" class="+area.getClass().getName()+" type="+area.aeV()+" Qf="+(area.bax()!=null)+" AP="+area.a(ffw.sgD)+" HP="+area.a(ffw.sgC)+" bcM="+area.bcM()+" bcN="+area.bcN()+" bcP="+area.bcP()+" bcO="+area.bcO()+" radius="+area.bcL()+" height="+area.bcK()+" direction="+area.baA()+" ownerActivate="+area.e((amP)owner)+" ownerTargets="+area.d((amP)owner));
  }
 }
}
