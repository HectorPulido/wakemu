import java.nio.file.*; import java.util.*;
public class ProbeNativeGateContract {
 static class Owner extends biw { byte affiliation; public byte bcM(){return affiliation;} public long Sn(){return 7;} public Qf bax(){return null;} }
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Map<Integer,faV> selected=new HashMap<>();
  apw.bGL().a(new aKa(),new apB<aKa>(){public void load(aKa a){if(a.d()==823||a.d()==2131)selected.put(a.d(),bcN.hFx.a(a));}});
  for(int ref:new int[]{823,2131}){
   Owner owner=new Owner(); owner.affiliation=0;
   fbm spec=new fbm(900+ref,2,3,(short)4,null,7,owner,(short)1,aAS.wL(3)); spec.M((byte)5);
   faV area=selected.get(ref).b(spec);
   if(!(area instanceof bcS)||!(area instanceof faX)||area.aeV()!=19||area.bax()!=null||area.bcL()!=0)throw new AssertionError("native gate identity/Qf");
   if(area.bcM()!=0||area.bcN()!=5||area.baM().getX()!=2||area.baM().getY()!=3)throw new AssertionError("gate capture/position");
   owner.affiliation=1;
   if(area.bcM()!=0||area.bcN()!=5||area.e((amP)null)||area.c((amP)null)!=null||area.d((amP)null)!=null)throw new AssertionError("gate independent affiliation/callbacks");
   if(area.baG()||area.baK()||!area.baF())throw new AssertionError("native Qq fresh guards");
   System.out.println("PASS native gate"+ref+" faX/bcS type19; own position; captured bcM0; fbm bcN5; nullQf; no callback targets");
  }
 }
}
