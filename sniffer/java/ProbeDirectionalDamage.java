import java.lang.reflect.*;
import java.util.*;
public class ProbeDirectionalDamage {
 static PV actor(Map<PC,Integer> stats,int x,int direction){
  Sl facing=new Sl();facing.a(x,0,(short)0,aAS.wL(direction));
  return (PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class},(proxy,m,a)->switch(m.getName()){
   case "a"->stats.containsKey(a[0]);case "c"->stats.getOrDefault(a[0],0);
   case "bcz"->x;case "bcA"->0;case "bcB"->(short)0;
   case "bcL","bcK"->(byte)0;case "baB"->facing;
   default->throw new UnsupportedOperationException(m.getName());});
 }
 public static void main(String[] args){
  for(int direction:new int[]{1,3,5})for(int mask=0;mask<4;mask++){
   fau f=new fau(actor(Map.of(ffw.sgN,100),1,1),actor(Map.of(ffw.sgO,100),0,direction),eVg.rpf,null);
   f.setValue(400);f.Tf(mask);f.mq(false);f.mw(true);f.fSy();
   int expected=direction==1?400:direction==3?440:new int[]{500,1000,405,810}[mask];
   if(f.getValue()!=expected)throw new AssertionError("direction"+direction+" mask"+mask+" actual"+f.getValue()+" expected"+expected);
   System.out.println("direction="+direction+" mask="+mask+" damage="+f.getValue());
  }
 }
}
