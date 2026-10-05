import java.nio.file.*;
import java.util.*;
public class ProbeNativeStateVariantSelection {
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");fyZ.guX().a(new bbV());
  for(int ref:new int[]{3425,3442,8913}){
   fyW state=fyZ.guX().aax(ref);if(state==null)throw new AssertionError("state");
   int accepted=0;List<Integer> roots=new ArrayList<>();
   for(eVn effect:state.fH((short)10)){
    boolean accept=!state.guW()||effect.dd(1L);
    if(accept){accepted++;roots.add(effect.aZE());}
   }
   if(ref==3425&&(state.guW()||!roots.contains(159161)))throw new AssertionError("critical incorrectly suppresses Concentration");
   System.out.println("PASS native eZk.c critical state"+ref+" selective="+state.guW()+" accepted="+accepted+" roots="+roots);
  }
 }
}
