import java.nio.file.*;import java.util.*;
public class ProbeNativeAreaStateManager{
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Map<Integer,faV> selected=new HashMap<>();Map<Integer,Boolean> flags=new HashMap<>();
  apw.bGL().a(new aKa(),new apB<aKa>(){public void load(aKa a){if(a.d()==1474||a.d()==1477||a.d()==1558){selected.put(a.d(),bcN.hFx.a(a));flags.put(a.d(),Arrays.stream(a.ckE()).anyMatch(x->x==12));}}});
  for(int ref:new int[]{1474,1477,1558}){
   faV prototype=selected.get(ref);
   faV area=prototype.b(new fbm(901+ref,2,-3,(short)4,null,7,null,(short)1,aAS.wL(3)));
   boolean expected=flags.get(ref);
   if((area.bax()!=null)!=expected)throw new AssertionError("Qfproperty "+ref);
   if(area.bcL()!=0)throw new AssertionError("Qq radius");
   System.out.println("PASS area"+ref+" ownQf="+expected+" radius0 UID="+area.Sn());
  }
 }
}
