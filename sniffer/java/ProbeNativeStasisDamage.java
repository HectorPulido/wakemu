import java.util.*;
public class ProbeNativeStasisDamage {
 public static void main(String[] args) {
  Map<PC,Integer> source=new HashMap<>(Map.of(ffw.sgR,100,ffw.sgS,200,ffw.sgT,0,ffw.sgU,0));
  Map<PC,Integer> target=new HashMap<>(Map.of(ffw.sgW,0,ffw.sgX,100,ffw.sgY,200,ffw.sgZ,300));
  System.out.println("events="+ProbeNativeDamageEventIds.events(917,11));
  int[] expected={100,300,100,300};
  for(int mask=0;mask<4;mask++){
   fau f=new fau(ProbeNativeLightDamage.actor(source,1),ProbeNativeLightDamage.actor(target,0),eVg.rpj,null);
   f.setValue(100);f.Tf(mask);f.mq(false);f.mw(true);f.fSy();if(f.getValue()!=expected[mask])throw new AssertionError("Stasis result");System.out.println("mask="+mask+" value="+f.getValue());
  }
 }
}
